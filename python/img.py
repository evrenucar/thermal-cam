from escpos.printer import Serial
import time

PRINTER_PORT = '/dev/ttyAMA0'  # Change to match your environment
BAUDRATE = 9600

try:
    # Initialize the printer
    printer = Serial(
        devfile=PRINTER_PORT,
        baudrate=BAUDRATE,
        encoding='cp437'
    )

    # ----------------------------------------------------
    # You can continue the script here as desired
    # ----------------------------------------------------
    

    printer._raw(b'\x1B\x40')  # ESC @


    printer.image("/home/evren/Desktop/ninja.bmp", impl="bitImageColumn", fragment_height=200)

    # Print "lol" after the bitmap (optional)
    printer.text("lol\n")
    time.sleep(1)

    print("Test print (with custom bitmap) completed successfully!")

    # Optional: Cut the paper
    # printer.cut()

    printer.close()

except Exception as e:
    print(f"Error: {e}")
