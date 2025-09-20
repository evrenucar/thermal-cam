from escpos.printer import Serial

# Configure the serial connection to your printer
PRINTER_PORT = '/dev/ttyAMA0'
BAUDRATE = 9600  # Default for many ESC/POS printers

try:
    # Initialize the printer with the desired encoding
    printer = Serial(devfile=PRINTER_PORT, baudrate=BAUDRATE, encoding='cp1252')  # Use 'utf-8' if supported

    # Set the code page to CP1252
    # ESC t n: Select character code table
    # n=16 corresponds to CP1252 for many printers; verify with your printer's manual
    printer._raw(b'\x1B\x74\x10')  # ESC t 16

    # Start a demo print
    printer.text("Hello, ESC/POS Printer!\n")
    printer.text("------------------------\n")
    printer.set(align='center', bold=True, double_width=True)
    printer.text("Demo Print\n")
    printer.set(align='left', bold=False, double_width=False)
    printer.text("This is a test print using the python-escpos library.\n")
    printer.text("\n")
    printer.text("Features:\n")
    printer.text(" - Bold text\n")
    printer.text(" - Double width text\n")
    printer.text(" - Alignment\n")
    printer.text("------------------------\n")
    printer.qr("https://example.com", size=4)
    printer.text("\nScan the QR code to visit example.com\n")
    printer.cut()

    print("Print job completed successfully!")

except Exception as e:
    print(f"Error: {e}")
