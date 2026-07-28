#!/usr/bin/env python3
"""Smoke test for the thermal printer driver.

    python3 test_printer.py                 # logic only, no hardware needed
    python3 test_printer.py /dev/ttyAMA0    # also print a real page

The logic checks run anywhere: they swap in a fake serial port and inspect the
bytes the driver *would* have sent. That matters more than it looks. The bitmap
path has broken twice, and both times the symptom was the printer silently
emitting kanji instead of an image -- a failure you can only see on paper, on a
device, with paper loaded. These assertions catch the same breakage on a laptop.

Guarded here:
  - chunk headers are DC2 * <rows> 48
  - no chunk exceeds the command-buffer row cap
  - chunk bodies are exactly 48*rows bytes
  - every row of the image is sent exactly once
  - bit packing: black pixel -> set bit, MSB first
  - narrow images are padded to 384px, not stretched
  - width > 384 raises instead of failing obscurely

No framework on purpose -- plain asserts, one file, runs with bare python3.
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib" / "ext"))


class FakeSerial:
    """Stand-in for serial.Serial that records everything written to it."""

    def __init__(self, *args, **kwargs):
        self.writes = []

    def write(self, data):
        self.writes.append(bytes(data))

    def flush(self):
        pass

    def inWaiting(self):
        return 0

    def read(self):
        return b"\x00"


def load_driver():
    """Import printer.py with pyserial stubbed, so this runs without hardware."""
    try:
        import serial  # noqa: F401
    except ImportError:
        stub = types.ModuleType("serial")
        stub.Serial = FakeSerial
        sys.modules["serial"] = stub

    import printer as printer_mod
    printer_mod.Serial = FakeSerial
    printer_mod.sleep = lambda *_: None      # skip the burn-time pacing delays
    return printer_mod


def new_printer(mod):
    p = mod.ThermalPrinter(serialport="fake")
    p.printer.writes.clear()                 # drop the __init__ setup bytes
    return p


# --- the checks ------------------------------------------------------------

def check_padding(mod):
    """A narrow image is padded with white to 384, keeping pixels left-aligned."""
    p = new_printer(mod)
    w, h = 3, 2
    bits = p.convert_pixel_array_to_binary([0] * (w * h), w, h)
    assert len(bits) == 384 * h, "expected %d bits, got %d" % (384 * h, len(bits))
    for row in range(h):
        assert bits[row * 384:row * 384 + w] == [0, 0, 0], "row %d not black" % row
        assert set(bits[row * 384 + w:(row + 1) * 384]) == {1}, "row %d pad not white" % row


def check_threshold(mod):
    """Dark pixels become 0 (burn), light pixels 1 (leave paper)."""
    p = new_printer(mod)
    bits = p.convert_pixel_array_to_binary([0, 255, 47, 48], 4, 1)
    assert bits[:4] == [0, 1, 0, 1], bits[:4]


def check_too_wide_raises(mod):
    """w > 384 must name itself, not throw TypeError on a subscript later."""
    p = new_printer(mod)
    try:
        p.convert_pixel_array_to_binary([0] * 385, 385, 1)
    except ValueError as e:
        assert "385" in str(e), "error should name the offending width: %s" % e
        return
    raise AssertionError("expected ValueError for width 385")


def check_bad_pixel_type_raises(mod):
    p = new_printer(mod)
    try:
        p.convert_pixel_array_to_binary(["nope"], 1, 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unsupported pixel type")


def check_chunking(mod):
    """Chunk framing is the thing that broke before. Verify it byte by byte."""
    p = new_printer(mod)
    h = 8                                     # deliberately not a multiple of 3
    p.print_bitmap([0] * (384 * h), 384, h)

    writes = p.printer.writes
    assert writes[0] == b"\n", "print_bitmap should linefeed first, got %r" % writes[0]
    chunks = writes[1:]
    assert chunks, "no bitmap chunks were written"

    total_rows = 0
    for i, c in enumerate(chunks):
        assert c[0] == 18 and c[1] == 42, "chunk %d bad header %r" % (i, c[:2])
        rows, width_bytes = c[2], c[3]
        assert width_bytes == 48, "chunk %d width should be 48 bytes, got %d" % (i, width_bytes)
        assert rows > 0, "chunk %d claims %d rows" % (i, rows)
        # The real ceiling: header + body must fit the printer's ~255B buffer.
        # floor((255-4)/48) = 5 rows. Exceeding it drops the printer out of
        # bitmap mode mid-stream and the next header prints as kanji.
        assert rows * 48 <= 255 - 4, \
            "chunk %d has %d rows (%dB) - overflows the ~255B buffer" % (i, rows, rows * 48)
        assert len(c) == 4 + rows * 48, \
            "chunk %d body is %d bytes, header claims %d rows" % (i, len(c) - 4, rows)
        total_rows += rows

    assert total_rows == h, "sent %d rows, image has %d" % (total_rows, h)


def check_bit_packing(mod):
    """All-black -> 0xFF bytes. All-white -> 0x00. MSB is the leftmost pixel."""
    p = new_printer(mod)
    p.print_bitmap([0] * 384, 384, 1)
    body = p.printer.writes[1][4:]
    assert set(body) == {0xFF}, "all-black row should pack to 0xFF, got %r" % sorted(set(body))

    p = new_printer(mod)
    p.print_bitmap([255] * 384, 384, 1)
    body = p.printer.writes[1][4:]
    assert set(body) == {0x00}, "all-white row should pack to 0x00, got %r" % sorted(set(body))

    p = new_printer(mod)
    row = [0] + [255] * 383                   # only the leftmost pixel is black
    p.print_bitmap(row, 384, 1)
    body = p.printer.writes[1][4:]
    assert body[0] == 0x80, "leftmost pixel should be the MSB, got 0x%02X" % body[0]


def hardware_smoke(mod, port):
    """Optional: actually print. Needs a printer, paper, and the right port."""
    from PIL import Image
    print("  opening %s ..." % port)
    p = mod.ThermalPrinter(serialport=port)
    p.justify("C")
    p.print_text("thermal-cam self test\n")
    p.justify("L")

    img = Image.new("L", (384, 60), 255)
    for x in range(384):                      # a gradient shows heat problems clearly
        for y in range(60):
            img.putpixel((x, y), int(255 * x / 383))
    bw = img.convert("1")
    p.print_bitmap(list(bw.getdata()), *bw.size)
    p.linefeed(3)
    print("  printed a gradient strip - check for banding or faint rows")


def main():
    mod = load_driver()
    # Real pyserial gets swapped for FakeSerial above; say so, so a pass here is
    # never mistaken for "the hardware works".
    print("thermal-cam printer driver tests (no hardware)")

    checks = [
        ("padding to 384px", check_padding),
        ("black/white threshold", check_threshold),
        ("width > 384 raises", check_too_wide_raises),
        ("bad pixel type raises", check_bad_pixel_type_raises),
        ("chunk framing", check_chunking),
        ("bit packing", check_bit_packing),
    ]

    failed = 0
    for name, fn in checks:
        try:
            fn(mod)
            print("  PASS  %s" % name)
        except AssertionError as e:
            failed += 1
            print("  FAIL  %s\n          %s" % (name, e))

    if len(sys.argv) > 1:
        print("\nhardware smoke test on %s" % sys.argv[1])
        try:
            hardware_smoke(mod, sys.argv[1])
        except Exception as e:
            failed += 1
            print("  FAIL  hardware: %s" % e)

    print("\n%d/%d passed" % (len(checks) - failed, len(checks)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
