# Current engineering state — 2026-07-30

## Start here

Thermal Cam is a Raspberry Pi camera that previews on a 2.7-inch e-ink panel
and prints a 384-pixel-wide photograph on 58 mm thermal paper.

**Hosted:**

- [Project dashboard](https://evrenucar.github.io/thermal-cam/)
- [Browser emulator](https://evrenucar.github.io/thermal-cam/emulator.html)
- [Detailed status](https://evrenucar.github.io/thermal-cam/status.html)
- [Public repository](https://github.com/evrenucar/thermal-cam)

The public repository is the active source and GitHub Pages serves `docs/` from
`master`. New work should happen on a feature branch and merge into `master`
after tests pass.

## What works

- Camera capture → e-ink preview → save → thermal print on Raspberry Pi 5.
- ESC/POS bitmap printing at 9600 baud with chunk-size and heat pacing guards.
- Six hardware-free printer driver regression checks in `pi/test_printer.py`.
- Hosted emulator with live view, image upload, webcam input, rotation, crop,
  d-pad controls, print animation, capture library and fault injection.
- Browser Floyd–Steinberg dithering is isolated in `docs/dither.js`; parity tests
  compare fixed grayscale patterns against Pillow's device pipeline.
- Responsive project dashboard links the emulator, key files, current work,
  hardware stack and roadmap.
- ESP32 build artifacts are ignored and no longer tracked.

## Current development focus

1. Collect feedback on the hosted dashboard and emulator.
2. Decide how to reduce the roughly 56-second print duration. About 26.3 seconds
   is serial transfer alone at 9600 baud; speed changes require paper tests.
3. Exercise the proposed d-pad control model in emulator focus mode.
4. Build the mobile plywood development rig with every wire reachable.

`docs/status.json` is the concise machine-readable task snapshot used by both
hosted status views.

## Hardware work still required

### Zero 2W serial path

Bluetooth and WiFi must remain available. Test the mini-UART with a pinned core
clock first and retain USB-serial as the fallback. Do not use
`dtoverlay=disable-bt` as the product solution.

### Print speed and density

Do not raise baud or alter heat timing based only on the emulator. The bitmap
path has previously failed as kanji output when serial data was corrupted, and
power sag can resemble a software print-density bug. Validate signal integrity,
density and printer temperature on real paper.

### Power

The internal LiPo and protection/charger path must comfortably sustain roughly
1.5–2 A printer burn peaks without voltage sag.

## Known software debt

- `pi/main.py` captures and dithers faster than the e-ink panel can refresh. It
  wastes a core on Pi 5 and may consume the Zero 2W's practical CPU budget.
- High-resolution originals are retained for future crop/reposition editing,
  but the device UI for that flow does not exist yet.
- `pi/lib/int/ui.py` is still an empty stub; the hosted d-pad interaction has not
  been moved onto the device.
- The emulator and Pillow parity tests currently cover deterministic grayscale
  patterns, not the complete rotate/resize/crop pipeline.

## Commands

```bash
# All hardware-free checks
python3 -m unittest discover -s tests -v
python3 pi/test_printer.py

# Local hosted pages
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

For printer-driver invariants and paths that should not be touched, read
`CLAUDE.md` before editing device code.
