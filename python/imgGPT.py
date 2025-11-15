#!/usr/bin/env python3
from escpos.printer import Serial
from PIL import Image, ImageOps, ImageFilter
import time

# ---------- CONFIG ----------
PRINTER_PORT = '/dev/ttyAMA0'    # or '/dev/serial0' or '/dev/ttyS0'
BAUDRATE = 9600                 # try 19200; many 58mm clones are fine with it
MAX_W = 384                      # typical width for 58mm heads @ 203dpi
FRAGMENT_H = 1024                # slice height to avoid buffer overflows
ROTATE_DEG = 90                  # 0 or 90 depending on your mech
TEXT_AFTER = "lol\n"
USE_IMPL = "graphics"            # try "graphics" first; fall back to "bitImageRaster"
ENABLE_XONXOFF = True            # helps avoid underruns on some clones
# ----------------------------

def prep_for_printer(img: Image.Image) -> Image.Image:
    """
    Rotate, scale to MAX_W (always), apply tone curve, and convert to 1-bit with dithering.
    """
    if ROTATE_DEG:
        img = img.rotate(ROTATE_DEG, expand=True)

    # 1) Work in grayscale
    img = img.convert("L")

    # 2) Scale to printer width (always fill width for best dot usage)
    w, h = img.size
    nh = int(h * (MAX_W / float(w)))
    img = img.resize((MAX_W, nh), Image.LANCZOS)

    # 3) Tone curve for thermal: modest autocontrast + gamma < 1 (darken mids)
    img = ImageOps.autocontrast(img, cutoff=2)  # trims 2% tails
    gamma = 0.80                                # 0.7–0.9 often looks great
    img = img.point(lambda p: int((p / 255.0) ** gamma * 255))

    # Optional crisping helps dithers: mild unsharp mask
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=2))

    # 4) Dither to 1-bit
    img = img.convert("1", dither=Image.FLOYDSTEINBERG)

    return img

def print_pil_image(img_1bit: Image.Image):
    p = Serial(
        devfile=PRINTER_PORT,
        baudrate=BAUDRATE,
        bytesize=8, parity='N', stopbits=1, timeout=1,
        dsrdtr=False, rtscts=False, xonxoff=ENABLE_XONXOFF,
        encoding='cp437'
    )
    try:
        p.hw('init')  # ESC @
        p.text("Camera print test (58mm)\n\n")

        # Print via preferred impl
        p.image(
            img_1bit,
            impl=USE_IMPL,                       # "graphics" or "bitImageRaster"
            high_density_horizontal=True,
            high_density_vertical=True,
            fragment_height=FRAGMENT_H
        )

        if TEXT_AFTER:
            p.text("\n" + TEXT_AFTER)

        # If your unit supports smoothing toggle and it's washing out the dither:
        # p._raw(b'\x1D\x62\x00')  # GS b 0  -> smoothing OFF on some clones
        # p._raw(b'\x1D\x62\x01')  # GS b 1  -> smoothing ON  (model-dependent)

    finally:
        p.close()

def main():
    # Live capture path (kept for reference)
    # img = capture_to_pil()
    # img1 = prep_for_printer(img)
    # img1.save("debug_after.png")  # optional
    # print_pil_image(img1)

    # Sandbox: ALWAYS preprocess the file you load
    im = Image.open("/home/evren/repos/thermal-cam/python/pics/20251026-131731_before.png")
    im1 = prep_for_printer(im)         # <-- do not skip this step
    print_pil_image(im1)
    print("Done: captured + printed.")

if __name__ == "__main__":
    main()
