# thermal-cam

A camera that prints. Point, shoot, and a thermal-paper photo comes out.
Raspberry Pi + 2.7" e-ink + 58mm ESC/POS printer.

## Read this first

- **[docs/STATE.md](docs/STATE.md)** — where we left off, what's blocked, what's next.
- **[docs/PRODUCT.md](docs/PRODUCT.md)** — product direction and every decision made so far.

## The only code that ships

Nine files, all under `pi/`. This is what runs on the device:

```
pi/main.py              entry point: ThermalCamera, 2 worker threads, GPIO
pi/test_printer.py      the tests — run these, no hardware needed
pi/lib/int/config.py    every hardware constant (pins, baud, sizes)
pi/lib/int/ui.py        empty stub; GPIO 6 does nothing yet
pi/lib/ext/printer.py   ESC/POS driver — the only non-trivial logic here
pi/lib/ext/epd*.py      Waveshare e-ink driver (vendored, don't edit)
pi/lib/ext/epdconfig.py GPIO/SPI abstraction (vendored, don't edit)
```

Plus `docs/` (the site and the emulator) and `tools/` (the local review server).

## Ignore these — they are dead weight

**1,384 of the 1,464 tracked files are not worth reading.** Grep and glob will
surface them; they are noise.

| Path | What it is | Verdict |
|---|---|---|
| `arduino/esp32-trial/build/` | 1,338 ESP32 build artifacts | **Never read.** Contains a 5.3 MB `build.ninja` and a 4.4 MB `compile_commands.json` that will eat your context for nothing. |
| `arduino/ThermalPrinter/` | Upstream vendor lib + examples | Abandoned. Has 3 near-duplicate copies of `TPrinter.cpp`. |
| `esp-idf/` | ESP32 port attempt | Abandoned — it overheated. |
| `python/` | Early scripts, hardcoded `/home/evren/…` paths | Reference only, does not run. |
| `resources/` | Printer datasheet PDF + vendor demo code | Only open the PDF if you need a register-level answer. |

**The one exception worth reading:**
`arduino/DUPA_bitmap_printing/TPrinter.cpp` is the working reference
implementation for bitmap printing — see `printBitmap()`, `printerBufferLimit`
and `setDelayBitmap`. There are four files named `TPrinter.cpp` in this repo;
**this is the canonical one.** The others are stale copies.

## Gotchas that have already cost real time

The printer driver has broken twice, both times printing kanji instead of an
image, and both times only visible on paper. Before touching
`pi/lib/ext/printer.py`, know these:

1. **Baud is 9600, not 19200.** The upstream library default corrupts every
   byte, and corrupted bitmap data trips the printer's kanji mode.
2. **Bitmap chunks are capped at 3 rows.** The command buffer is ~255 bytes and
   a 384px row is 48 bytes, so 5 is the hard ceiling. Exceeding it drops the
   printer out of bitmap mode mid-stream.
3. **`print_bitmap` paces between chunks.** It counts black bits, estimates burn
   time from the heat settings, and sleeps. It looks like a magic `sleep` and it
   is not — it is calibration from the datasheet's heat model. **Do not
   "simplify" it into a fixed delay.**

Also: `DISPLAY_WIDTH=264, DISPLAY_HEIGHT=176` in `config.py` are the *landscape*
dimensions. The panel is natively 176×264 and `DISPLAY_ROTATION=90` swaps them
back. The names do not mean what they suggest.

## Tests

```bash
cd pi && python3 test_printer.py          # 6 checks, no hardware
cd pi && python3 test_printer.py /dev/ttyAMA0   # ...plus print a real strip
```

Plain asserts, no framework. It fakes the serial port and inspects the bytes the
driver would have sent. Run it after any change to `printer.py`.

## Emulator

`docs/emulator.html` runs the whole interface with no camera, Pi or printer —
live e-ink panel, paper strip, d-pad, fault injection. Live at
<https://evrenucar.github.io/thermal-cam/emulator.html>.

Its dithering mirrors PIL's Floyd–Steinberg through `docs/dither.js`.
`tests/test_dither_parity.py` compares fixed patterns against Pillow; extend that
test whenever the browser or device image pipeline changes.

## Repository and publishing

`origin` is the active public repository: `evrenucar/thermal-cam`. GitHub Pages
serves `docs/` from `master`. Develop on a focused feature branch, run the
hardware-free suites, then merge and verify the hosted URLs.

Work on a focused feature branch; do not commit new development directly to
`master`.
