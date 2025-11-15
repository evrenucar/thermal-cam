#!/usr/bin/env python3
from escpos.printer import Serial
from PIL import Image
import time, os, subprocess, tempfile, sys

# ---------- CONFIG ----------
PRINTER_PORT = '/dev/ttyAMA0'    # or '/dev/serial0' or '/dev/ttyS0'
BAUDRATE = 9600                  # match your working value (try 19200 if needed)
MAX_W = 384                      # typical max printable width for 58mm heads
FRAGMENT_H = 1024                 # slice height to avoid buffer overflows
ROTATE_DEG = 90                   # set 90 if your print is sideways
TEXT_AFTER = "lol\n"             # change or remove
# ----------------------------

def capture_to_pil():
    """
    Try Picamera2 first (preferred). If unavailable, fall back to libcamera-jpeg CLI.
    Returns a PIL.Image in RGB.
    """
    
    from picamera2 import Picamera2
    import numpy as np
    picam2 = Picamera2()
    # 1640x1232 is a good default on many sensors; adjust if you like
    config = picam2.create_still_configuration(main={"size": (1640, 1232)})
    picam2.configure(config)
    picam2.start()
    # let auto-exposure settle a bit
    time.sleep(2)
    arr = picam2.capture_array()  # numpy array (H, W, 3)
    picam2.stop()
    return Image.fromarray(arr, mode="RGB")

from PIL import Image

def prep_for_printer(img: Image.Image) -> Image.Image:
    """
    Rotate, resize to MAX_W (keeping aspect), and convert to 1-bit with dithering.
    """
    if ROTATE_DEG:
        img = img.rotate(ROTATE_DEG, expand=True)

    # Resize to fit width
    w, h = img.size
    if w > MAX_W:
        nh = int(h * (MAX_W / float(w)))
        img = img.resize((MAX_W, nh), Image.LANCZOS)

    # Convert to 1-bit with Floyd–Steinberg dithering
    img = img.convert("1", dither=Image.FLOYDSTEINBERG)

    return img


def print_pil_image(img_1bit: Image.Image):
    p = Serial(
        devfile=PRINTER_PORT,
        baudrate=BAUDRATE,
        bytesize=8, parity='N', stopbits=1, timeout=1,
        dsrdtr=False, rtscts=False, xonxoff=False,
        encoding='cp437'
    )
    try:
        p.hw('init')  # ESC @
        # Optional: quick header to confirm serial is clean
        p.set_sleep_in_fragment()
        p.text("Camera print test (58mm)\n\n")

        # Stream the image in fragments to avoid buffer issues on tiny printers
        # python-escpos will handle slicing if we pass fragment_height.
        p.image(
            img_1bit,
            impl="bitImageRaster",
            high_density_horizontal=True,
            high_density_vertical=True,
            fragment_height=1028
        )

        if TEXT_AFTER:
            p.text("\n" + TEXT_AFTER)

        # Many 58mm units have no cutter
        # p.cut()
    finally:
        p.close()

def main():
    # timestring = time.strftime("%Y%m%d-%H%M%S")
    # img = capture_to_pil()
    # img.save(f"pics/{timestring}_before.png") 
    # img1 = prep_for_printer(img)
    # img1.save(f"pics/{timestring}_after.png")  # for debugging
    # print_pil_image(img1)
    


    # sandbox
    #
    #

    im = Image.open(f"/home/evren/repos/thermal-cam/python/pics/20251026-131731_after.png")
    print_pil_image(im)
    #
    #
    #
    print("Done: captured + printed.")

if __name__ == "__main__":
    main()


#
                # data = list(i.getdata())
                # w, h = i.size
                # p.print_bitmap(data, w, h)