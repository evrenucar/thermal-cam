"""
Configuration settings for Thermal Camera Raspberry Pi application
"""

# E-ink Display Configuration
DISPLAY_WIDTH = 264
DISPLAY_HEIGHT = 176
DISPLAY_ROTATION = 90  # 0, 90, 180, 270

# Thermal Printer Configuration
PRINTER_PORT = '/dev/ttyAMA0'  # Serial port for thermal printer

# Printer behavior
PRINTER_HEAT_TIME = 80  # Heating time (10us units)
PRINTER_HEAT_INTERVAL = 2  # Heating interval (10us units)
PRINTER_HEATING_DOTS = 7  # Heating dots (max printing dots = 8*(n+1))

# Camera Configuration
CAMERA_ROTATION = 90  # 0, 90, 180, 270 degrees

# Output
SAVE_IMAGES = True  # Save captured/processed images to disk
IMAGE_OUTPUT_DIR = './captured_images'
