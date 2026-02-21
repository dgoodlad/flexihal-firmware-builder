#!/usr/bin/env python3
"""Install my_plugin dependencies from grblHAL web builder JSON config."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


def parse_args():
    parser = argparse.ArgumentParser(
        description="Install my_plugin sources from grblHAL web builder JSON config"
    )
    parser.add_argument(
        "--config", required=True, help="Path to the web builder JSON config file"
    )
    parser.add_argument(
        "--driver-dir", required=True, help="Path to the cloned driver repo"
    )
    return parser.parse_args()


def parse_github_tree_url(url):
    """Parse a GitHub tree URL into (owner, repo, branch, path).

    Expected format: https://github.com/{owner}/{repo}/tree/{branch}/{path}
    """
    pattern = r"https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return match.group(1), match.group(2), match.group(3), match.group(4)


def clone_and_extract(owner, repo, branch, path, dest_dir):
    """Sparse-clone a GitHub repo and copy plugin .c/.h files to dest_dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_url = f"https://github.com/{owner}/{repo}.git"
        clone_dir = os.path.join(tmpdir, repo)

        # Sparse clone
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch,
             "--filter=blob:none", "--sparse", repo_url, clone_dir],
            check=True,
        )
        subprocess.run(
            ["git", "-C", clone_dir, "sparse-checkout", "set", path],
            check=True,
        )

        # Copy .c and .h files to destination
        src_path = os.path.join(clone_dir, path)
        if not os.path.isdir(src_path):
            print(f"Error: plugin path '{path}' not found in {owner}/{repo}", file=sys.stderr)
            sys.exit(1)

        copied = 0
        for filename in os.listdir(src_path):
            if filename.endswith((".c", ".h")):
                src = os.path.join(src_path, filename)
                dst = os.path.join(dest_dir, filename)
                shutil.copy2(src, dst)
                print(f"  Copied {filename}")
                copied += 1

        return copied


def main():
    args = parse_args()

    with open(args.config) as f:
        config = json.load(f)

    plugins = config.get("my_plugin", [])
    if not plugins:
        print("No my_plugin entries found, nothing to install.")
        return

    dest_dir = os.path.join(args.driver_dir, "Src")
    os.makedirs(dest_dir, exist_ok=True)

    for url in plugins:
        print(f"Installing plugin from: {url}")
        owner, repo, branch, path = parse_github_tree_url(url)
        count = clone_and_extract(owner, repo, branch, path, dest_dir)
        print(f"  Installed {count} file(s)")


if __name__ == "__main__":
    main()
