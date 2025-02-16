from escpos.printer import Serial
import time

PRINTER_PORT = '/dev/ttyUSB0'  # Change to match your environment
BAUDRATE = 9600

try:
    # Initialize the printer
    printer = Serial(
        devfile=PRINTER_PORT,
        baudrate=BAUDRATE,
        encoding='cp437'
    )

    # Reset printer
    printer._raw(b'\x1B\x40')  # ESC @
    time.sleep(0.5)

    # Print "BRUH"
    printer.text("BRUH\n")
    time.sleep(1)

    # ----------------------------------------------------
    # INSERT THE NEW PRINT ROUTINE (replacing the comment)
    # ----------------------------------------------------
    # This replicates:
    #   Thermal.write(18);  // DC2
    #   Thermal.write(86);  // 'V'
    #   Thermal.write(50);  // nL=50 (decimal)
    #   Thermal.write(0);   // nH=0
    #
    # Then 50 rows, each containing 48 bytes of 0xAA
    # Finally two line feeds.

    # Optional: let the user know in text.
    printer.text("Print bitmap image\n")

    # Send DC2, 'V', 50, and 0
    printer._raw(b'\x12')   # 0x12 = DC2
    printer._raw(b'\x56')   # 0x56 = 'V'
    printer._raw(b'\x32')   # Decimal 50 (0x32)
    printer._raw(b'\x00')   # 0

    # Now send 50 rows, each containing 48 bytes of 0xAA
    for _ in range(50):
        printer._raw(b'\xAA' * 48)  # 0xAA repeated 48 times

    # Paper feed x2 (two line feeds)
    printer._raw(b'\x0A\x0A')

    printer.text("Print bitmap done\n")

    # ----------------------------------------------------
    # You can continue the script here as desired
    # ----------------------------------------------------
    
    # Print "lol" after the bitmap (optional)
    printer.text("lol\n")
    time.sleep(1)

    print("Test print (with custom bitmap) completed successfully!")

    # Optional: Cut the paper
    # printer.cut()

    printer.close()

except Exception as e:
    print(f"Error: {e}")
