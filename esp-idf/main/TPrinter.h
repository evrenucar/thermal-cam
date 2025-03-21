#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "driver/uart.h"
#include "driver/gpio.h"
#include"esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

// ASCII control codes
#define A_GS  29
#define A_DC2 18
#define A_HT  9
#define A_LF  10
#define A_CR  13
#define A_SPACE  32
#define A_ESC  27
#define A_FS  28
#define A_FF  14
#define A_STAR 42

// Print modes
#define FONT_B         (1 << 0) // 9x17 instead of 12x24
#define DARK_MODE      (1 << 1) // "anti-white" mode (rarely supported)
#define UPSIDE_DOWN    (1 << 2) // rarely supported
#define BOLD           (1 << 3)
#define DOUBLE_HEIGHT  (1 << 4)
#define DOUBLE_WIDTH   (1 << 5)
#define STRIKEOUT      (1 << 6)

#define CODEPAGE_CP437 0  // USA, European Standard
#define CODEPAGE_KATAKANA 1
#define CODEPAGE_CP850 2     // Multilingual
#define CODEPAGE_CP860 3     // Portugal
#define CODEPAGE_CP863 4     // Canada-French
#define CODEPAGE_CP865 5     // Nordic
#define CODEPAGE_WCP1251 6   // Slavic
#define CODEPAGE_CP866 7     // Slavic 2
#define CODEPAGE_MIK 8       // Slavic/Bulgarian
#define CODEPAGE_CP755 9     // East Europe, Latvia 2
#define CODEPAGE_IRAN 10     // Persia
#define CODEPAGE_CP862 15    // Hebrew
#define CODEPAGE_WCP1252 16  // Latin 1
#define CODEPAGE_WCP1253 17  // Greece
#define CODEPAGE_CP852 18    // Latin 2
#define CODEPAGE_CP858 19    // Multilingual Latin 1 + ?
#define CODEPAGE_IRAN2 20    // Perisan
#define CODEPAGE_LATVIA 21
#define CODEPAGE_CP864 22       // Arabic
#define CODEPAGE_ISO_8859_1 23  // Western Europe
#define CODEPAGE_CP737 24       // Greece
#define CODEPAGE_WCP1257 25     // Baltic
#define CODEPAGE_THAI 26
#define CODEPAGE_CP720 27  // Arabic
#define CODEPAGE_CP855 28
#define CODEPAGE_CP857 29    // Turkish
#define CODEPAGE_WCP1250 30  // Central Europe
#define CODEPAGE_CP775 31
#define CODEPAGE_WCP1254 32      // Turkish
#define CODEPAGE_WCP1255 33      // Hebrew
#define CODEPAGE_WCP1256 34      // Arabic
#define CODEPAGE_WCP1258 35      // Vietnamese
#define CODEPAGE_ISO_8859_2 36   // Latin 2
#define CODEPAGE_ISO_8859_3 37   // Latin 3
#define CODEPAGE_ISO_8859_4 38   // Baltic
#define CODEPAGE_ISO_8859_5 39   // Slavic
#define CODEPAGE_ISO_8859_6 40   // Arabic
#define CODEPAGE_ISO_8859_7 41   // Greek
#define CODEPAGE_ISO_8859_8 42   // Hebrew
#define CODEPAGE_ISO_8859_9 43   // Turkish
#define CODEPAGE_ISO_8859_15 44  // Latin 9
#define CODEPAGE_THAI2 45
#define CODEPAGE_CP856 46
#define CODEPAGE_CP874 47

#define CHARSET_USA 0
#define CHARSET_FRANCE 1
#define CHARSET_GERMANY 2
#define CHARSET_UK 3
#define CHARSET_DENMARK1 4
#define CHARSET_SWEDEN 5
#define CHARSET_ITALY 6
#define CHARSET_SPAIN_1 7
#define CHARSET_JAPAN 8
#define CHARSET_NORWAY 9
#define CHARSET_DENMARK_2 10
#define CHARSET_SPAIN2 11
#define CHARSET_LATIN_AMERICA 12
#define CHARSET_SOUTH_KOREA 13
#define CHARSET_SLOVENIA 14
#define CHARSET_CHINA 15

class Tprinter {
public:
    /**
     * Constructor
     * @param uartNum  The UART controller number (e.g. UART_NUM_1)
     * @param baud     Baud rate (e.g. 9600)
     */
    Tprinter(uart_port_t uartNum, int baud = 9600);

    /**
     * Call once to configure internal fields and wait for printer readiness.
     * You can also set up the UART yourself externally. In that case,
     * skip initPrinterUart() and just ensure the `uartNum` is active.
     */
    esp_err_t initPrinterUart(int txPin, int rxPin);

    /** Basic printing interface (equivalent to Arduino's write). */
    esp_err_t writeByte(uint8_t b);
    esp_err_t writeBytes(const uint8_t* data, size_t len);

    /**
     * In Arduino, we used `Print::write()`.  
     * Here we provide a simple function for printing text. 
     * This does not expand newlines, etc. – you can do that in the caller.
     */
    esp_err_t printText(const char* text);

    /** All the methods from the original code, adapted to ESP-IDF. */
    void feed(uint8_t n = 1);
    void enableDtr(gpio_num_t dtrPin, bool busyLevel = true);
    void disableDtr(bool pullUp = true);
    void wait();
    void setDelay(uint64_t us);

    void setCodePage(uint8_t page = 36);
    void setCharset(uint8_t val = 14);

    void autoCalculate(bool val = true);
    void calculatePrintTime();
    void setTimes(uint64_t p = 30000, uint64_t f = 3000);
    void setHeat(uint8_t n1 = 9, uint8_t n2 = 80, uint8_t n3 = 2);

    void setMode(uint8_t m1=0, uint8_t m2=0, uint8_t m3=0,
                 uint8_t m4=0, uint8_t m5=0, uint8_t m6=0, uint8_t m7=0);
    void unsetMode(uint8_t m1=0, uint8_t m2=0, uint8_t m3=0,
                   uint8_t m4=0, uint8_t m5=0, uint8_t m6=0, uint8_t m7=0);

    void invert(bool n = false);
    void justify(char val);
    void underline(uint8_t n);
    void setInterline(uint8_t n);
    void setCharSpacing(uint8_t n = 0);

    void setTabs(uint8_t* tab = nullptr, uint8_t size = 0);
    void clearTabs();
    void tab();

    void reset();
    void begin();
    void offline();
    void online();

    // Demo functions (printable character sets, codepages, etc.)
    void printCharset();
    void printCodepage();

    // Replacements for some Arduino debug usage
    // e.g. might just do a no-op or use ESP_LOGI
    void identifyChars(const char* tab);
    void printFromUart(uart_port_t fromUart);

    // The big function for printing bitmaps
    void printBitmap(uint8_t* bitmap, uint16_t width, uint16_t height,
                     uint8_t scale = 1, bool center = true);

private:
    // Replacements for the old Arduino timing
    inline uint64_t getMicros() const { return esp_timer_get_time(); }

    void update();
    void initBitmapData(uint8_t rowsInPackage, uint8_t bytesPerRow);
    void sendBitmapByte(uint8_t byteToSend);
    void setDelayBitmap(uint16_t width, uint16_t height, uint16_t blackPixels);

private:
    // UART specifics
    uart_port_t uartNum_;
    int         baudrate_;

    // Printer status tracking
    bool  busyState_ = true;   // The logic level that indicates "busy"
    bool  calculateMode_ = true;
    bool  dtrEnabled_ = false;
    gpio_num_t dtrPin_ = GPIO_NUM_NC; // "Not Connected" by default

    // Timings
    uint64_t endPoint_ = 0;
    uint64_t char_send_time_ = 0;            // microseconds for one char transfer
    uint64_t oneDotHeight_printTime_ = 40000; // adjustable
    uint64_t oneDotHeight_feedTime_  = 3000;  // adjustable
    uint64_t feed_time_  = 63000; // default for 6-dot interline
    uint64_t print_time_ = 720000; // default for 24-height

    // Printer geometry
    static constexpr uint16_t widthInDots_ = 384;
    static constexpr uint8_t  printerBufferLimit_ = 255;

    uint16_t cursor_ = 0;
    uint8_t  tabs_[32]{};
    uint8_t  tabsAmount_ = 0;

    // Font / layout
    uint8_t widthMax_ = 32;   // max char per line
    uint8_t charHeight_ = 24; // dots
    uint8_t charWidth_  = 12; // dots
    uint8_t interlineHeight_ = 6;
    uint8_t charSpacing_ = 0;
    uint8_t printMode_   = 0;

    // Heating parameters
    uint8_t heating_dots_      = 9;
    uint8_t heating_time_      = 80; 
    uint8_t heating_interval_  = 2;
};
