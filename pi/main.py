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
import time
import threading
import queue

# Optional camera library imports
try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

try:
    from picamera import PiCamera
except ImportError:
    PiCamera = None

# GPIO library
try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    Button = None
    GPIO_AVAILABLE = False

# numpy is required by both camera libraries for capturing arrays
try:
    import numpy as np
except ImportError:
    np = None

# GPIO Pin definitions
CAPTURE_PIN = 5
PRINT_PIN = 13
MENU_PIN = 6
EXIT_PIN = 19

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
        self.capturing = True
        self.save_pending = False
        
        # Threading and queue
        self.display_queue = queue.Queue(maxsize=1)
        self.capture_thread = None
        self.display_thread = None
        self.image_lock = threading.Lock()
        
        # GPIO button instances
        self.button_capture = None
        self.button_print = None
        self.button_menu = None
        self.button_exit = None
    
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
    
    def initialize_gpio(self):
        """Initialize GPIO pins for button inputs using gpiozero"""
        if not GPIO_AVAILABLE:
            logger.error("gpiozero library not found. GPIO buttons will not work.")
            return False
        
        try:
            logger.info("Initializing GPIO for buttons with gpiozero...")
            
            # Initialize buttons
            self.button_capture = Button(CAPTURE_PIN, pull_up=True, bounce_time=0.05)
            self.button_print = Button(PRINT_PIN, pull_up=True, bounce_time=0.05)
            self.button_menu = Button(MENU_PIN, pull_up=True, bounce_time=0.05)
            self.button_exit = Button(EXIT_PIN, pull_up=True, bounce_time=0.5)

            # Assign callbacks
            self.button_capture.when_pressed = self._callback_toggle_capture
            self.button_print.when_pressed = self._callback_print
            self.button_menu.when_pressed = self._callback_menu
            self.button_exit.when_pressed = self._callback_exit
            
            logger.info("GPIO initialized for buttons.")
            return True
        except Exception as e:
            logger.error(f"Error initializing GPIO with gpiozero: {e}")
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
            
            logger.info(f"Image captured: {image.size}")
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
    
    def _callback_toggle_capture(self):
        """Callback to start/stop image capture loop and save on stop."""
        self.capturing = not self.capturing
        if self.capturing:
            logger.info("--- GPIO: START CAPTURE ---")
            print("Capture started. Press GPIO5 again to stop and save.")
        else:
            logger.info("--- GPIO: STOP CAPTURE ---")
            print("Capture stopped, flagging to save image.")
            self.save_pending = True

    def _callback_print(self):
        """Callback to print the current image."""
        logger.info("--- GPIO: PRINT ---")
        self._action_print()

    def _callback_menu(self):
        """Callback for menu button."""
        logger.info("--- GPIO: MENU (RESERVED) ---")
        self._action_reserved()

    def _callback_exit(self):
        """Callback to exit the application."""
        logger.info("--- GPIO: EXIT ---")
        self._action_quit()

    def _action_print(self):
        """Print the current image."""
        logger.info("--- ACTION: PRINT ---")
        
        with self.image_lock:
            image_to_print = self.current_image
            timestamp_to_print = self.current_timestamp

        if not image_to_print:
            print("✗ No image captured yet. Press GPIO5 to capture first.")
            return

        if not self.printer:
            print("✗ Printer not available")
            return

        print("Preparing image for printer...")
        printer_img = self.prepare_for_printer(image_to_print)
        if printer_img:
            self.save_images(
                timestamp=timestamp_to_print, 
                printer_img=printer_img
            )
            
            if self.print_image(printer_img):
                print("✓ Image printed successfully")
            else:
                print("✗ Failed to print image")
        else:
            print("✗ Failed to prepare image for printer")

    def _action_reserved(self):
        """Handle reserved key."""
        logger.info("--- ACTION: RESERVED ---")
        print("Reserved button pressed.")

    def _action_quit(self):
        """Signal the application to quit."""
        logger.info("--- ACTION: QUIT ---")
        print("Quitting application...")
        self.running = False
    
    def _capture_loop(self):
        """Thread target for continuous image capture."""
        logger.info("Capture thread started.")
        while self.running:
            if not self.capturing:
                time.sleep(0.1)
                continue

            try:
                original = self.capture_image()
                if original:
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    try:
                        # Drop old frame if queue is full
                        if self.display_queue.full():
                            self.display_queue.get_nowait()
                        self.display_queue.put_nowait((original, timestamp))
                    except queue.Full:
                        logger.warning("Display queue is full, dropping a frame.")
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(1)
        logger.info("Capture thread finished.")

    def _display_loop(self):
        """Thread target for displaying images from the queue."""
        logger.info("Display thread started.")
        while self.running:
            try:
                original, timestamp = self.display_queue.get(timeout=0.2)
                
                with self.image_lock:
                    self.current_image = original
                    self.current_timestamp = timestamp
                
                print("Displaying image...")
                display_img = self.prepare_for_display(original)
                if display_img:
                    self.display_image(display_img)
                    print("✓ Image displayed")
                else:
                    print("✗ Failed to prepare image for display")

            except queue.Empty:
                if self.save_pending:
                    self._save_current_image()
                    self.save_pending = False
                continue
            except Exception as e:
                logger.error(f"Error in display loop: {e}")
        logger.info("Display thread finished.")

    def _save_current_image(self):
        """Helper to save the current image."""
        with self.image_lock:
            image_to_save = self.current_image
            timestamp_to_save = self.current_timestamp

        if image_to_save:
            print("Saving image...")
            display_img = self.prepare_for_display(image_to_save)
            self.save_images(
                timestamp=timestamp_to_save,
                original=image_to_save,
                display_img=display_img
            )
            print("✓ Image saved.")
        else:
            print("No image to save.")

    def run(self):
        """Main loop with GPIO button control"""
        logger.info("Starting Thermal Camera Application (GPIO Mode)")
        
        # Initialize hardware
        if not self.initialize_display():
            logger.error("Failed to initialize display")
            return False
        
        if not self.initialize_printer():
            logger.warning("Printer not available, continuing without printer")
        
        if not self.initialize_camera():
            logger.error("Failed to initialize camera")
            return False
            
        if not self.initialize_gpio():
            # Error already logged
            return False
        
        print("Application started. Use GPIO buttons to control.")
        print(f"  GPIO{CAPTURE_PIN}: Start/Stop Capture (saves on stop)")
        print(f"  GPIO{PRINT_PIN}: Print")
        print(f"  GPIO{EXIT_PIN}: Exit")
        
        self.running = True
        self.capturing = True

        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.display_thread = threading.Thread(target=self._display_loop)
        self.capture_thread.start()
        self.display_thread.start()

        try:
            while self.running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        finally:
            logger.info("Shutting down...")
            self.running = False
            
            if self.capture_thread and self.capture_thread.is_alive():
                self.capture_thread.join()
            if self.display_thread and self.display_thread.is_alive():
                self.display_thread.join()

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
        
        # No explicit cleanup needed for gpiozero when the script ends gracefully


def main():
    """Main entry point"""
    app = ThermalCamera()
    try:
        # Use GPIO mode
        success = app.run()
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
