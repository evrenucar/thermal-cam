# thermal-cam

Raspberry Pi 5 device that captures camera images, shows them on a Waveshare 2.7" e-ink display, and prints them on a 58mm thermal printer. Four GPIO buttons drive it.

## Map

```
thermal-cam/
├── pi/                # production code (this is what runs on the device)
│   ├── main.py            # entry point: ThermalCamera class, 3 threads, GPIO
│   ├── test_printer.py    # standalone printer test (text + bitmap)
│   ├── lib/int/
│   │   ├── config.py      # all hardware constants (pins, baud, sizes)
│   │   └── ui.py          # empty stub
│   └── lib/ext/
│       ├── printer.py     # ESC/POS thermal printer driver
│       ├── epd2in7_V2.py  # Waveshare e-ink driver
│       └── epdconfig.py   # GPIO/SPI hardware abstraction
├── arduino/           # earlier prototypes
│   ├── DUPA_bitmap_printing/  # working bitmap-print reference (TPrinter.cpp)
│   └── ThermalPrinter/        # upstream lib (BinaryWorlds)
├── esp-idf/           # ESP32 trial
├── python/            # experimental scripts (python-escpos based)
└── resources/         # printer datasheet PDF + MCU demo code
```

## Hardware

- Raspberry Pi 5
- Waveshare 2.7" e-ink (264×176, SPI)
- 58mm thermal printer (ESC/POS, **9600 baud**, /dev/ttyAMA0)
- Pi Camera (Picamera2)
- 4 GPIO buttons: 5=capture, 13=print, 6=menu (unused), 19=exit

## Run

```bash
cd pi
python3 main.py            # full app
python3 test_printer.py    # printer-only smoke test
```

## What works

- Camera capture → e-ink display → save to disk
- Text printing
- Bitmap printing (after the fixes below)
- GPIO buttons for capture / print / exit

## What doesn't / known issues

- `lib/int/ui.py` is empty — menu button (GPIO 6) does nothing
- Print contrast is uneven on dense areas (faint rows in mid-tones); needs heat tuning in `config.py` (`PRINTER_HEAT_TIME`, `PRINTER_HEATING_DOTS`, `PRINTER_HEAT_INTERVAL`)
- `python/img.py` and `python/imgGPT.py` have hardcoded `/home/evren/...` paths; reference only

## Notes for future-me on the printer

The driver in `pi/lib/ext/printer.py` is ported from Adafruit/Ladyada's library. Two non-obvious gotchas tripped us up:

1. **Baud rate is 9600, not 19200.** The original library default was 19200, which corrupts every byte → bitmap data trips the printer's default kanji mode → prints Chinese characters instead of the image.
2. **Bitmap chunks must be ≤ 5 rows.** The printer's command buffer is ~255 bytes. A 384-px row is 48 bytes, so `floor(255/48) = 5` rows per `DC2 *` command. Sending more makes the printer drop out of bitmap mode mid-stream and print the next chunk's header bytes (`*`, `0`) as text.

The Arduino reference at `arduino/DUPA_bitmap_printing/TPrinter.cpp` gets both right — see `printBitmap()` and the `printerBufferLimit` constant.

## Tests

There's no test framework. `pi/test_printer.py` is a manual smoke test — opens the printer, prints a line of text and a real captured photo, and exits. Run it after any change to `printer.py`.
