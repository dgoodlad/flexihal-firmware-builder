#!/usr/bin/env python3
"""Convert a grblHAL web builder JSON config into a platformio.local.ini overlay."""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate platformio.local.ini from grblHAL web builder JSON config"
    )
    parser.add_argument(
        "--config", required=True, help="Path to the web builder JSON config file"
    )
    parser.add_argument(
        "--driver-dir", required=True, help="Path to the cloned driver repo"
    )
    parser.add_argument(
        "--board-meta", required=True, help="Path to the board_meta directory"
    )
    parser.add_argument(
        "--env-name", required=True, help="PlatformIO environment name"
    )
    parser.add_argument(
        "--upstream", default=None, help="Path to upstream.json for dependency pinning"
    )
    return parser.parse_args()


def load_json(path):
    with open(path) as f:
        return json.load(f)


def find_board_in_driver(driver_json, board_symbol):
    """Look up the board in driver.json and return its caps (pio_board, ldscript)."""
    for board in driver_json.get("boards", []):
        if board.get("symbol") == board_symbol:
            return board.get("caps", {})
    return None


def detect_networking(symbols):
    """Detect which networking stack to use based on symbols."""
    symbol_names = {s.split("=")[0] for s in symbols}
    has_wizchip = "_WIZCHIP_" in symbol_names
    has_ethernet = "ETHERNET_ENABLE" in symbol_names

    if has_wizchip:
        return "wiznet"
    elif has_ethernet:
        return "eth"
    return None


def merge_symbols(json_symbols, extra_symbols):
    """Merge symbols, with JSON symbols taking precedence. Deduplicates by key."""
    # Build a dict of key -> full symbol string
    merged = {}
    # Add extras first (lower precedence)
    for sym in extra_symbols:
        key = sym.split("=")[0]
        merged[key] = sym
    # Add JSON symbols (higher precedence, overrides extras)
    for sym in json_symbols:
        key = sym.split("=")[0]
        merged[key] = sym
    return list(merged.values())


def ensure_board_symbol(symbols, board_symbol):
    """Ensure the board symbol has =1 suffix."""
    key = board_symbol
    # Check if already present
    for i, sym in enumerate(symbols):
        sym_key = sym.split("=")[0]
        if sym_key == key:
            # Already present, ensure it has =1
            if "=" not in sym:
                symbols[i] = f"{sym}=1"
            return symbols

    # Not present, add it
    symbols.insert(0, f"{key}=1")
    return symbols


def apply_dep_pins(extra_lib_deps, deps):
    """Append #SHA to GitHub lib_dep URLs that have a matching pin in deps."""
    if not deps:
        return extra_lib_deps
    pinned = []
    for dep in extra_lib_deps:
        if dep in deps:
            dep = f"{dep}#{deps[dep]}"
        pinned.append(dep)
    return pinned


def generate_ini(env_name, pio_board, board_build_mcu, ldscript, symbols,
                 networking, extra_lib_deps, extra_scripts):
    """Generate the platformio.local.ini content."""
    lines = []
    lines.append(f"[env:{env_name}]")
    lines.append(f"board = {pio_board}")
    lines.append(f"board_build.mcu = {board_build_mcu}")
    lines.append(f"board_build.ldscript = {ldscript}")

    # build_flags
    lines.append("build_flags =")
    lines.append("  ${common.build_flags}")
    if networking == "wiznet":
        lines.append("  ${wiznet_networking.build_flags}")
    elif networking == "eth":
        lines.append("  ${eth_networking.build_flags}")
    for sym in symbols:
        lines.append(f"  -D {sym}")

    # lib_deps
    lines.append("lib_deps =")
    lines.append("  ${common.lib_deps}")
    for dep in extra_lib_deps:
        lines.append(f"  {dep}")
    if networking == "wiznet":
        lines.append("  ${wiznet_networking.lib_deps}")
    elif networking == "eth":
        lines.append("  ${eth_networking.lib_deps}")

    # lib_extra_dirs
    lines.append("lib_extra_dirs = ${common.lib_extra_dirs}")

    # extra_scripts
    if extra_scripts:
        lines.append("extra_scripts =")
        for script in extra_scripts:
            lines.append(f"  {script}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


def main():
    args = parse_args()

    # Load configs
    config = load_json(args.config)
    board_symbol = config["board"]

    driver_json_path = os.path.join(args.driver_dir, "driver.json")
    driver_json = load_json(driver_json_path)

    board_meta_path = os.path.join(args.board_meta, f"{board_symbol}.json")
    board_meta = load_json(board_meta_path)

    # Look up board in driver.json
    board_caps = find_board_in_driver(driver_json, board_symbol)
    if board_caps is None:
        print(f"Error: board '{board_symbol}' not found in driver.json", file=sys.stderr)
        sys.exit(1)

    pio_board = board_caps["pio_board"]
    ldscript = board_caps["ldscript"]

    # Board metadata
    board_build_mcu = board_meta["board_build_mcu"]
    extra_symbols = board_meta.get("extra_symbols", [])
    extra_lib_deps = board_meta.get("extra_lib_deps", [])
    extra_scripts = board_meta.get("extra_scripts", [])

    # Merge symbols
    json_symbols = config.get("symbols", [])
    symbols = merge_symbols(json_symbols, extra_symbols)
    symbols = ensure_board_symbol(symbols, board_symbol)

    # Pin dependency versions from upstream.json
    upstream = load_json(args.upstream) if args.upstream else {}
    deps = upstream.get("deps", {})
    extra_lib_deps = apply_dep_pins(extra_lib_deps, deps)

    # Detect networking
    networking = detect_networking(symbols)

    # Generate ini
    ini_content = generate_ini(
        args.env_name, pio_board, board_build_mcu, ldscript,
        symbols, networking, extra_lib_deps, extra_scripts,
    )

    # Write to driver dir
    output_path = os.path.join(args.driver_dir, "platformio.local.ini")
    with open(output_path, "w") as f:
        f.write(ini_content)

    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
