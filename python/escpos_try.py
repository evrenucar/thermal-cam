from escpos.printer import Serial
import time

PRINTER_PORT = '/dev/ttyUSB2'  # Ensure this is the correct port
BAUDRATE = 9600

# Define code pages to try
code_pages = {
    'CP437': {'encoding': 'cp437', 'command': b'\x1B\x74\x00'},
    'CP850': {'encoding': 'cp850', 'command': b'\x1B\x74\x01'},
    'CP1252': {'encoding': 'cp1252', 'command': b'\x1B\x74\x10'},
    'UTF-8': {'encoding': 'utf-8', 'command': b'\x1B\x74\x11'},  # Verify support
}

try:
    for cp_name, cp_info in code_pages.items():
        print(f"Attempting to set code page to {cp_name}...")
        
        # Initialize the printer with the specified encoding
        printer = Serial(devfile=PRINTER_PORT, baudrate=BAUDRATE, encoding=cp_info['encoding'])
        
        # Reset the printer
        printer._raw(b'\x1B\x40')  # ESC @
        time.sleep(1)  # Wait for reset
        
        # Set the code page
        printer._raw(cp_info['command'])
        time.sleep(0.5)  # Allow time for setting
        
        # Print test text
        test_text = f"Test Print with {cp_name}: Hello, World!\n"
        printer.text(test_text)
        printer.cut()
        
        print(f"Printed with {cp_name}. Check the output.\n")
        
        printer.close()
        time.sleep(2)  # Wait before next attempt

except Exception as e:
    print(f"Error: {e}")
