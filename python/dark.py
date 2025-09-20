from escpos.printer import Serial
import time

PRINTER_PORT = '/dev/ttyAMA0'  # Ensure this is the correct port
BAUDRATE = 9600

try:
    # Initialize the printer with CP437 encoding
    printer = Serial(devfile=PRINTER_PORT, baudrate=BAUDRATE, encoding='cp437')  # Using 'cp437' as default

    # Reset the printer to default settings
    printer._raw(b'\x1B\x40')  # ESC @

    # Set print density to a higher value for darker print
    printer._raw(b'\x1B\x47\x10')  # ESC G 16 (Adjust '16' as per your printer's manual)
    time.sleep(0.5)  # Allow time for the printer to process the command

    # Print "BRUH" normally
    printer.text("BRUH\n")
    time.sleep(1)

    # Print "lol" normally
    printer.text("lol\n")
    time.sleep(1)

    # Enable bold mode for "meow meow"
    printer.set(bold=True)
    printer.text("meow meow\n")
    time.sleep(1)

    # Print "meow meow" with bold and newline
    printer.text("meow meow \n")
    time.sleep(1)

    # Print "meow meow meow meow" with bold
    printer.text("""We're no strangers to love
You know the rules and so do I
A full commitment's what I'm thinkin' of
You wouldn't get this from any other guy
I just wanna tell you how I'm feeling
Gotta make you understand
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you
We've known each other for so long
Your heart's been aching, but you're too shy to say it
Inside, we both know what's been going on
We know the game and we're gonna play it
And if you ask me how I'm feeling
Don't tell me you're too blind to see
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you
We've known each other for so long
Your heart's been aching, but you're too shy to say it
Inside, we both know what's been going on
We know the game and we're gonna play it
I just wanna tell you how I'm feeling
Gotta make you understand
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you
Never gonna give you up
Never gonna let you down
Never gonna run around and desert you
Never gonna make you cry
Never gonna say goodbye
Never gonna tell a lie and hurt you""")
    time.sleep(1)

    # Disable bold mode and print "lol"
    printer.set(bold=False)
    printer.text("lol\n")
    time.sleep(1)

    # Optional: Cut the paper
    # printer.cut()

    print("Test print completed successfully!")

    printer.close()

except Exception as e:
    print(f"Error: {e}")
