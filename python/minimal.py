from escpos.printer import Serial
import time

PRINTER_PORT = '/dev/ttyUSB2'  # Ensure this is the correct port
BAUDRATE = 9600

try:
    # Initialize the printer
    printer = Serial(devfile=PRINTER_PORT, baudrate=BAUDRATE, encoding='cp437')  # Using 'cp437' as default

    # Reset the printer to default settings
    printer._raw(b'\x1B\x40')  # ESC @

    # Simple print command
    printer.text("BRUH\n")
    time.sleep(1)
    printer.text("lol\n")
    time.sleep(1)
    printer.text("meow meow")
    time.sleep(1)
    printer.text("meow meow \n")
    time.sleep(1)
    printer.text("meow meow meow meow\n")
    time.sleep(1)
    printer.text("lol\n")
    time.sleep(1)

    #
    # printer.cut()

    print("Test print completed successfully!")

    printer.close()

except Exception as e:
    print(f"Error: {e}")
