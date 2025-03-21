// made by BinaryWorlds
// Not for commercial use, in other case by free to use it.
// Just copy this text and link to original repository:
// https://github.com/BinaryWorlds/ThermalPrinter

// I am not responsible for errors in the library. I deliver it "as is".
// I will be grateful for all suggestions.

// Tested on firmware 2.69 and JP-QR701
// Some features may not work on older firmware.
#define CAMERA_MODEL_AI_THINKER // Has PSRAM
#define CONFIG_CAMERA_TASK_STACK_SIZE 490*490
#include <Arduino.h>
#include <HardwareSerial.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "TPrinter.h"

const int width = 320;
const int height = 240;

const byte rxPin  = 3;
const byte txPin  = 1;

HardwareSerial mySerial(0);
Tprinter myPrinter(&mySerial, 9600);
uint8_t buf2[320/8 * 240];

void setupLedFlash(int pin) {
#if CONFIG_LED_ILLUMINATOR_ENABLED
  ledcAttach(pin, 5000, 8);
#else
  log_i("LED flash is disabled -> CONFIG_LED_ILLUMINATOR_ENABLED = 0");
#endif
}


#define MAX_WIDTH 480

// Two static (file-scope) line buffers, each up to MAX_WIDTH bytes
static uint8_t currentLine[MAX_WIDTH];
static uint8_t nextLine[MAX_WIDTH];

// Helper: Convert one RGB565 pixel to 8-bit grayscale
static inline uint8_t rgb565_to_gray(uint16_t pixel)
{
    // Extract 5-bit Red and Blue, 6-bit Green
    uint8_t r = (pixel >> 11) & 0x1F;
    uint8_t g = (pixel >> 5)  & 0x3F;
    uint8_t b =  pixel        & 0x1F;

    // Scale up to 8 bits
    r = (r << 3) | (r >> 2);  // 5 bits -> 8
    g = (g << 2) | (g >> 4);  // 6 bits -> 8
    b = (b << 3) | (b >> 2);  // 5 bits -> 8

    // Standard luminosity approximation
    //  (0.299 * R + 0.587 * G + 0.114 * B)
    return 255 - static_cast<uint8_t>((299*r + 587*g + 114*b) / 1000);
}

void convertTo1BPP_Dither(const uint8_t *input, uint8_t *output)
{
    // Safety check: ensure we don't overrun our static arrays
    if (width > MAX_WIDTH) {
        // Handle error (e.g., print message or return).
        fprintf(stderr, "width=%d exceeds MAX_WIDTH=%d!\n", width, MAX_WIDTH);
        return;
    }

    // Function to convert a single row from RGB565 to grayscale into a given buffer.
    auto fillGrayRow = [&](int rowIndex, uint8_t* rowBuffer) {
        // If rowIndex is beyond the image, fill with 0 (or mid gray),
        // so any "downward" error doesn't blow up real data.
        if (rowIndex >= height) {
            for (int x = 0; x < width; x++) {
                rowBuffer[x] = 0;
            }
            return;
        }
        // Each pixel is 16 bits in the input
        const uint16_t* rowRGB = reinterpret_cast<const uint16_t*>(input) + (rowIndex * width);
        for (int x = 0; x < width; x++) {
            rowBuffer[x] = rgb565_to_gray(rowRGB[x]);
        }
    };

    // Fill the first two rows: currentLine = row 0, nextLine = row 1
    fillGrayRow(0, currentLine);
    fillGrayRow(1, nextLine);

    // We'll pack 8 pixels per output byte
    int bytesPerRow = width / 8; // (assuming width is multiple of 8)

    // For each row 'y'
    for (int y = 0; y < height; y++)
    {
        // ----------------------------
        // 1) Floyd–Steinberg dithering on currentLine,
        //    distributing error into nextLine
        // ----------------------------
        for (int x = 0; x < width; x++)
        {
            int oldPixel = currentLine[x];        // 0..255
            int newPixel = (oldPixel >= 128) ? 255 : 0; // threshold
            currentLine[x] = static_cast<uint8_t>(newPixel);

            // Quantization error
            int error = oldPixel - newPixel;

            // Spread error to neighbors
            // Right pixel (x+1, same row)
            if (x + 1 < width) {
                currentLine[x + 1] = static_cast<uint8_t>(
                    currentLine[x + 1] + (error * 7) / 16
                );
            }
            // Down-left (x-1, y+1)
            if (x - 1 >= 0) {
                nextLine[x - 1] = static_cast<uint8_t>(
                    nextLine[x - 1] + (error * 3) / 16
                );
            }
            // Directly below (x, y+1)
            {
                nextLine[x] = static_cast<uint8_t>(
                    nextLine[x] + (error * 5) / 16
                );
            }
            // Down-right (x+1, y+1)
            if (x + 1 < width) {
                nextLine[x + 1] = static_cast<uint8_t>(
                    nextLine[x + 1] + (error * 1) / 16
                );
            }
        }

        // ----------------------------
        // 2) Pack the dithered currentLine into the 1BPP output
        // ----------------------------
        for (int xByte = 0; xByte < bytesPerRow; xByte++)
        {
            uint8_t byteVal = 0;
            for (int bit = 0; bit < 8; bit++)
            {
                int x = xByte * 8 + bit;
                // If pixel is white => set bit
                if (currentLine[x] == 255) {
                    // MSB is the leftmost pixel
                    byteVal |= (1 << (7 - bit));
                }
            }
            output[y * bytesPerRow + xByte] = byteVal;
        }

        // ----------------------------
        // 3) Advance to the next row:
        //    - currentLine <- nextLine
        //    - refill nextLine from row (y+2)
        // ----------------------------
        if (y + 1 < height)
        {
            // Swap the line buffers (just pointer swap)
            for (int x = 0; x < width; x++) {
                // Move nextLine into currentLine
                currentLine[x] = nextLine[x];
            }
            // Fill the nextLine with grayscale data for row y+2
            fillGrayRow(y + 2, nextLine);
        }
    }
}

void setup() {
  micros();
 
  mySerial.begin(9600, SERIAL_8N1);
  myPrinter.begin();
  myPrinter.setHeat(1, 224, 80);  // recommended for your printer, can tweak
  myPrinter.justify('C');         // center text
  myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(1);


  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_QVGA;
  config.pixel_format = PIXFORMAT_GRAYSCALE;  // for streaming
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;  
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if (config.pixel_format == PIXFORMAT_JPEG) {
    if (psramFound()) {
      config.jpeg_quality = 10;
      config.fb_count = 2;
      config.grab_mode = CAMERA_GRAB_LATEST;
    } else {
      // Limit the frame size when PSRAM is not available
      config.frame_size = FRAMESIZE_SVGA;
      config.fb_location = CAMERA_FB_IN_DRAM;
    }
  } else {
    // Best option for face detection/recognition
#if CONFIG_IDF_TARGET_ESP32S3
    config.fb_count = 2;
#endif
  }

#if defined(CAMERA_MODEL_ESP_EYE)
  pinMode(13, INPUT_PULLUP);
  pinMode(14, INPUT_PULLUP);
#endif

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    mySerial.printf("Camera init failed with error 0x%x", err);
    return;
  }
  sensor_t *s = esp_camera_sensor_get();
  s->set_special_effect(s,2);
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);        // flip it back
    s->set_brightness(s, 1);   // up the brightness just a bit
    s->set_saturation(s, -2);  // lower the saturation
  }
  // drop down frame size for higher initial frame rate
  if (config.pixel_format == PIXFORMAT_JPEG) {
    s->set_framesize(s, FRAMESIZE_QVGA);
  }

#if defined(CAMERA_MODEL_M5STACK_WIDE) || defined(CAMERA_MODEL_M5STACK_ESP32CAM)
  s->set_vflip(s, 1);
  s->set_hmirror(s, 1);
#endif

#if defined(CAMERA_MODEL_ESP32S3_EYE)
  s->set_vflip(s, 1);
#endif

// Setup LED FLash if LED pin is defined in camera_pins.h

  ledcAttach(LED_GPIO_NUM, 5000, 8);

  Serial.println("Hello, camera!");

  camera_fb_t *fb = NULL;
  esp_err_t res = ESP_OK;
  fb = esp_camera_fb_get();

  if(!fb){
    myPrinter.println("Failed to get the image! Skill issue.");
  }


  uint8_t* buf = fb->buf;

  convertTo1BPP_Dither(fb->buf, buf2);

  // Print the Among Us image in a few scales
  myPrinter.printBitmap(buf2, fb->width, fb->height);
  myPrinter.feed(1);
  myPrinter.println("Phase 1 Testing");
  myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(1);


}

void loop() {
  // Nothing here
}


