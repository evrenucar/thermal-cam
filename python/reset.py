from escpos.printer import Serial

PRINTER_PORT = '/dev/ttyUSB2'  # Ensure this is the correct port
BAUDRATE = 9600

try:
    # Initialize the printer
    printer = Serial(devfile=PRINTER_PORT, baudrate=BAUDRATE)

    # Reset the printer to default settings
    printer._raw(b'\x1B\x40')  # ESC @

  #  print("Printer reset successfully!")

    printer.close()

except Exception as e:
    print(f"Error: {e}")
