#!/usr/bin/env python3
# coding: utf-8

from serial import Serial as PySerial
from struct import unpack
from time import sleep

class ThermalPrinter:
    """
    Minimal thermal printer driver for 58mm ESC/POS-like panels.

    Python 3 port of an older script:
    - Proper bytes (no implicit str->bytes)
    - Integer division fixes
    - range() instead of xrange()
    - Removed duplicate method names
    - Explicit codepage selection to avoid CJK/“Chinese” text
    """

    SERIALPORT = '/dev/ttyAMA0'   # Adjust for your device
    BAUDRATE = 19200
    TIMEOUT = 3

    # thresholds for image -> 1bpp
    black_threshold = 48     # lower => darker
    alpha_threshold = 127

    encoding = 'cp437'       # python-side encoding
    codepage_id = 0          # ESC t 0 = CP437 on most clones

    def __init__(self, heatTime=80, heatInterval=2, heatingDots=7, serialport=None):
        port = serialport or self.SERIALPORT
        self.printer = PySerial(port, self.BAUDRATE, timeout=self.TIMEOUT)

        # Hard reset / init
        self._w(b'\x1b@')  # ESC @

        # --- Heating configuration (ESC 7 n1 n2 n3) ---
        # n1: heating dots (8*(n1+1)), n2: heating time(10us), n3: heating interval(10us)
        self._w(b'\x1b7' + bytes([heatingDots, heatTime, heatInterval]))

        # --- Density / break time (DC2 '#' n) ---
        # D4..D0 = density step (0..31), D7..D5 = break time (0..7), unit 250us
        printDensity = 15   # 0..31  (50% + 5%*n)
        printBreakTime = 15 # 0..7   (n*250us)  (some clones accept 0..31; old code used <<4|, so keep it)
        self._w(b'\x12#' + bytes([(printDensity << 4) | (printBreakTime & 0x0F)]))

        # --- Make sure we’re NOT in Kanji/CJK mode & select Latin code page ---
        # FS . = cancel Kanji; ESC R 0 = USA; ESC t n = code page
        self._w(b'\x1C\x2E')          # FS .
        self._w(b'\x1bR\x00')         # ESC R 0
        self.set_codepage(0, 'cp437') # ESC t 0 + Python encoding

    # ---------------- Core helpers ----------------
    def _w(self, data: bytes):
        self.printer.write(data)

    def reset(self):
        self._w(b'\x1b@')

    # ---------------- Status / power ----------------
    def offline(self):
        self._w(b'\x1b=' + b'\x00')

    def online(self):
        self._w(b'\x1b=' + b'\x01')

    def sleep(self):
        self.sleep_after(1)

    def sleep_after(self, seconds):
        if seconds:
            sleep(seconds)
            self._w(b'\x1b8' + seconds.to_bytes(2, 'little', signed=False))

    def wake(self):
        self._w(b'\xff')
        sleep(0.05)
        self._w(b'\x1b8\x00\x00')

    def has_paper(self) -> bool:
        # ESC v 0 — many clones return a single status byte
        self._w(b'\x1bv\x00')
        status = -1
        for _ in range(9):
            if self.printer.in_waiting:
                status = unpack('b', self.printer.read(1))[0]
                break
            sleep(0.01)
        # bit 2 (0x04) typically “paper out” on many mechanisms
        return not bool(status & 0x04) if status >= 0 else True

    # ---------------- Text ----------------
    def set_codepage(self, esc_t_value: int, py_encoding: str):
        """Set printer code page (ESC t n) and Python-side encoding to match."""
        self.codepage_id = esc_t_value
        self.encoding = py_encoding
        self._w(b'\x1bt' + bytes([esc_t_value]))

    def linefeed(self, number=1):
        self._w(b'\n' * max(1, int(number)))

    def justify(self, align="L"):
        # ESC a n: 0 left, 1 center, 2 right
        pos = 0 if align.upper() == "L" else 1 if align.upper() == "C" else 2
        self._w(b'\x1ba' + bytes([pos]))

    def bold(self, on=True):
        self._w(b'\x1bE' + (b'\x01' if on else b'\x00'))

    def font_b(self, on=True):
        # ESC ! n — bit0 toggles font A/B on most clones
        self._w(b'\x1b!' + (b'\x01' if on else b'\x00'))

    def underline(self, on=True):
        # ESC - n : 1=1dot, 2=2dots
        self._w(b'\x1b-' + (b'\x01' if on else b'\x00'))

    def inverse(self, on=True):
        self._w(b'\x1dB' + (b'\x01' if on else b'\x00'))

    def upsidedown(self, on=True):
        self._w(b'\x1b{' + (b'\x01' if on else b'\x00'))

    def print_text(self, msg: str, chars_per_line: int = None):
        data = msg.encode(self.encoding, errors='replace')
        if not chars_per_line:
            self._w(data)
            sleep(0.2)
        else:
            # naive wrap by fixed width
            out = []
            col = 0
            for ch in msg:
                out.append(ch)
                col += 1
                if ch == '\n':
                    col = 0
                elif col >= chars_per_line:
                    out.append('\n')
                    col = 0
            self._w(''.join(out).encode(self.encoding, errors='replace'))
            sleep(0.2)

    def print_markup(self, markup: str):
        lines = markup.splitlines(True)
        for l in lines:
            if len(l) < 3:
                self.print_text(l)
                continue
            style = l[0]
            justification = l[1].upper()
            text = l[3:]

            if style == 'b':
                self.bold()
            elif style == 'u':
                self.underline()
            elif style == 'i':
                self.inverse()
            elif style == 'f':
                self.font_b()

            self.justify(justification)
            self.print_text(text)
            if justification != 'L':
                self.justify("L")

            if style == 'b':
                self.bold(False)
            elif style == 'u':
                self.underline(False)
            elif style == 'i':
                self.inverse(False)
            elif style == 'f':
                self.font_b(False)

    # ---------------- Barcodes (basic) ----------------
    def set_barcode_text_position(self, pos: int):
        # GS H n (0 none, 1 above, 2 below, 3 both)
        self._w(b'\x1dH' + bytes([pos & 0x03]))

    def set_barcode_height(self, height: int):
        # GS h n  (1..255)
        self._w(b'\x1dh' + bytes([max(1, min(255, height))]))

    def set_barcode_width(self, module_w: int = 2):
        # GS w n  (2..6 typical)
        module_w = max(2, min(6, int(module_w)))
        self._w(b'\x1dw' + bytes([module_w]))

    def barcode(self, data: str, symbology: int = 65):
        """
        Print a barcode.
        symbology: 65=UPC-A, 66=UPC-E, 67=EAN13, 68=EAN8, 69=CODE39, 70=I25, 71=CODEBAR,
                   72=CODE93, 73=CODE128, 74=CODE11, 75=MSI
        """
        enc = data.encode(self.encoding, errors='ignore')
        self._w(b'\x1dk' + bytes([symbology]) + bytes([len(enc)]) + enc)

    # ---------------- Images ----------------
    def convert_pixel_array_to_binary(self, pixels, w, h):
        """
        Convert pixels -> 1bpp list (0=black,1=white), padded to 384 columns.
        pixels: list of 0..255 (L), or (R,G,B), or (R,G,B,A)
        """
        target_w = 384
        if w > target_w:
            print(f"Bitmap width too large: {w}. Needs to be <= {target_w}")
            return False
        if w < target_w:
            print(f"Bitmap under {target_w} ({w}), padding with white")

        bw = [1] * (target_w * h)

        # helper to write into padded row
        def put(i_src, val):
            row = i_src // w
            col = i_src % w
            idx = col + row * target_w
            bw[idx] = 0 if val else 1  # 0=black,1=white in original logic

        first = pixels[0]
        if isinstance(first, int):  # L
            for i, p in enumerate(pixels):
                put(i, 1 if p < self.black_threshold else 0)
        elif isinstance(first, (tuple, list)) and len(first) == 3:  # RGB
            for i, p in enumerate(pixels):
                lum = (p[0] + p[1] + p[2]) / 3.0
                put(i, 1 if lum < self.black_threshold else 0)
        elif isinstance(first, (tuple, list)) and len(first) == 4:  # RGBA
            for i, p in enumerate(pixels):
                lum = (p[0] + p[1] + p[2]) / 3.0
                put(i, 1 if (lum < self.black_threshold and p[3] > self.alpha_threshold) else 0)
        else:
            print("Unsupported pixel format. Use L, RGB or RGBA.")
            return False

        return bw

    def print_bitmap(self, pixels, w, h, output_png=False):
        """
        Print a bitmap using legacy column mode (ESC * + DC2 '*').
        Best if the image width is 384 px. For photos, consider pre-dithering.
        """
        from math import ceil

        if output_png:
            from PIL import Image, ImageDraw
            test_img = Image.new('RGB', (384, h), (255, 255, 255))
            draw = ImageDraw.Draw(test_img)

        self.linefeed()

        bw = self.convert_pixel_array_to_binary(pixels, w, h)
        if bw is False:
            return

        print_bytes = bytearray()
        counter = 0
        target_w = 384
        bytes_per_row = target_w // 8  # 48

        # Send in stripes to avoid huge buffers: up to 255 rows per block
        for row_start in range(0, h, 255):
            chunk_h = min(255, h - row_start)
            # DC2 '*' m n : some clones use 0x12 0x2A chunk_h 0x30
            print_bytes += bytes((0x12, 0x2A, chunk_h, 0x30))
            for i in range(bytes_per_row * chunk_h):
                b = 0
                for bit in range(8):
                    # map counter to bw index
                    val = bw[counter]
                    counter += 1
                    if val == 0:            # black pixel
                        b |= (1 << (7 - bit))
                        if output_png:
                            x = (counter % target_w)
                            y = (counter // target_w)
                            draw.point((x, y), fill=(0, 0, 0))
                    else:
                        if output_png:
                            x = (counter % target_w)
                            y = (counter // target_w)
                            draw.point((x, y), fill=(255, 255, 255))
                print_bytes.append(b)

        # write out
        self._w(print_bytes)

        if output_png:
            with open('print-output.png', 'wb') as f:
                test_img.save(f, 'PNG')
            print("Output saved to print-output.png")

# ---------------- Demo / CLI ----------------
if __name__ == '__main__':
    import sys, os
    from PIL import Image

    if len(sys.argv) == 2:
        serialport = sys.argv[1]
    else:
        serialport = ThermalPrinter.SERIALPORT

    if not os.path.exists(serialport):
        sys.exit(f"ERROR: Serial port not found at: {serialport}")

    print(f"Testing printer on port {serialport}")
    p = ThermalPrinter(serialport=serialport)

    # Text tests
    p.print_text("\nHello maailma. How's it going?\n")
    p.print_text("Part of this ")
    p.bold(True)
    p.print_text("line is bold\n")
    p.bold(False)
    p.print_text("Part of this ")
    p.font_b(True)
    p.print_text("line is fontB\n")
    p.font_b(False)

    p.justify("R"); p.print_text("right justified\n")
    p.justify("C"); p.print_text("centered\n")
    p.justify("L"); p.print_text("left justified\n")
    p.upsidedown(True);  p.print_text("upside down\n"); p.upsidedown(False)

    markup = """bl bold left
ur underline right
fc font b centred (next line blank)
nl
il inverse left
"""
    p.print_markup(markup)

    # Image test (expects example-lammas.png in CWD)
    try:
        img = Image.open("example-lammas.png")
        data = list(img.getdata())
        w, h = img.size
        p.print_bitmap(data, w, h, output_png=True)
    except FileNotFoundError:
        p.print_text("\n(example-lammas.png not found; skipping image test)\n")

    p.set_barcode_text_position(2)  # below
    p.set_barcode_height(60)
    p.set_barcode_width(2)
    p.barcode("014633098808", symbology=65)  # UPC-A
    p.linefeed(3)
