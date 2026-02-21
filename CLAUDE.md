# Flexi-HAL Firmware Builder

Personal, unofficial grblHAL firmware builder for the Flexi-HAL CNC board. Not affiliated with or supported by the grblHAL project or Expatria Technologies. Converts grblHAL web builder JSON exports into PlatformIO builds via GitHub Actions.

## Repository structure

- `upstream.json` — global upstream version pins (driver commit SHA, third-party dep SHAs)
- `configs/` — grblHAL web builder JSON exports, one per firmware build
- `board_meta/` — board-specific metadata (MCU, extra symbols/libs/scripts) not included in web builder exports
- `scripts/generate_pio_config.py` — converts JSON config + board meta + upstream `driver.json` into `platformio.local.ini`
- `scripts/install_plugins.py` — sparse-clones `my_plugin` GitHub repos, copies `.c`/`.h` into driver `Src/`
- `.github/workflows/build.yml` — 3-job workflow: discover configs, build matrix, create release
- `.github/workflows/check-updates.yml` — weekly check for upstream updates, opens PRs on `auto-update/upstream`

## How the build works

The upstream grblHAL STM32F4xx driver repo uses PlatformIO with `stm32cube` framework. Its `platformio.ini` includes `extra_configs = platformio.local.ini`, so we generate that overlay file without modifying any upstream sources.

### Config sources merged into platformio.local.ini

1. **Upstream pins** (`upstream.json`) — `driver_url`, `driver_ref`, `deps` (GitHub URL -> commit SHA)
2. **Web builder JSON** (`configs/*.json`) — `board`, `symbols`, `my_plugin`, `URL` (URL kept for web builder compat but not used by build)
3. **Driver repo** (`driver.json`) — `pio_board`, `ldscript` looked up by board symbol in `boards[].caps`
4. **Board metadata** (`board_meta/BOARD_*.json`) — `board_build_mcu`, `extra_symbols`, `extra_lib_deps`, `extra_scripts`

### Key behaviors

- Symbols from JSON take precedence over board meta `extra_symbols` when deduplicating
- Board symbol (e.g. `BOARD_FLEXI_HAL`) gets `=1` suffix automatically
- `OVERRIDE_MY_MACHINE` is already in upstream `${common.build_flags}`, so `-D` flags fully control board config
- Networking stack is auto-detected: `_WIZCHIP_` in symbols -> `${wiznet_networking.*}`, `ETHERNET_ENABLE` alone -> `${eth_networking.*}`
- `my_plugin` URLs must be GitHub tree URLs: `https://github.com/{owner}/{repo}/tree/{branch}/{path}`
- Third-party `extra_lib_deps` GitHub URLs get `#SHA` appended from `upstream.json` `deps` for reproducible builds

## Local testing

```sh
REF=$(python3 -c "import json; print(json.load(open('upstream.json'))['driver_ref'])")
URL=$(python3 -c "import json; print(json.load(open('upstream.json'))['driver_url'])")
git init driver && cd driver && git remote add origin "$URL"
git fetch --depth 1 origin "$REF" && git checkout FETCH_HEAD
git submodule update --init --recursive --depth 1 && cd ..
python3 scripts/generate_pio_config.py --config configs/dgoodlad-flexihal.json --driver-dir driver --board-meta board_meta --env-name dgoodlad_flexihal --upstream upstream.json
python3 scripts/install_plugins.py --config configs/dgoodlad-flexihal.json --driver-dir driver
pio run -d driver -e dgoodlad_flexihal
```

The `driver/` directory is gitignored and should be cloned fresh for testing.

## CI workflow

- **Triggers**: push to main (path-filtered on `configs/`, `scripts/`, `board_meta/`, `upstream.json`, workflow file), PRs, manual dispatch (with optional single config input)
- **Discover job**: lists all `configs/*.json` files as a matrix
- **Build job**: clones driver repo at pinned commit from `upstream.json`, generates overlay, installs plugins, runs `pio run`, uploads `.bin`/`.elf`/`.uf2`
- **Release job** (main only): creates a GitHub release with all firmware artifacts
- Env name is derived from config filename: `configs/foo-bar.json` -> env `foo_bar`

## Check-updates workflow

- **Schedule**: weekly (Monday 06:00 UTC) + manual dispatch
- Compares current `upstream.json` pins against upstream HEAD for driver and each dep
- If any differ, updates `upstream.json` and creates/updates a PR on `auto-update/upstream`
- PR body includes old/new SHAs, GitHub compare links, and grblHAL core build date
- Since `upstream.json` is in build workflow path triggers, the PR automatically gets a build check
