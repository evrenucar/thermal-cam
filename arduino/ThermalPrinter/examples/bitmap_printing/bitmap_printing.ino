// made by BinaryWorlds
// Not for commercial use, in other case by free to use it.
// Just copy this text and link to original repository:
// https://github.com/BinaryWorlds/ThermalPrinter

// I am not responsible for errors in the library. I deliver it "as is".
// I will be grateful for all suggestions.

// Tested on firmware 2.69 and JP-QR701
// Some features may not work on older firmware.
#define CAMERA_MODEL_AI_THINKER // Has PSRAM

#include <Arduino.h>
#include <HardwareSerial.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "TPrinter.h"

// Same dimensions: 40 wide × 37 tall = 1480 bits total = 185 bytes
const uint16_t amongUsBitmapWidth  = 384;
const uint16_t amongUsBitmapHeight = 512;
      const int width = 240;
    const int height = 240;
int16_t ztemp[width * height];


const byte rxPin  = 3;
const byte txPin  = 1;

HardwareSerial mySerial(0);
Tprinter myPrinter(&mySerial, 9600);
uint8_t buf2[240/8 * 240];

void setupLedFlash(int pin) {
#if CONFIG_LED_ILLUMINATOR_ENABLED
  ledcAttach(pin, 5000, 8);
#else
  log_i("LED flash is disabled -> CONFIG_LED_ILLUMINATOR_ENABLED = 0");
#endif
}



void convertTo1BPP_Dither(const uint8_t *input, uint8_t *output) {

    
    // Use a temporary buffer with int16_t to hold pixel values and accumulated error.
    // This avoids floats while allowing negative error values.
    
    // Copy input grayscale values into the temporary buffer.
    for (int i = 0; i < width * height; i++) {
        ztemp[i] = input[i];
    }
    
    // Apply Floyd–Steinberg dithering using integer arithmetic.
    // We use a threshold of 128 to decide between black (0) and white (255).
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int idx = y * width + x;
            int oldPixel = ztemp[idx];
            int newPixel = (oldPixel >= 128) ? 255 : 0;
            int error = oldPixel - newPixel;
            ztemp[idx] = newPixel;
            
            // Distribute the error to neighboring pixels:
            // Right pixel gets 7/16 of the error.
            if (x + 1 < width)
                ztemp[y * width + (x + 1)] += (error * 7) / 16;
            // Bottom-left gets 3/16.
            if (x - 1 >= 0 && y + 1 < height)
                ztemp[(y + 1) * width + (x - 1)] += (error * 3) / 16;
            // Bottom gets 5/16.
            if (y + 1 < height)
                ztemp[(y + 1) * width + x] += (error * 5) / 16;
            // Bottom-right gets 1/16.
            if (x + 1 < width && y + 1 < height)
                ztemp[(y + 1) * width + (x + 1)] += (error * 1) / 16;
        }
    }
    
    // Pack the dithered binary image into the output buffer.
    // The output buffer is organized in pages of 8 rows each.
    // For each column and page, pack 8 pixels (one per bit) into a byte.
    for (int page = 0; page < height / 8; page++) {
        for (int x = 0; x < width; x++) {
            uint8_t byte = 0;
            for (int bit = 0; bit < 8; bit++) {
                int y = page * 8 + bit;
                int idx = y * width + x;
                // Set the bit if the pixel is white (255).
                if (ztemp[idx] == 255) {
                    byte |= (1 << (7 - bit)); // MSB is the top pixel.
                }
            }
            output[page * width + x] = byte;
        }
    }
}

void setup() {
  micros();
 
  mySerial.begin(9600, SERIAL_8N1);
  myPrinter.begin();
  myPrinter.setHeat(1, 224, 80);  // recommended for your printer, can tweak
//  myPrinter.setHeat(1, 224, 40);  // recommended for your printer, can tweak
  myPrinter.justify('C');         // center text
    myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(1);

  //Serial.begin(115200);
  //Serial.setDebugOutput(true);
  //Serial.println();

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
  config.frame_size = FRAMESIZE_240X240;
  // config.pixel_format = PIXFORMAT_GRAYSCALE;  // for streaming
  config.pixel_format = PIXFORMAT_RGB565; // for face detection/recognition
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
    config.frame_size = FRAMESIZE_240X240;
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


  // myPrinter.enableDtr(dtrPin, LOW);
  uint8_t* buf = fb->buf;

  convertTo1BPP_Dither(fb->buf, buf2);

  // for(int i = 0; i < 240 / 8; i++){
  //   for(int j = 0; j < 240; j++){
  //     buf2[i * 240 + j] = 0;
  //     for(int z = 0; z < 8; z++){
  //       uint8_t val;
  //       if(buf[(i*8+z)*240+j] > 100){
  //         val = 0xff;
  //       } else {
  //         val = 0x00;
  //       }
  //       buf2[i*240 + j] |= (1<< (7 - z)) & val;
  //     }
  //   }
  // }

  // Print the Among Us image in a few scales
  myPrinter.printBitmap(buf2, fb->width, fb->height);
  myPrinter.feed(1);
  myPrinter.println("Phase 1 Testing");
  myPrinter.println("Evren and Bartek ©");
  myPrinter.feed(1);


  // myPrinter.printBitmap(amongUsBitmap, amongUsBitmapWidth, amongUsBitmapHeight, 5);
  // myPrinter.feed(1);
  // // myPrinter.println("5x bigger");

  // myPrinter.printBitmap(amongUsBitmap, amongUsBitmapWidth, amongUsBitmapHeight, 0);
  // myPrinter.feed(1);
  // myPrinter.println("Max size");

  // Print again uncentered
  // myPrinter.printBitmap(amongUsBitmap, amongUsBitmapWidth, amongUsBitmapHeight, 1, false);
  // myPrinter.feed(1);
  // myPrinter.println("Original size, not centered");
}

void loop() {
  // Nothing here
}


// // made by BinaryWorlds
// // Not for commercial use, in other case by free to use it.
// // Just copy this text and link to oryginal repository:
// // https://github.com/BinaryWorlds/ThermalPrinter

// // I am not responsible for errors in the library. I deliver it "as it is".
// // I will be grateful for all suggestions.

// // Tested on firmware 2.69 and JP-QR701
// // Some features may not work on the older firmware.

// #include <Arduino.h>
// #include <HardwareSerial.h>

// #include "TPrinter.h"

// const uint8_t bitmapWidth = 40;
// const uint8_t bitmapHeight = 37;

// // link to repo
// uint8_t qrcode[] = {
//     0x7F, 0x2,  0x72, 0x1D, 0xFC, 0x41, 0x5,  0x38, 0xE1, 0x4,  0x5D, 0x75, 0x73, 0x51, 0x74, 0x5D,
//     0x25, 0x0,  0x35, 0x74, 0x5D, 0x4E, 0xB7, 0x99, 0x74, 0x41, 0x7C, 0x8F, 0x45, 0x4,  0x7F, 0x55,
//     0x55, 0x55, 0xFC, 0x0,  0x27, 0x2E, 0x20, 0x0,  0x25, 0x46, 0xE3, 0x6E, 0xD0, 0xE,  0xBE, 0x87,
//     0x91, 0x8,  0x33, 0x95, 0xC7, 0xFA, 0x60, 0x20, 0xF1, 0x9A, 0x5E, 0xF8, 0xB,  0xB,  0x93, 0x43,
//     0x8C, 0x3A, 0xA7, 0x28, 0xBE, 0x50, 0x7D, 0x8B, 0x6F, 0x8D, 0x30, 0x34, 0xD2, 0xB2, 0xD5, 0x9C,
//     0x73, 0xEC, 0x2C, 0x3,  0xB8, 0x78, 0xC,  0x21, 0x6D, 0xC0, 0x3,  0xEA, 0xCA, 0xCB, 0x80, 0x56,
//     0x5E, 0xDE, 0x9E, 0xDC, 0x63, 0xAA, 0x3,  0xB,  0x18, 0x2,  0x1A, 0x50, 0xB8, 0x48, 0x2B, 0x8F,
//     0xFD, 0x8E, 0x0,  0x28, 0x57, 0x63, 0x94, 0xB0, 0x23, 0xA7, 0x63, 0x39, 0x5C, 0x4C, 0x77, 0x7A,
//     0x27, 0xF0, 0x1D, 0xA4, 0x0,  0xF6, 0xA0, 0x2,  0x4A, 0xA7, 0x91, 0x8,  0x67, 0x7D, 0xA7, 0x8F,
//     0xC8, 0x0,  0x72, 0xE3, 0xBC, 0x60, 0x7F, 0x2C, 0x80, 0xE5, 0x78, 0x41, 0x30, 0x4D, 0x84, 0x5C,
//     0x5D, 0x41, 0x69, 0xC7, 0xF4, 0x5D, 0x11, 0xFC, 0x9,  0x70, 0x5D, 0x2D, 0x46, 0x15, 0x88, 0x41,
//     0x6B, 0x33, 0x4A, 0xD8, 0x7F, 0x1D, 0xF,  0xA8, 0x1C};
// // 185 bytes length
// // 40 * 37 * 8 = 1480

// const byte rxPin = 16;
// const byte txPin = 17;
// const byte dtrPin = 27;  // optional
// const byte rsePin = 4;   // direction of transmission, max3485

// HardwareSerial mySerial(2);
// Tprinter myPrinter(&mySerial, 9600);

// void setup() {
//   micros();
//   mySerial.begin(9600, SERIAL_8N1, rxPin, txPin);

//   pinMode(rsePin, OUTPUT);     // optional
//   digitalWrite(rsePin, HIGH);  // optional

//   // myPrinter.enableDtr(dtrPin, LOW);

//   myPrinter.begin();
//   myPrinter.setHeat(1, 224, 40);  // in begin setHeat was called with val: 0,255,0
//   myPrinter.justify('C');         // only text

//   myPrinter.printBitmap(qrcode, bitmapWidth, bitmapHeight);
//   myPrinter.feed(1);
//   myPrinter.println("orginal size");

//   myPrinter.printBitmap(qrcode, bitmapWidth, bitmapHeight, 5);
//   myPrinter.feed(1);
//   myPrinter.println("5x bigger");

//   myPrinter.printBitmap(qrcode, bitmapWidth, bitmapHeight, 0);
//   myPrinter.feed(1);
//   myPrinter.println("max size");

//   myPrinter.printBitmap(qrcode, bitmapWidth, bitmapHeight, 1, false);
//   myPrinter.feed(1);
//   myPrinter.println("original size, not centered");
// }
// void loop() {}