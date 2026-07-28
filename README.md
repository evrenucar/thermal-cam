# thermal-cam

A camera that prints. Point, shoot, and a thermal-paper photo comes out. No
screen to review on, no phone, no app — the paper is the photo.

**Where this is going:** a compact handheld on a **Raspberry Pi Zero 2W**.
**Where it is now:** a **Raspberry Pi 5** on the bench, because that's what we
have and it makes development faster. See [docs/PRODUCT.md](docs/PRODUCT.md) for
the direction, the roadmap, and the gap between those two boards.

Captures from a Pi Camera, shows the result on a Waveshare 2.7" e-ink panel, and
prints it on a 58mm thermal printer. Four GPIO buttons drive it.

## Map

```
thermal-cam/
├── pi/                # production code (this is what runs on the device)
│   ├── main.py            # entry point: ThermalCamera class, 2 worker threads, GPIO
│   ├── test_printer.py    # driver tests, runs without hardware
│   ├── lib/int/
│   │   ├── config.py      # all hardware constants (pins, baud, sizes)
│   │   └── ui.py          # empty stub
│   └── lib/ext/
│       ├── printer.py     # ESC/POS thermal printer driver
│       ├── epd2in7_V2.py  # Waveshare e-ink driver
│       └── epdconfig.py   # GPIO/SPI hardware abstraction
├── docs/
│   └── PRODUCT.md     # product direction, target hardware, roadmap
├── tools/             # local review loop — serve.py + HTML pages
├── arduino/           # earlier prototypes
│   ├── DUPA_bitmap_printing/  # working bitmap-print reference (TPrinter.cpp)
│   └── ThermalPrinter/        # upstream lib (BinaryWorlds)
├── esp-idf/           # ESP32 trial
├── python/            # experimental scripts (python-escpos based)
└── resources/         # printer datasheet PDF + MCU demo code
```

## Hardware

- Raspberry Pi 5 (dev) → Raspberry Pi Zero 2W (target)
- Waveshare 2.7" e-ink (176×264 native, SPI)
- 58mm thermal printer (ESC/POS, **9600 baud**, /dev/ttyAMA0)
- Pi Camera (Picamera2)
- 4 GPIO buttons: 5=capture, 13=print, 6=menu (unused), 19=exit

## Run

```bash
cd pi
python3 main.py                        # full app, needs the hardware
python3 test_printer.py                # driver tests, no hardware needed
python3 test_printer.py /dev/ttyAMA0   # ...plus print a real gradient strip
```

```bash
python3 tools/serve.py     # review + grill pages at http://127.0.0.1:8765/
```

## What works

- Camera capture → e-ink display → save to disk
- Text printing
- Bitmap printing
- GPIO buttons for capture / print / exit

## Tests

`pi/test_printer.py`. Plain asserts, no framework, and it runs on a laptop — it
swaps in a fake serial port and inspects the bytes the driver *would* have sent.
That's the point: the bitmap path has broken twice, and both times the symptom
was kanji on paper instead of an image, which you can otherwise only see on a
device with paper loaded.

It guards chunk framing, the buffer row cap, bit packing and order, 384px
padding, and the width guard. Verified by mutation: raising `ROWS_PER_CHUNK`
past the buffer limit, reversing the bit shift, or corrupting the chunk header
each make it fail.

Run it after any change to `printer.py`.

## What doesn't / known issues

- `lib/int/ui.py` is empty — menu button (GPIO 6) does nothing
- Print contrast is uneven on dense areas (faint rows in mid-tones); needs heat
  tuning in `config.py` (`PRINTER_HEAT_TIME`, `PRINTER_HEATING_DOTS`,
  `PRINTER_HEAT_INTERVAL`)
- `python/img.py` and `python/imgGPT.py` have hardcoded `/home/evren/...` paths;
  reference only
- The capture loop spins with no sleep, burning a core to discard frames the
  e-ink can never display. Harmless on a Pi 5, probably fatal on a Zero 2W.

## Notes for future-me on the printer

The driver in `pi/lib/ext/printer.py` is ported from Adafruit/Ladyada's library.
Three non-obvious things tripped us up:

1. **Baud rate is 9600, not 19200.** The original library default was 19200,
   which corrupts every byte → bitmap data trips the printer's default kanji
   mode → prints Chinese characters instead of the image.
2. **Bitmap chunks must be ≤ 5 rows.** The printer's command buffer is ~255
   bytes. A 384-px row is 48 bytes, so `floor(255/48) = 5` rows per `DC2 *`
   command. Sending more makes the printer drop out of bitmap mode mid-stream
   and print the next chunk's header bytes (`*`, `0`) as text.
3. **Chunks need pacing.** Even at a legal chunk size, sending the next chunk
   faster than the head can burn the current one overflows the buffer with the
   same result. `print_bitmap` counts black bits per chunk, estimates burn time
   from the heat settings, and sleeps. It looks like a magic `sleep` and it
   isn't — it's calibration derived from the datasheet's heat model. Don't
   "simplify" it into a fixed delay.

The Arduino reference at `arduino/DUPA_bitmap_printing/TPrinter.cpp` gets all
three right — see `printBitmap()`, `printerBufferLimit` and `setDelayBitmap`.

## Review loop

`tools/` holds a local, stdlib-only server and a set of HTML pages for working
through design decisions and capturing the answers — including pasted images and
dropped files. See [tools/README.md](tools/README.md).

Open questions about product direction live in `tools/grill.html`.
