# Mario Kart Wii for Nintendo 3DS

A native Nintendo 3DS port and CIA builder for **Mario Kart Wii**, originally developed by **dudewhat** and continued with features and fixes.

This repository contains **no copyrighted Nintendo assets**. It builds an installable CIA on your own computer directly from your legally dumped retail Mario Kart Wii disc.

---

## Overview

Unlike an emulator, this is a **native port** running directly on the 3DS ARM11 CPU and PICA200 GPU:
- **Game Engine & Physics**: Powered by [Kinoko](https://github.com/vabold/Kinoko) (a C++ cleanroom reimplementation of Mario Kart Wii's physics and game logic).
- **Renderer**: Custom hardware renderer built on [citro3d](https://github.com/devkitPro/citro3d) with custom PICA vertex shaders (`mkw.v.pica`, `effect.v.pica`) and texture optimization.
- **Audio**: Custom DSP audio streaming system supporting retail sound effects and streamed music.
- **Bottom Screen**: Custom touchscreen HUD, real-time leaderboard, and top-down minimap.
- **Cleanroom Pipeline**: The included build system automatically extracts, converts, and optimizes courses, character models, animations, and sound effects directly from a user-supplied retail Mario Kart Wii disc dump.

### Performance Targets
- **New 3DS / New 2DS**: 60 FPS (30 FPS with stereoscopic 3D enabled)
- **Old 3DS / 2DS**: 30 FPS

---

## Features

- **Game Modes**:
  - **Grand Prix (150cc)**: Race all four courses in a cup with standings and points.
  - **Time Trials**: Solo time trial with Triple Mushroom; best times per course saved to SD card.
  - **VS Race**: Solo VS race against 11 CPU opponents.
- **Full Vehicle Roster**: All 12 vehicles available for every driver (including unlockables).
- **Modern Controls**:
  - Hop and drift or trick off ramps using **R** (Mario Kart 7 style).
  - Manual tricks and bike wheelies using **X / Y** (direction determined by Circle Pad) or the **D-Pad**.
- **HUD & Visuals**:
  - Particle effects: start-boost charge smoke, burnout puffs, drift tyre smoke, off-road dust, and landing puffs.
  - Restored Toadette hair braid attachments and HUD position display polish.
  - Official Nintendo 3DS system splash and custom Standard Kart M HOME menu banner/icon.

---

## Controls

| Button | Action |
|---|---|
| Circle Pad | Steer; hold Up/Down when using an item to throw Forward/Backward |
| A | Accelerate |
| B | Brake / Reverse |
| R | Hop and drift; trick off ramps (MK7 style) |
| X / Y | Trick (Circle Pad selects direction) / bike wheelie |
| D-Pad | Trick / wheelie (Wii Classic Controller style) |
| L | Use item |
| START | Pause race |
| Touch Screen | Switch bottom-screen minimap / leaderboard view |

---

## Requirements

To build the CIA, you need:
1. **A clean dump of Mario Kart Wii (USA)** (`RMCE01`) as an `.iso` or `.wbfs` image.
   *(RVZ or NKit dumps should first be converted to ISO using Dolphin).*
2. **Tools & Dependencies**:
   - [devkitPro](https://devkitpro.org/wiki/Getting_Started) with `3ds-dev` (`sudo dkp-pacman -S 3ds-dev` on macOS/Linux, or tick "3DS Development" in the Windows installer)
   - **Python 3.11** or newer (with PATH enabled)
   - **Node.js (LTS)** (used by BRRES model exporters)
   - **Git** (Git for Windows on PC: https://git-scm.com/download/win)
   - **Xcode Command Line Tools** (on macOS: `xcode-select --install`)
   - ~15 GB free disk space

---

## Quick Start (Building the CIA)

### 1. Clone the repository
```bash
git clone --recurse-submodules https://github.com/darthmdev/mkw-3ds-cia-builder.git
cd mkw-3ds-cia-builder
```
*(If cloned without submodules, run `git submodule update --init --recursive` followed by `python3 tools/bootstrap.py`)*

### 2. Build
**On Windows (Easy Launcher):**
- Double-click `Build MKW CIA.bat`.
- Drag your Mario Kart Wii (USA) disc image into the window and press `Enter`.

**On macOS (Easy Launcher):**
- Double-click `Build MKW CIA.command`.
- Drag your Mario Kart Wii (USA) disc image into the Terminal window and press `Return`.

**On Command Line:**
```bash
# Setup virtual environment and dependencies
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
npm ci

# Build CIA
python3 tools/release/build_cia.py "/path/to/Mario Kart Wii (USA).iso"
```

The build pipeline will:
1. Fetch and verify pinned CIA tools (`makerom`, `bannertool`).
2. Verify the disc dump against `tools/release/usa-disc.json`.
3. Cook and convert all course models, drivers, karts, effects, UI, and audio into 3DS-optimized formats.
4. Compile the native ELF using `arm-none-eabi-g++` and Citro3D.
5. Package the game into `build/release/mkw-3ds.cia`.

### 3. Install
- Copy `build/release/mkw-3ds.cia` to your 3DS SD card.
- Install it using **FBI** (Custom Firmware required: [3ds.hacks.guide](https://3ds.hacks.guide)).
- Run **DSP1** on your 3DS at least once to ensure DSP audio firmware is dumped.

> **Note**: Do not share pre-built CIAs as they contain proprietary game assets. Share this repository and builder instead.

---

## Project Structure

```
├── .gitmodules           # Submodule configurations (citro3d, kinoko, gclib, noclip)
├── dependencies.json     # Pinned dependency revisions and references
├── include/mkw/          # Engine, audio, course, and UI header files
├── src/                  # Native C++ game engine, renderer, audio, and PICA shaders
├── tools/                # Python and TypeScript asset cookers, exporters, and compilers
│   ├── release/          # CIA build and packaging scripts (build_cia.py)
│   └── import_courses.py # SZS course importer and parser
├── patches/              # Target patches applied to vendor libraries (Kinoko & Citro3D)
├── licenses/             # Open-source licenses of third-party libraries
└── vendor/               # Submodules (Kinoko, noclip.website, gclib, citro3d)
```

---

## Future Roadmap

- [ ] **Custom Track Support**: Extend `tools/import_courses.py` and `tools/course_catalog.py` to allow importing custom tracks.
- [ ] **Retro Rewind Port**: Support loading and selecting track sets from the popular *Retro Rewind* distribution.
- [ ] **Battle Mode**: Implement Balloon Battle and Coin Runners rules and arenas.
- [ ] **Old 3DS Memory Optimization**: Further vertex/texture compression to maximize stability across all 3DS hardware revisions.
- [ ] **Multiplayer / Networking**: Investigate local wireless (adhoc) and Pretendo network integration.

---

## Contributing

Contributions are welcome! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Clean code and C++23 standards.
- 3DS hardware and memory constraint guidelines (Old 3DS vs New 3DS).
- AI assistance policy (AI code is allowed, but must be reviewed and tested).
- Local build and emulator/hardware testing instructions.

---

## Credits & Acknowledgements

- **dudewhat** (Discord) — Original author and creator of the Mario Kart Wii 3DS port, hardware renderer, DSP audio engine, and CIA packaging pipeline.
- **DarthMDev** — Repository maintenance, Windows build support, project documentation, architecture archive, and mod support (in progress).
- **MiniBandit** — Gameplay improvements (Grand Prix, Time Trials, 12 vehicles, controls, visual effects) and Windows builder support.
- [Kinoko](https://github.com/vabold/Kinoko) by **vabold**, **snailspeed3**, and contributors — Cleanroom C++ reimplementation of Mario Kart Wii physics and game mechanics.
- [citro3d](https://github.com/devkitPro/citro3d) & [libctru](https://github.com/devkitPro/libctru) by the **devkitPro team** — Nintendo 3DS homebrew libraries and toolchain.
- [noclip.website](https://github.com/magcius/noclip.website) by **Jasper (magcius)** — Model and format parsing infrastructure.
- [gclib](https://github.com/LagoLunatic/gclib) by **LagoLunatic** — GameCube / Wii filesystem and archive extraction.
- [ogws](https://github.com/doldecomp/ogws) — Reference for NW4R effect particle simulation.
