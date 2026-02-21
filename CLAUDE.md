# Flexi-HAL Firmware Builder

Personal, unofficial grblHAL firmware builder for the Flexi-HAL CNC board. Not affiliated with or supported by the grblHAL project or Expatria Technologies. Converts grblHAL web builder JSON exports into PlatformIO builds via GitHub Actions.

## Repository structure

- `configs/` — grblHAL web builder JSON exports, one per firmware build
- `board_meta/` — board-specific metadata (MCU, extra symbols/libs/scripts) not included in web builder exports
- `scripts/generate_pio_config.py` — converts JSON config + board meta + upstream `driver.json` into `platformio.local.ini`
- `scripts/install_plugins.py` — sparse-clones `my_plugin` GitHub repos, copies `.c`/`.h` into driver `Src/`
- `.github/workflows/build.yml` — 3-job workflow: discover configs, build matrix, create release

## How the build works

The upstream grblHAL STM32F4xx driver repo uses PlatformIO with `stm32cube` framework. Its `platformio.ini` includes `extra_configs = platformio.local.ini`, so we generate that overlay file without modifying any upstream sources.

### Config sources merged into platformio.local.ini

1. **Web builder JSON** (`configs/*.json`) — `board`, `symbols`, `my_plugin`, `URL`
2. **Driver repo** (`driver.json`) — `pio_board`, `ldscript` looked up by board symbol in `boards[].caps`
3. **Board metadata** (`board_meta/BOARD_*.json`) — `board_build_mcu`, `extra_symbols`, `extra_lib_deps`, `extra_scripts`

### Key behaviors

- Symbols from JSON take precedence over board meta `extra_symbols` when deduplicating
- Board symbol (e.g. `BOARD_FLEXI_HAL`) gets `=1` suffix automatically
- `OVERRIDE_MY_MACHINE` is already in upstream `${common.build_flags}`, so `-D` flags fully control board config
- Networking stack is auto-detected: `_WIZCHIP_` in symbols -> `${wiznet_networking.*}`, `ETHERNET_ENABLE` alone -> `${eth_networking.*}`
- `my_plugin` URLs must be GitHub tree URLs: `https://github.com/{owner}/{repo}/tree/{branch}/{path}`

## Local testing

```sh
git clone --recurse-submodules --depth 1 https://github.com/grblHAL/STM32F4xx driver
python3 scripts/generate_pio_config.py --config configs/dgoodlad-flexihal.json --driver-dir driver --board-meta board_meta --env-name dgoodlad_flexihal
python3 scripts/install_plugins.py --config configs/dgoodlad-flexihal.json --driver-dir driver
pio run -d driver -e dgoodlad_flexihal
```

The `driver/` directory is gitignored and should be cloned fresh for testing.

## CI workflow

- **Triggers**: push to main (path-filtered), PRs, manual dispatch (with optional single config input)
- **Discover job**: lists all `configs/*.json` files as a matrix
- **Build job**: clones driver repo, generates overlay, installs plugins, runs `pio run`, uploads `.bin`/`.elf`/`.uf2`
- **Release job** (main only): creates a GitHub release with all firmware artifacts
- Env name is derived from config filename: `configs/foo-bar.json` -> env `foo_bar`
