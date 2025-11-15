#!/usr/bin/env python3
"""
Thermal Camera Main Application
Captures an image from Raspberry Pi camera, displays it on e-ink display, and prints it.
Interactive keyboard control: Q=capture, W=print, E=reserved, R=quit
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from PIL import Image
import select

# Optional camera library imports
try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

try:
    from picamera import PiCamera
except ImportError:
    PiCamera = None

# numpy is required by both camera libraries for capturing arrays
try:
    import numpy as np
except ImportError:
    np = None

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib/ext'))


# Import internal modules
from int.config import (
    DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_ROTATION,
    PRINTER_PORT, 
    PRINTER_HEAT_TIME, PRINTER_HEAT_INTERVAL, PRINTER_HEATING_DOTS,
    CAMERA_ROTATION, SAVE_IMAGES, IMAGE_OUTPUT_DIR
)

# Import external modules
from epd2in7_V2 import EPD
from printer import ThermalPrinter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThermalCamera:
    """Main application class for thermal camera system"""
    
    def __init__(self):
        """Initialize camera, display, and printer"""
        self.epd = None
        self.printer = None
        self.output_dir = None
        self.current_image = None  # Store captured image
        self.current_timestamp = None # Store timestamp of capture
        self.running = True
        self.camera_available = False
        self.camera = None  # Persistent camera instance
    
    def initialize_camera(self):
        """Initialize the camera (once at startup)"""
        logger.info("Initializing camera...")
        
        # Try using libcamera first (newer method)
        if Picamera2:
            try:
                self.camera = Picamera2()
                config = self.camera.create_still_configuration(main={"size": (1640, 1232)})
                self.camera.configure(config)
                self.camera.start()
                logger.info("Camera initialized (Picamera2)")
                self.camera_available = True
                return True
            except Exception as e:
                logger.error(f"Picamera2 initialization failed: {e}")

        # Fallback to legacy picamera
        if PiCamera:
            try:
                self.camera = PiCamera()
                self.camera.resolution = (1640, 1232)
                logger.info("Camera initialized (legacy PiCamera)")
                self.camera_available = True
                return True
            except Exception as e:
                logger.error(f"Legacy PiCamera initialization failed: {e}")

        logger.error("No camera library available or initialization failed.")
        self.camera_available = False
        return False
    
    def initialize_display(self):
        """Initialize the e-ink display"""
        try:
            logger.info("Initializing e-ink display...")
            self.epd = EPD()
            if self.epd.init_Fast() == 0:
                logger.info(f"Display initialized: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
                return True
            else:
                logger.error("Failed to initialize display")
                return False
        except Exception as e:
            logger.error(f"Error initializing display: {e}")
            return False
    
    def initialize_printer(self):
        """Initialize the thermal printer"""
        try:
            logger.info(f"Initializing thermal printer on {PRINTER_PORT}...")
            self.printer = ThermalPrinter(
                heatTime=PRINTER_HEAT_TIME,
                heatInterval=PRINTER_HEAT_INTERVAL,
                heatingDots=PRINTER_HEATING_DOTS,
                serialport=PRINTER_PORT
            )
            logger.info("Printer initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing printer: {e}")
            return False
    
    def capture_image(self):
        """Capture image from already-initialized camera"""
        if not self.camera_available or not self.camera:
            logger.error("Camera not available")
            return None
        
        if not np:
            logger.error("Numpy is not installed, cannot capture image.")
            return None

        try:
            # Check if it's Picamera2
            if Picamera2 and isinstance(self.camera, Picamera2):
                arr = self.camera.capture_array()
                image = Image.fromarray(arr, mode="RGB")
            elif PiCamera and isinstance(self.camera, PiCamera):
                # Legacy PiCamera
                output = np.empty((1232, 1640, 3), dtype=np.uint8)
                self.camera.capture(output, format='rgb')
                image = Image.fromarray(output, mode="RGB")
            else:
                logger.error("Unsupported camera type.")
                return None
            
            logger.debug(f"Image captured: {image.size}")
            return image
            
        except Exception as e:
            logger.error(f"Error capturing image: {e}")
            return None
    
    def prepare_for_display(self, image):
        """Prepare image for e-ink display (convert to 1-bit BW)"""
        try:
            logger.info("Preparing image for display...")
            
            # Rotate if needed
            if CAMERA_ROTATION != 0:
                image = image.rotate(CAMERA_ROTATION, expand=True)
            
            # Adjust display size based on rotation
            if DISPLAY_ROTATION in [90, 270]:
                display_size = (DISPLAY_HEIGHT, DISPLAY_WIDTH)
            else:
                display_size = (DISPLAY_WIDTH, DISPLAY_HEIGHT)

            # Resize to fit display while maintaining aspect ratio
            image.thumbnail(display_size, Image.Resampling.LANCZOS)
            
            # Create new image with display dimensions, fill with white
            bg = Image.new('1', display_size, 1)  # 1 = white
            offset = (
                (display_size[0] - image.width) // 2,
                (display_size[1] - image.height) // 2
            )
            
            # Convert to grayscale then to 1-bit with dithering
            image_gray = image.convert('L')
            image_bw = image_gray.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
            
            bg.paste(image_bw, offset)
            logger.info(f"Image prepared for display: {bg.size}")
            return bg
            
        except Exception as e:
            logger.error(f"Error preparing image for display: {e}")
            return None
    
    def prepare_for_printer(self, image):
        """Prepare image for thermal printer (convert to 1-bit, resize to 384px width)"""
        try:
            logger.info("Preparing image for printer...")
            
            MAX_WIDTH = 384
            
            # Rotate if needed
            if CAMERA_ROTATION != 0:
                image = image.rotate(CAMERA_ROTATION, expand=True)
            
            # Resize to fit printer width
            w, h = image.size
            if w > MAX_WIDTH:
                new_height = int(h * (MAX_WIDTH / float(w)))
                image = image.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
            
            # Convert to grayscale then to 1-bit with dithering
            image_gray = image.convert('L')
            image_bw = image_gray.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
            
            logger.info(f"Image prepared for printer: {image_bw.size}")
            return image_bw
            
        except Exception as e:
            logger.error(f"Error preparing image for printer: {e}")
            return None
    
    def display_image(self, image):
        """Display image on e-ink display"""
        if not self.epd or not image:
            logger.warning("Display or image not available")
            return False
        
        try:
            logger.info("Displaying image on e-ink display...")
            
            # Get buffer from EPD
            buf = self.epd.getbuffer(image)
            
            # Display the image using fast mode
            self.epd.display_Fast(buf)
            logger.info("Image displayed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            return False
    
    def print_image(self, image):
        """Print image on thermal printer"""
        if not self.printer or not image:
            logger.warning("Printer or image not available")
            return False
        
        try:
            logger.info("Printing image on thermal printer...")
            
            # Get pixel data
            pixels = list(image.getdata())
            w, h = image.size
            
            # Print the bitmap
            self.printer.print_bitmap(pixels, w, h)
            
            # Add some line feeds and text
            self.printer.linefeed(2)
            self.printer.justify("C")
            self.printer.print_text("Thermal Camera\n")
            self.printer.justify("L")
            self.printer.linefeed(1)
            
            logger.info("Image printed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error printing image: {e}")
            return False
    
    def save_images(self, timestamp, original=None, display_img=None, printer_img=None):
        """Save images to disk for debugging"""
        if not SAVE_IMAGES or not timestamp:
            return
        
        try:
            # Create output directory if it doesn't exist
            Path(IMAGE_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            
            # Build file paths
            original_path = f"{IMAGE_OUTPUT_DIR}/{timestamp}_original.png"
            display_path = f"{IMAGE_OUTPUT_DIR}/{timestamp}_display.png"
            printer_path = f"{IMAGE_OUTPUT_DIR}/{timestamp}_printer.png"

            if original and not os.path.exists(original_path):
                original.save(original_path)
            if display_img and not os.path.exists(display_path):
                display_img.save(display_path)
            if printer_img and not os.path.exists(printer_path):
                printer_img.save(printer_path)
            
            logger.info(f"Images with timestamp {timestamp} saved to {IMAGE_OUTPUT_DIR}")
            
        except Exception as e:
            logger.error(f"Error saving images: {e}")
    
    def print_help(self):
        """Print keyboard help"""
        help_text = (
            "╔════════════════════════════════════════════════╗\n"
            "║     Thermal Camera - Interactive Mode         ║\n"
            "╠════════════════════════════════════════════════╣\n"
            "║  Q  - Capture and display image               ║\n"
            "║  W  - Print current image                     ║\n"
            "║  E  - Reserved for future use                 ║\n"
            "║  R  - Quit application                        ║\n"
            "╚════════════════════════════════════════════════╝"
        )
        print(help_text)
    
    def handle_key_input(self, key):
        """Handle keyboard input by dispatching to action methods."""
        key = key.upper()
        
        actions = {
            'Q': self._action_capture,
            'W': self._action_print,
            'E': self._action_reserved,
            'R': self._action_quit,
        }
        
        action = actions.get(key)
        if action:
            action()
        else:
            logger.warning(f"Unknown command: {key}")

    def _action_capture(self):
        """Capture, process, display, and save an image."""
        logger.info("--- ACTION: CAPTURE ---")
        print("Capturing image...")
        original = self.capture_image()
        if not original:
            print("✗ Failed to capture image")
            return

        self.current_image = original
        self.current_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        display_img = self.prepare_for_display(original)
        if display_img:
            self.display_image(display_img)
            # Save original and display images
            # self.save_images(
            #     timestamp=self.current_timestamp, 
            #     original=original, 
            #     display_img=display_img
            # )
            print("✓ Image captured and displayed")
        else:
            print("✗ Failed to prepare image for display")

    def _action_print(self):
        """Print the current image."""
        logger.info("--- ACTION: PRINT ---")
        if not self.current_image:
            print("✗ No image captured yet. Press Q to capture first.")
            return

        if not self.printer:
            print("✗ Printer not available")
            return

        print("Preparing image for printer...")
        printer_img = self.prepare_for_printer(self.current_image)
        if printer_img:
            # Save the printer image before printing
            self.save_images(
                timestamp=self.current_timestamp, 
                printer_img=printer_img
            )
            
            if self.print_image(printer_img):
                print("✓ Image printed successfully")
            else:
                print("✗ Failed to print image")
        else:
            print("✗ Failed to prepare image for printer")

    def _action_reserved(self):
        """Handle reserved key 'E'."""
        logger.info("--- ACTION: E (RESERVED) ---")
        print("E key is reserved for future use.")

    def _action_quit(self):
        """Signal the application to quit."""
        logger.info("--- ACTION: QUIT ---")
        print("Quitting application...")
        self.running = False
    
    def run_interactive(self):
        """Main interactive loop with keyboard control"""
        logger.info("Starting Thermal Camera Application (Interactive Mode)")
        
        # Initialize hardware
        if not self.initialize_display():
            logger.error("Failed to initialize display")
            return False
        
        if not self.initialize_printer():
            logger.warning("Printer not available, continuing without printer")
        
        if not self.initialize_camera():
            logger.error("Failed to initialize camera")
            return False
        
        # Print help
        self.print_help()
        
        # Interactive loop
        logger.info("Entering interactive mode. Press a key (Q, W, E, R)")
        print("\nReady for input. Press Q, W, E, or R:")
        
        try:
            while self.running:
                # Wait for keyboard input (non-blocking with timeout)
                #ready, _, _ = select.select([sys.stdin], [], [], 0.5)
                key = 'Q' #sys.stdin.read(1)
                if key:
                    self.handle_key_input(key)
                    if self.running:
                        print("\nPress Q, W, E, or R:")
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self.running = False
        
        # Cleanup
        self.cleanup()
        logger.info("Application closed")
        return True
    
    def cleanup(self):
        """Cleanup resources"""
        if self.epd:
            try:
                self.epd.sleep()
            except:
                pass
        
        if self.printer:
            try:
                self.printer.sleep()
            except:
                pass
        
        if self.camera:
            try:
                self.camera.close()
            except:
                pass


def main():
    """Main entry point"""
    app = ThermalCamera()
    try:
        # Use interactive mode
        success = app.run_interactive()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        app.cleanup()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        app.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()
