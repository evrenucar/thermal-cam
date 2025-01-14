import serial
import time

def send_to_printer(port='/dev/ttyUSB2', baudrate=9600):
    try:
        # Open the serial port
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Wait for the connection to initialize
            time.sleep(2)

            # ESC/POS Commands
            initialize = b'\x1B\x40'        # Initialize printer
            line_feed = b'\x0A'             # Line feed
            cut_paper = b'\x1D\x56\x00'     # Full cut

            # Text to print``
            text = "Hello, ESC/POS Printer!\n"

            # Combine commands
            commands = initialize + text.encode('utf-8') + line_feed + cut_paper

            # Send commands to the printer
            ser.write(commands)

            print("Commands sent to the printer successfully.")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as ex:
        print(f"An error occurred: {ex}")

if __name__ == "__main__":
    send_to_printer()
