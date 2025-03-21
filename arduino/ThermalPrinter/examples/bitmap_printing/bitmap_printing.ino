#define CAMERA_MODEL_AI_THINKER // Has PSRAM
#define CONFIG_CAMERA_TASK_STACK_SIZE 490*490

#include <Arduino.h>
#include <HardwareSerial.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "TPrinter.h"

// The camera will capture 480×320 (HVGA). After rotation, final is 320×480.
const int CAPTURE_WIDTH  = 480;   // HVGA width
const int CAPTURE_HEIGHT = 320;   // HVGA height

// 1-bit buffers
// dithering output => (CAPTURE_WIDTH/8)*CAPTURE_HEIGHT
// rotated (90°CW)  => (CAPTURE_HEIGHT/8)*CAPTURE_WIDTH
static uint8_t dithered_1bpp[(CAPTURE_WIDTH/8) * CAPTURE_HEIGHT];
static uint8_t rotated_1bpp[(CAPTURE_HEIGHT/8) * CAPTURE_WIDTH];

const byte rxPin = 3;
const byte txPin = 1;
HardwareSerial mySerial(0);
Tprinter myPrinter(&mySerial, 9600);

// We'll use two line buffers for Floyd–Steinberg dithering:
static uint8_t currentLine[CAPTURE_WIDTH];
static uint8_t nextLine[CAPTURE_WIDTH];

/**
 * Perform Floyd–Steinberg dithering from an 8-bit grayscale buffer
 * to a 1-bit (black/white) output.
 *
 * @param[in]  input   8-bit grayscale data, size = width * height
 * @param[out] output  1-bit per pixel, size = (width/8)*height
 */
void ditherTo1BPP(const uint8_t* input, int width, int height, uint8_t* output)
{
  // Helper to load one row from the grayscale input (or fill with 0 if out of range)
  auto loadRow = [&](int rowIndex, uint8_t* buffer) {
    if (rowIndex < 0 || rowIndex >= height) {
      memset(buffer, 0, width);
    } else {
      memcpy(buffer, &input[rowIndex * width], width);
    }
  };

  // Load the first two rows
  loadRow(0, currentLine);
  loadRow(1, nextLine);

  int bytesPerRow = width / 8;

  for (int y = 0; y < height; y++)
  {
    // 1) Dither currentLine, distributing error to nextLine
    for (int x = 0; x < width; x++)
    {
      int oldPixel = currentLine[x];             // 0..255
      int newPixel = (oldPixel >= 128) ? 255 : 0; // threshold
      currentLine[x] = (uint8_t)newPixel;

      int error = oldPixel - newPixel;

      // Distribute error to neighbors
      // Right (x+1)
      if (x + 1 < width) {
        currentLine[x + 1] = (uint8_t)(currentLine[x + 1] + (error * 7) / 16);
      }
      // Down-left (x-1, y+1)
      if ((x - 1 >= 0) && (y + 1 < height)) {
        nextLine[x - 1] = (uint8_t)(nextLine[x - 1] + (error * 3) / 16);
      }
      // Down (x, y+1)
      if (y + 1 < height) {
        nextLine[x] = (uint8_t)(nextLine[x] + (error * 5) / 16);
      }
      // Down-right (x+1, y+1)
      if ((x + 1 < width) && (y + 1 < height)) {
        nextLine[x + 1] = (uint8_t)(nextLine[x + 1] + (error * 1) / 16);
      }
    }

    // 2) Pack dithered row into output (1-bit)
    for (int xByte = 0; xByte < bytesPerRow; xByte++) {
      uint8_t byteVal = 0;
      for (int bit = 0; bit < 8; bit++) {
        int x = xByte * 8 + bit;
        // White => set the bit
        if (currentLine[x] == 255) {
          byteVal |= (1 << (7 - bit));
        }
      }
      output[y * bytesPerRow + xByte] = byteVal;
    }

    // 3) Move nextLine -> currentLine, load nextLine from y+2
    if (y + 1 < height) {
      memcpy(currentLine, nextLine, width);
      loadRow(y + 2, nextLine);
    }
  }
}

/**
 * Rotate a 1-bit image (width×height) by 90° clockwise.
 * The output size is height×width, i.e. outWidth=height, outHeight=width.
 *
 * @param[in]  input   1-bit image, size = (width/8)*height
 * @param[in]  width   original width in pixels
 * @param[in]  height  original height in pixels
 * @param[out] output  the rotated result, size = (height/8)*width
 */
void rotate1BPP_90CW(const uint8_t* input, int width, int height, uint8_t* output)
{
  // Clear output first (optional)
  memset(output, 0, (height/8) * width);

  // For each pixel in the original, set the corresponding rotated bit
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      // Extract bit from input[y,x]
      int inByteIndex = y * (width / 8) + (x / 8);
      int inBitPos    = 7 - (x % 8);
      bool isSet      = (input[inByteIndex] >> inBitPos) & 1;

      // Compute new coords in rotated output
      int newX = (height - 1) - y;
      int newY = x;

      // Set that bit in output
      int outByteIndex = newY * (height / 8) + (newX / 8);
      int outBitPos    = 7 - (newX % 8);
      if (isSet) {
        output[outByteIndex] |= (1 << outBitPos);
      }
    }
  }
}

void setup() {
  mySerial.begin(9600, SERIAL_8N1);
  myPrinter.begin();
  myPrinter.setHeat(1, 224, 80);
  myPrinter.justify('C');
  myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(1);

  // Configure camera for HVGA (480×320), 8-bit grayscale
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size   = FRAMESIZE_HVGA;       // 480×320
  config.pixel_format = PIXFORMAT_GRAYSCALE;  // 8-bit grayscale
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count     = 1;

  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    myPrinter.println("Camera init failed!");
    return;
  }

  ledcAttach(LED_GPIO_NUM, 5000, 8); // If LED_GPIO_NUM is defined

  Serial.println("Hello, camera!");

  // Grab one frame
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    myPrinter.println("Failed to get the image!");
    return;
  }
  esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();
  esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();

  // 'fb->width' should be 480, 'fb->height' should be 320 (if HVGA is supported).
  // 8-bit grayscale => fb->len = 480*320 = 153600 bytes
  const uint8_t* grayInput = fb->buf;

  // 1) Dither to 1-bit (no rotation)
  ditherTo1BPP(grayInput, fb->width, fb->height, dithered_1bpp);

  // 2) Rotate 90° clockwise
  rotate1BPP_90CW(dithered_1bpp, fb->width, fb->height, rotated_1bpp);

  // Free the camera buffer
  esp_camera_fb_return(fb);

  // 3) Invert the bits (negative image)
  // The rotated image is (320 wide × 480 tall), stored in rotated_1bpp.
  int sizeBytes = (CAPTURE_HEIGHT/8) * CAPTURE_WIDTH; // = (320/8)*480 = 40*480 = 19200
  for (int i = 0; i < sizeBytes; i++) {
    rotated_1bpp[i] ^= 0xFF;  // Flip all bits
  }

  // 4) Print the result: 320 wide × 480 tall
  myPrinter.printBitmap(rotated_1bpp, /*width=*/320, /*height=*/480);
  myPrinter.feed(1);
  myPrinter.println("320x480 Output (Inverted)");
  myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(2);
}

void loop() {
  // Nothing here
}
