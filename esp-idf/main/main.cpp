/* @file main.cpp
 * @brief Thermal printer example for ESP32-CAM AI Thinker camera board
 * @author Evren Ucar && Bartlomiej Dudek
 * @date 2025-03-21
 * @version 2.0
 */

#define CAMERA_MODEL_AI_THINKER

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_camera.h"
#include "camera_pins.h"

// Include your TPrinter IDF-based library
#include "TPrinter.h"

// For demonstration, we'll use HVGA (480×320) grayscale
static const int CAPTURE_WIDTH  = 480;
static const int CAPTURE_HEIGHT = 320;

// We store the dithered/rotated image in these global buffers:
static uint8_t dithered_1bpp[(CAPTURE_WIDTH/8) * CAPTURE_HEIGHT];
static uint8_t rotated_1bpp[(CAPTURE_HEIGHT/8) * CAPTURE_WIDTH];

// Two line buffers for Floyd–Steinberg dithering (width=480)
static uint8_t currentLine[CAPTURE_WIDTH];
static uint8_t nextLine[CAPTURE_WIDTH];

/**
 * Perform Floyd–Steinberg dithering on an 8-bit grayscale input
 * of size (width×height), producing a 1-bit output in 'output'.
 */
static void ditherTo1BPP(const uint8_t* input, int width, int height, uint8_t* output)
{
    auto loadRow = [&](int rowIndex, uint8_t* buf) {
        if (rowIndex < 0 || rowIndex >= height) {
            memset(buf, 0, width);
        } else {
            memcpy(buf, &input[rowIndex * width], width);
        }
    };

    // Load first two lines
    loadRow(0, currentLine);
    loadRow(1, nextLine);

    int bytesPerRow = width / 8;

    for (int y = 0; y < height; y++) {
        // 1) Dither currentLine
        for (int x = 0; x < width; x++) {
            int oldPixel = currentLine[x];                 // 0..255
            int newPixel = (oldPixel >= 128) ? 255 : 0;     // threshold
            currentLine[x] = (uint8_t)newPixel;

            int error = oldPixel - newPixel;

            // Spread error
            if (x+1 < width) {
                currentLine[x+1] = (uint8_t)(currentLine[x+1] + (error*7)/16);
            }
            if ((x-1 >= 0) && (y+1 < height)) {
                nextLine[x-1] = (uint8_t)(nextLine[x-1] + (error*3)/16);
            }
            if (y+1 < height) {
                nextLine[x] = (uint8_t)(nextLine[x] + (error*5)/16);
            }
            if ((x+1 < width) && (y+1 < height)) {
                nextLine[x+1] = (uint8_t)(nextLine[x+1] + (error*1)/16);
            }
        }

        // 2) Pack dithered row into 1-bpp
        for (int xByte = 0; xByte < bytesPerRow; xByte++) {
            uint8_t byteVal = 0;
            for (int bit = 0; bit < 8; bit++) {
                int x = xByte*8 + bit;
                if (currentLine[x] == 255) {
                    byteVal |= (1 << (7 - bit));
                }
            }
            output[y * bytesPerRow + xByte] = byteVal;
        }

        // 3) Advance to next line
        if (y+1 < height) {
            memcpy(currentLine, nextLine, width);
            loadRow(y+2, nextLine);
        }
    }
}

/**
 * Rotate a 1-bpp image (width×height) 90° clockwise into 'output'.
 * Output size: (height×width) => new width=height, new height=width.
 */
static void rotate1BPP_90CW(const uint8_t* input, int width, int height, uint8_t* output)
{
    memset(output, 0, (height/8)*width);

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int inByteIndex = y*(width/8) + (x/8);
            int inBitPos    = 7 - (x % 8);
            bool isSet      = (input[inByteIndex] >> inBitPos) & 1;

            // new coords
            int newX = (height - 1) - y;
            int newY = x;

            int outByteIndex = newY*(height/8) + (newX/8);
            int outBitPos    = 7 - (newX % 8);
            if (isSet) {
                output[outByteIndex] |= (1 << outBitPos);
            }
        }
    }
}

extern "C" void app_main(void)
{
    // 1) Create Tprinter object on UART0 (GPIO1 TX, GPIO3 RX)
    Tprinter printer(UART_NUM_0, 9600);
    printer.initPrinterUart(/*txPin=*/1, /*rxPin=*/3);

    // Optionally, enable DTR if your hardware has a busy line
    // printer.enableDtr((gpio_num_t)2, true);

    // Initialize the printer
    printer.begin();
    printer.setHeat(1, 224, 1);
    printer.justify('C');
    printer.printText("Thermal Camera Demo!\n");
    printer.feed(2);

    // 2) Initialize camera for HVGA grayscale
    camera_config_t config;
    config.ledc_channel  = LEDC_CHANNEL_0;
    config.ledc_timer    = LEDC_TIMER_0;
    config.pin_d0        = Y2_GPIO_NUM;
    config.pin_d1        = Y3_GPIO_NUM;
    config.pin_d2        = Y4_GPIO_NUM;
    config.pin_d3        = Y5_GPIO_NUM;
    config.pin_d4        = Y6_GPIO_NUM;
    config.pin_d5        = Y7_GPIO_NUM;
    config.pin_d6        = Y8_GPIO_NUM;
    config.pin_d7        = Y9_GPIO_NUM;
    config.pin_xclk      = XCLK_GPIO_NUM;
    config.pin_pclk      = PCLK_GPIO_NUM;
    config.pin_vsync     = VSYNC_GPIO_NUM;
    config.pin_href      = HREF_GPIO_NUM;
    config.pin_sccb_sda  = SIOD_GPIO_NUM;
    config.pin_sccb_scl  = SIOC_GPIO_NUM;
    config.pin_pwdn      = PWDN_GPIO_NUM;
    config.pin_reset     = RESET_GPIO_NUM;

    // 20 MHz XCLK, HVGA = 480×320, grayscale
    config.xclk_freq_hz  = 20000000;
    config.frame_size    = FRAMESIZE_HVGA;      // 480x320
    config.pixel_format  = PIXFORMAT_GRAYSCALE; // 8-bit
    config.grab_mode     = CAMERA_GRAB_LATEST;
    config.fb_location   = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality  = 12;
    config.fb_count      = 1;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        printer.printText("Camera init failed!\n");
        printer.feed(2);
        return;
    }

    // 3) Capture one frame
    camera_fb_t *fb = esp_camera_fb_get();
    esp_camera_fb_return(fb);
    fb = esp_camera_fb_get();
    esp_camera_fb_return(fb);
    fb = esp_camera_fb_get();



    if (!fb) {
        printer.printText("esp_camera_fb_get() failed!\n");
        printer.feed(2);
        return;
    }

    if (fb->width != CAPTURE_WIDTH || fb->height != CAPTURE_HEIGHT) {
        // Just a warning, but we can still process if it's the same or smaller.
        // Or you could do additional logic here.
        printer.printText("Warning: Unexpected frame size.\n");
    }

    // 4) Dither & Rotate
    ditherTo1BPP(fb->buf, fb->width, fb->height, dithered_1bpp);
    rotate1BPP_90CW(dithered_1bpp, fb->width, fb->height, rotated_1bpp);

    // 5) Free the camera buffer
    esp_camera_fb_return(fb);

    // 6) (Optional) Invert bits => negative
    int sizeBytes = (CAPTURE_HEIGHT/8) * CAPTURE_WIDTH; // 19200 for 480×320
    for (int i = 0; i < sizeBytes; i++) {
        rotated_1bpp[i] ^= 0xFF;
    }

    // 7) Print the final 320×480 image
    printer.printBitmap(rotated_1bpp, /*width=*/320, /*height=*/480);
    printer.feed(1);
    printer.printText("Printed 320×480 capture!\n");
    printer.feed(2);

    // Done. Stay idle
    while(true) {
        vTaskDelay(portMAX_DELAY);
    }
}
