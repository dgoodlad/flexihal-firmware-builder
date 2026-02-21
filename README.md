# Flexi-HAL Firmware Builder

**Personal, unofficial** [grblHAL](https://github.com/grblHAL) firmware builds for the [Flexi-HAL](https://github.com/Expatria-Technologies/Flexi-HAL) CNC controller board. This project is not affiliated with, endorsed by, or supported by the grblHAL project or Expatria Technologies. Use at your own risk.

Configure your firmware in the [grblHAL web builder](http://svn.io-engineering.com:8080/?driver=STM32F4xx&board=Flexi-HAL), export the JSON, drop it in `configs/`, push, and get firmware binaries from a GitHub release.

## How it works

```
configs/*.json ──> generate_pio_config.py ──> platformio.local.ini ──> pio run ──> .bin/.elf/.uf2
                          |
                   board_meta/*.json
                   driver.json (from upstream repo)
```

1. The GitHub Actions workflow discovers all JSON configs in `configs/`
2. For each config, it clones the upstream [grblHAL STM32F4xx](https://github.com/grblHAL/STM32F4xx) driver repo at the commit pinned in `upstream.json`
3. `generate_pio_config.py` converts the JSON config into a `platformio.local.ini` overlay — the driver repo's `platformio.ini` already includes this overlay via `extra_configs`
4. `install_plugins.py` fetches any `my_plugin` sources referenced in the config
5. PlatformIO builds the firmware
6. On push to `main`, a GitHub release is created with the firmware binaries

## Usage

### Adding or updating a config

1. Go to the [grblHAL web builder](http://svn.io-engineering.com:8080/?driver=STM32F4xx&board=Flexi-HAL)
2. Configure your desired features and plugins
3. Export the JSON configuration
4. Save it as `configs/<your-name>.json`
5. Push to `main` (or open a PR to test first)

The workflow will build firmware for every JSON file in `configs/`.

### Manual dispatch

You can trigger a build manually from the Actions tab. Optionally specify a single config file path (e.g. `configs/dgoodlad-flexihal.json`) to build just one config.

### Local testing

```sh
# Clone the driver repo at the pinned commit
REF=$(python3 -c "import json; print(json.load(open('upstream.json'))['driver_ref'])")
URL=$(python3 -c "import json; print(json.load(open('upstream.json'))['driver_url'])")
git init driver && cd driver
git remote add origin "$URL"
git fetch --depth 1 origin "$REF"
git checkout FETCH_HEAD
git submodule update --init --recursive --depth 1
cd ..

# Generate the PlatformIO config
python3 scripts/generate_pio_config.py \
  --config configs/dgoodlad-flexihal.json \
  --driver-dir driver \
  --board-meta board_meta \
  --env-name dgoodlad_flexihal \
  --upstream upstream.json

# Install plugins
python3 scripts/install_plugins.py \
  --config configs/dgoodlad-flexihal.json \
  --driver-dir driver

# Build
pip install platformio
pio run -d driver -e dgoodlad_flexihal
```

Firmware outputs land in `driver/.pio/build/dgoodlad_flexihal/`.

## Repository structure

```
upstream.json             Global upstream version pins (driver commit, dep SHAs)
configs/                  Web builder JSON exports (one per build)
board_meta/               Board-specific metadata not in the web builder export
scripts/
  generate_pio_config.py  JSON config -> platformio.local.ini
  install_plugins.py      Fetch my_plugin sources from GitHub
.github/workflows/
  build.yml               CI: discover -> build (matrix) -> release
  check-updates.yml       Automated upstream update PRs
```

### Board metadata

The web builder JSON export doesn't include certain hardware constants that PlatformIO needs. These are stored in `board_meta/BOARD_FLEXI_HAL.json`:

- `board_build_mcu` — exact MCU part number
- `extra_symbols` — hardware constants like `HSE_VALUE` and `NVS_SIZE`
- `extra_lib_deps` — additional PlatformIO libraries (eeprom, plugins, probe plugin)
- `extra_scripts` — post-build scripts (UF2 generation)

The script also reads `pio_board` and `ldscript` from the driver repo's own `driver.json`.

### Upstream version pinning

Builds are pinned to specific upstream commits via `upstream.json` at the repo root:

- `driver_url` — the upstream driver repo URL
- `driver_ref` — commit SHA to clone the driver at (pinning the driver also pins core, plugins, and networking via submodules)
- `deps` — map of GitHub URL to commit SHA for third-party dependencies (e.g. `grblhal_probe_plugin`)

A weekly workflow (`.github/workflows/check-updates.yml`) checks for new upstream commits and opens a PR on the `auto-update/upstream` branch. The PR includes compare links and the grblHAL core build date. It can also be triggered manually from the Actions tab.

### Networking detection

The script auto-detects the networking stack from the config symbols:

- `_WIZCHIP_` present -> WizNet (W5500) networking stack
- `ETHERNET_ENABLE` without `_WIZCHIP_` -> native STM32 Ethernet stack
