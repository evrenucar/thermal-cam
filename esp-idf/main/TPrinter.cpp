#include "TPrinter.h"
#include "esp_log.h"

// Optional logging tag
static const char* TAG = "Tprinter";

//-------------- CONSTRUCTOR & UART INIT --------------

Tprinter::Tprinter(uart_port_t uartNum, int baud)
    : uartNum_(uartNum), baudrate_(baud)
{
    // For 8N1, the time (us) to send 1 character = 10 or 11 bit times
    // We'll use 11 bit times for safety:
    // char_send_time_ = (11 * 1,000,000) / baudrate_;
    char_send_time_ = (11ULL * 1000000ULL) / baudrate_;
}

esp_err_t Tprinter::initPrinterUart(int txPin, int rxPin)
{
    // Basic config for the selected UART
    uart_config_t uart_config = {
        .baud_rate = baudrate_,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk= UART_SCLK_DEFAULT
    };

    esp_err_t ret = uart_param_config(uartNum_, &uart_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "uart_param_config failed");
        return ret;
    }

    ret = uart_set_pin(uartNum_, txPin, rxPin, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "uart_set_pin failed");
        return ret;
    }

    // Buffer sizes, queue size (0 => no event queue)
    ret = uart_driver_install(uartNum_, 1024, 0, 0, NULL, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "uart_driver_install failed");
        return ret;
    }

    // Optional: small delay to let the printer wake
    vTaskDelay(pdMS_TO_TICKS(100));

    return ESP_OK;
}

//-------------- BASIC WRITE / PRINT --------------

esp_err_t Tprinter::writeByte(uint8_t b)
{
    return writeBytes(&b, 1);
}

esp_err_t Tprinter::writeBytes(const uint8_t* data, size_t len)
{
    // We wait for any necessary previous “busy” or “timing” constraints
    wait();
    // Then write
    int written = uart_write_bytes(uartNum_, (const char*)data, len);
    if (written < 0) {
        ESP_LOGE(TAG, "uart_write_bytes failed");
        return ESP_FAIL;
    }

    // After sending, we might add a small delay to respect any data timing
    // but we handle that with setDelay(...) or endPoint_ logic if not using DTR.
    return ESP_OK;
}

esp_err_t Tprinter::printText(const char* text)
{
    // In Arduino, we had multiple ways. Here is a simple approach:
    size_t len = strlen(text);
    return writeBytes((const uint8_t*)text, len);
}

//-------------- WAIT & TIMING --------------

void Tprinter::wait()
{
    if (dtrEnabled_) {
        // Wait until the busy pin is NOT in the "busy" state
        while (gpio_get_level(dtrPin_) == (int)busyState_) {
            // Sleep or yield
            vTaskDelay(1);
        }
    } else {
        // If we do not have DTR, we rely on endPoint_ timing
        int64_t remaining = (int64_t)endPoint_ - (int64_t)getMicros();
        while (remaining > 0) {
            // busy-wait or do a small vTaskDelay
            remaining = (int64_t)endPoint_ - (int64_t)getMicros();
        }
    }
}

void Tprinter::setDelay(uint64_t us)
{
    if (!dtrEnabled_) {
        endPoint_ = getMicros() + us;
    }
}

//-------------- DTR FLOW CONTROL --------------

void Tprinter::enableDtr(gpio_num_t dtrPin, bool busyLevel)
{
    // If we already had a DTR pin, disable it
    if (dtrEnabled_ && dtrPin_ != dtrPin) {
        disableDtr();
    }

    dtrPin_    = dtrPin;
    busyState_ = busyLevel;

    // Configure as input w/ pull-up if needed
    gpio_config_t cfg = {};
    cfg.intr_type    = GPIO_INTR_DISABLE;
    cfg.mode         = GPIO_MODE_INPUT;
    cfg.pull_up_en   = GPIO_PULLUP_ENABLE;   // or false if you want
    cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    cfg.pin_bit_mask = (1ULL << dtrPin_);
    gpio_config(&cfg);

    dtrEnabled_ = true;
    wait();

    // Send "enable hardware flow control" to the printer if needed
    // On many printers, GS 'a' or DC2 can be used to enable real-time status
    // For example:
    writeByte(A_GS);
    writeByte('a');
    // 1<<5 => "Enable real-time status transmission" on some firmware
    writeByte((uint8_t)(1 << 5));

    setDelay(3 * char_send_time_);
}

void Tprinter::disableDtr(bool pullUp /*= true*/)
{
    // For safety, re-configure the pin
    gpio_config_t cfg = {};
    cfg.intr_type    = GPIO_INTR_DISABLE;
    cfg.mode         = GPIO_MODE_INPUT;
    cfg.pull_down_en = GPIO_PULLDOWN_DISABLE;
    cfg.pull_up_en   = pullUp ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE;
    cfg.pin_bit_mask = (1ULL << dtrPin_);
    gpio_config(&cfg);

    dtrEnabled_ = false;
}

//-------------- FEED / CODEPAGE / CHARSET --------------

void Tprinter::feed(uint8_t n)
{
    wait();
    // ESC 'd' <n>
    writeByte(A_ESC);
    writeByte('d');
    writeByte(n);

    // Delay to accommodate feeding
    setDelay(3 * char_send_time_ + feed_time_ * n);
    cursor_ = 0;
}

void Tprinter::setCodePage(uint8_t page /*=36*/)
{
    if (page > 47) page = 47;
    wait();

    // FS '.' => Kanji mode off
    writeByte(A_FS);
    writeByte('.');
    // ESC 't' <n>
    writeByte(A_ESC);
    writeByte('t');
    writeByte(page);

    setDelay(5 * char_send_time_);
}

void Tprinter::setCharset(uint8_t val /*=14*/)
{
    if (val > 15) val = 15;
    wait();

    // ESC 'R' <n>
    writeByte(A_ESC);
    writeByte('R');
    writeByte(val);

    setDelay(3 * char_send_time_);
}

//-------------- TIME CALCULATION / HEATING --------------

void Tprinter::autoCalculate(bool val /*=true*/)
{
    calculateMode_ = val;
    update(); 
}

void Tprinter::calculatePrintTime()
{
    // Rough estimate of total time based on dot usage
    // If you want to refine the formula, do so here
    print_time_ = ((widthInDots_ * charHeight_) / ((heating_dots_ + 1)*8)) 
                    * 10ULL * (heating_time_ + heating_interval_);
}

void Tprinter::setTimes(uint64_t p, uint64_t f)
{
    oneDotHeight_printTime_ = p;
    oneDotHeight_feedTime_  = f;

    if (!calculateMode_) {
        print_time_ = p * charHeight_;
        feed_time_  = f * (interlineHeight_ + charHeight_);
    }
}

void Tprinter::setHeat(uint8_t n1, uint8_t n2, uint8_t n3)
{
    wait();
    heating_dots_     = n1;
    heating_time_     = n2;
    heating_interval_ = n3;

    // ESC '7' => set heating parameters
    writeByte(A_ESC);
    writeByte('7');
    writeByte(n1);
    writeByte(n2);
    writeByte(n3);

    setDelay(5 * char_send_time_);
    if (calculateMode_) {
        calculatePrintTime();
    }
}

//-------------- MODE / STYLE --------------

void Tprinter::setMode(uint8_t m1, uint8_t m2, uint8_t m3,
                       uint8_t m4, uint8_t m5, uint8_t m6, uint8_t m7)
{
    wait();
    printMode_ |= (m1 + m2 + m3 + m4 + m5 + m6 + m7);

    writeByte(A_ESC);
    writeByte('!');
    writeByte(printMode_);

    setDelay(3 * char_send_time_);
    update();
}

void Tprinter::unsetMode(uint8_t m1, uint8_t m2, uint8_t m3,
                         uint8_t m4, uint8_t m5, uint8_t m6, uint8_t m7)
{
    wait();
    printMode_ &= ~(m1 + m2 + m3 + m4 + m5 + m6 + m7);

    writeByte(A_ESC);
    writeByte('!');
    writeByte(printMode_);

    setDelay(3 * char_send_time_);
    update();
}

void Tprinter::invert(bool n /*=false*/)
{
    wait();
    // ESC '{' <n>
    writeByte(A_ESC);
    writeByte('{');
    writeByte(n ? 1 : 0);
    setDelay(3 * char_send_time_);
}

void Tprinter::justify(char val)
{
    wait();
    uint8_t set = 0;
    switch (val) {
        case 'L': set = 0; break;
        case 'C': set = 1; break;
        case 'R': set = 2; break;
        default:  set = 0; // fallback to left
    }
    // ESC 'a' <set>
    writeByte(A_ESC);
    writeByte('a');
    writeByte(set);

    setDelay(3 * char_send_time_);
}

void Tprinter::underline(uint8_t n)
{
    if (n > 2) n = 2;
    wait();
    // ESC '-' <n>
    writeByte(A_ESC);
    writeByte('-');
    writeByte(n);

    setDelay(3 * char_send_time_);
}

void Tprinter::setInterline(uint8_t n)
{
    wait();
    // ESC '3' <n+charHeight_>
    writeByte(A_ESC);
    writeByte('3');

    if (n + charHeight_ >= 255) {
        interlineHeight_ = 255 - charHeight_;
    } else {
        interlineHeight_ = n;
    }
    uint8_t lineValue = interlineHeight_ + charHeight_;
    writeByte(lineValue);

    update();
    setDelay(3 * char_send_time_);
}

void Tprinter::setCharSpacing(uint8_t n /*=0*/)
{
    wait();
    // ESC ' ' <n>
    writeByte(A_ESC);
    writeByte(A_SPACE);
    writeByte(n);
    charSpacing_ = n;

    setDelay(3 * char_send_time_);
}

void Tprinter::setTabs(uint8_t* tab, uint8_t size)
{
    tabsAmount_ = 0;
    wait();
    // ESC 'D' ...
    writeByte(A_ESC);
    writeByte('D');

    for (uint8_t i = 0; i < size; i++) {
        if (tab[i] < widthMax_ && (tabsAmount_ < 32)) {
            writeByte(tab[i]);
            tabs_[tabsAmount_++] = (uint16_t)tab[i] * charWidth_;
        }
    }
    writeByte(0); // terminator
    cursor_ = 0;
    setDelay((tabsAmount_ + 3) * char_send_time_);
}

void Tprinter::clearTabs()
{
    wait();
    // ESC 'D' '0'
    writeByte(A_ESC);
    writeByte('D');
    writeByte('0');
    setDelay(3 * char_send_time_);

    tabsAmount_ = 0;
    memset(tabs_, 0, sizeof(tabs_));
}

void Tprinter::tab()
{
    for (uint8_t i = 0; i < tabsAmount_; i++) {
        if (tabs_[i] > cursor_) {
            cursor_ = tabs_[i];
            break;
        }
    }
    // send HT
    writeByte(A_HT);

    if ((widthInDots_ - cursor_) < charWidth_) {
        // new line
        setDelay(char_send_time_ + print_time_ + feed_time_);
        cursor_ = 0;
    } else {
        setDelay(char_send_time_);
    }
}

//-------------- RESET / BEGIN / ONLINE / OFFLINE --------------

void Tprinter::reset()
{
    // ESC '@'
    writeByte(A_ESC);
    writeByte('@');

    setDelay(2 * char_send_time_);
    cursor_ = 0;
    tabsAmount_ = 0;
    memset(tabs_, 0, sizeof(tabs_));

    interlineHeight_ = 6;
    printMode_   = 0;
    charSpacing_ = 0;

    heating_dots_     = 9;
    heating_time_     = 80;
    heating_interval_ = 2;

    update();
}

void Tprinter::begin()
{
    // Wait ~2 seconds
    setDelay(2000000ULL);
    wait();

    reset();
    online();
    setHeat();
    setCodePage();
    setCharset();
    setInterline(0);

    // Example: set some default tabs
    uint8_t list[] = {4, 8, 12, 16, 20, 24, 28, 32, 36, 40};
    setTabs(list, sizeof(list));
}

void Tprinter::offline()
{
    wait();
    // ESC '=' 0
    writeByte(A_ESC);
    writeByte('=');
    writeByte(0);

    setDelay(3 * char_send_time_);
}

void Tprinter::online()
{
    wait();
    // ESC '=' 1
    writeByte(A_ESC);
    writeByte('=');
    writeByte(1);

    setDelay(3 * char_send_time_);
}

//-------------- PRINT CHARSET / CODEPAGE DEMOS --------------

void Tprinter::printCharset()
{
    wait();
    // Example printing ASCII 0x20~0x7F
    // You can add line formatting as needed
    writeByte('\n');
    const char* header = "   01234567 89ABCDEF\n";
    printText(header);

    for (uint8_t i = 32; i < 128; i++) {
        if ((i % 16) == 0) {
            writeByte('\n');
            // Show row heading
            char buf[8];
            sprintf(buf, "%X- ", i/16);
            printText(buf);
        }
        writeByte(i);
        // Insert a space in the middle
        if ((i % 16) == 7) writeByte(' ');
    }
    writeByte('\n');
}

void Tprinter::printCodepage()
{
    wait();
    // Print range 0x80~0xFF
    writeByte('\n');
    const char* header = "   01234567 89ABCDEF\n";
    printText(header);

    for (uint16_t i = 128; i < 256; i++) {
        if ((i % 16) == 0) {
            writeByte('\n');
            char buf[8];
            if (i/16 < 10) sprintf(buf, "%d- ", i/16);
            else           sprintf(buf, "%X- ", i/16);
            printText(buf);
        }
        writeByte((uint8_t)i);
        if ((i % 16) == 7) writeByte(' ');
    }
    writeByte('\n');
}

//-------------- IDENTIFY CHARS / PRINT FROM UART --------------

void Tprinter::identifyChars(const char* tab)
{
    // This is a debug function that in Arduino printed hex values to Serial.
    // In IDF, we might just log them:
    ESP_LOGI(TAG, "Identify chars:");
    int i = 0;
    while (tab[i] != 0) {
        if (tab[i] != ' ') {
            // Print the chunk until next space
            int start = i;
            while (tab[i] != ' ' && tab[i] != 0) {
                i++;
            }
            // Show them
            char chunk[64];
            int n = i - start;
            if (n >= (int)sizeof(chunk)) n = sizeof(chunk)-1;
            memcpy(chunk, &tab[start], n);
            chunk[n] = 0;
            ESP_LOGI(TAG, "String: \"%s\"", chunk);
            // Show hex
            for (int j = 0; j < n; j++) {
                ESP_LOGI(TAG, "Char %c => 0x%02X", chunk[j], (unsigned char)chunk[j]);
            }
        } else {
            i++;
        }
    }
}

void Tprinter::printFromUart(uart_port_t fromUart)
{
    // This tries to read from `fromUart` and send to the printer's `uartNum_`.
    const int BufSize = 128;
    uint8_t buf[BufSize];
    while (true) {
        int len = uart_read_bytes(fromUart, buf, BufSize, 20/portTICK_PERIOD_MS);
        if (len > 0) {
            // Print each byte
            for (int i = 0; i < len; i++) {
                writeByte(buf[i]);
            }
        } else {
            // No more data
            break;
        }
    }
}

//-------------- BITMAP PRINTING --------------

void Tprinter::initBitmapData(uint8_t rowsInPackage, uint8_t bytesPerRow)
{
    wait();
    writeByte(A_DC2);
    writeByte(A_STAR);
    writeByte(rowsInPackage);
    writeByte(bytesPerRow);

    setDelay(4 * char_send_time_);
}

void Tprinter::sendBitmapByte(uint8_t byteToSend)
{
    wait();
    writeByte(byteToSend);
    setDelay(char_send_time_);
}

void Tprinter::setDelayBitmap(uint16_t width, uint16_t height, uint16_t blackPixels)
{
    if (dtrEnabled_) return;

    if (calculateMode_) {
        // A naive approach: 
        // ratio of blackPixels / totalPixels => approximate
        uint32_t totalPixels = width * height;
        double fraction = (double)blackPixels / (double)totalPixels;

        double dotTime = ((widthInDots_ * charHeight_) /
                          ((heating_dots_ + 1)*8)) *
                          10.0 * (heating_time_ + heating_interval_);

        uint64_t timeUs = (uint64_t)(fraction * dotTime);
        setDelay(timeUs);
    } else {
        // If not auto-calculating, we do a simpler approach:
        setDelay((oneDotHeight_printTime_ + oneDotHeight_feedTime_) * height);
    }
}
void Tprinter::printBitmap(uint8_t* bitmap, uint16_t width, uint16_t height,
                           uint8_t scale, bool center)
{
    // 1) Determine scale
    uint16_t maxScale = widthInDots_ / width;  // e.g. 384 / userWidth
    if (scale == 0 || scale > maxScale) {
        scale = maxScale;
    }

    // 2) Compute margin
    uint16_t marginWidth = 0;
    if (center) {
        marginWidth = (widthInDots_ - (scale * width)) / 2; 
    }

    // 3) Calculate the final scaled row width in pixels
    //    e.g. if scale=2 and width=100 => scaledWidth=200
    //    add margin => printedWidth=200+someMargin
    uint16_t scaledWidth  = scale * width;
    uint16_t printedWidth = scaledWidth + marginWidth;

    // 4) Byte count per row in final output
    uint16_t bytesPerRow = (printedWidth + 7) / 8;

    // 5) Package / buffer logic
    //    The printer can handle only up to `printerBufferLimit_` bytes at once.
    //    We figure out how many *full lines* that equates to (rowsInPackage).
    //    bufferSize = (rowsInPackage * bytesPerRow).
    uint16_t bufferSize      = (printerBufferLimit_ / bytesPerRow) * bytesPerRow;
    uint16_t rowsInPackage   = bufferSize / bytesPerRow;
    uint16_t totalRowsToSend = height * scale;  // total scaled rows

    // 6) Prepare iteration variables
    uint16_t bufferFillLevel = 0; // how many bytes have we put in this chunk
    uint16_t burned          = 0; // how many black pixels (for time calc)
    uint16_t currentDotNr    = 0; // how many pixels have been packed this row

    // We build each byte in 'byteToSend' from the leftmost pixel to the right, 
    // writing bits from MSB down to LSB, so offset=7..0
    uint8_t byteToSend = 0;
    uint8_t offset     = 7;

    // 7) Start with a feed(1), just like the original code.
    feed(1);

    // 8) Outer loops: for each row, we replicate the "rowFat" scale
    for (uint16_t row = 0; row < height; row++) {
        for (uint8_t rowFat = 0; rowFat < scale; rowFat++) {

            bool     isMarginAdded = false;
            uint16_t marginCounter = 0;

            // 9) For each column in the original image
            for (uint16_t column = 0; column < width; column++) {

                // EXACT margin logic from original
                if (center && !isMarginAdded && (marginCounter == marginWidth)) {
                    // margin is finished
                    isMarginAdded = true;
                    column        = 0; // reset column
                }

                uint8_t dot = 0; // default

                if (center && !isMarginAdded) {
                    // still inserting margin => dot=0 (white)
                    column       = 0; // forcibly stay at col=0
                    marginCounter++;
                } else {
                    // actual pixel from bitmap
                    // replicate: dot = bitRead(bitmap[(row*width + column)/8], 7 - ((row*width + column) % 8));
                    uint32_t index     = (row * width + column);
                    uint32_t byteIndex = index / 8;
                    uint8_t  bitPos    = 7 - (index % 8);
                    dot = (bitmap[byteIndex] >> bitPos) & 1; 
                }

                // 10) Expand horizontally by 'scale'
                for (uint8_t columnFat = 0; columnFat < scale; columnFat++) {
                    if (center && !isMarginAdded) {
                        // skip the horizontal scaling once margin is done
                        columnFat = scale; 
                        // effectively break from the horizontal scale loop
                    }

                    // set the next bit (MSB..LSB)
                    byteToSend |= (dot << offset);

                    currentDotNr++;
                    // If we're not using DTR and the pixel is black => count it
                    if (!dtrEnabled_ && dot) {
                        burned++;
                    }

                    // If we've reached the row's total pixel width, set offset=0
                    if (currentDotNr == printedWidth) {
                        offset       = 0;
                        currentDotNr = 0; 
                    }

                    // If offset=0 => we've filled an entire byte => send it
                    if (offset == 0) {
                        // Start a chunk if needed
                        if (bufferFillLevel == 0) {
                            if (rowsInPackage > totalRowsToSend) {
                                rowsInPackage = totalRowsToSend;
                            }
                            initBitmapData(rowsInPackage, bytesPerRow);
                        }

                        sendBitmapByte(byteToSend);

                        offset       = 7;
                        byteToSend   = 0;
                        bufferFillLevel++;

                        // If we've filled the entire chunk => do time delay, reset
                        if (bufferFillLevel == bufferSize) {
                            setDelayBitmap(printedWidth, rowsInPackage, burned);
                            totalRowsToSend   -= rowsInPackage;
                            bufferFillLevel    = 0;
                            burned             = 0;
                        }
                    } else {
                        // Otherwise, just move to next bit
                        offset--;
                    }
                }
            }
        }
    }

    // 11) In the original code snippet, there is no final flush for leftover bytes 
    //     if offset != 7. It's possible to add one, but let's match EXACT logic.
    //
    // If you do want to ensure the last partial bytes are sent, you'd do so here:
    // if (offset != 7) {
    //   // We have a partially filled byte
    //   ...
    // }
    // if (bufferFillLevel % bytesPerRow != 0) {
    //   // We haven't finished the last row chunk
    //   ...
    // }

    // 12) Done. The original code doesn't do any final feed, so we won't either.
    //     If you want to feed after printing, do it in your caller:
    // feed(1);
}

//-------------- PRIVATE: update layout metrics --------------

void Tprinter::update()
{
    charHeight_ = (printMode_ & FONT_B) ? 17 : 24; 
    charWidth_  = (printMode_ & FONT_B) ? 9  : 12;
    widthMax_   = (printMode_ & FONT_B) ? 42 : 32;

    if (printMode_ & DOUBLE_WIDTH) {
        charWidth_ *= 2;
        widthMax_ /= 2;
    }
    if (printMode_ & DOUBLE_HEIGHT) {
        charHeight_ *= 2;
    }

    if (calculateMode_) {
        calculatePrintTime();
    } else {
        print_time_ = (charHeight_ * oneDotHeight_printTime_);
        feed_time_  = (charHeight_ + interlineHeight_) * oneDotHeight_feedTime_;
    }
}
