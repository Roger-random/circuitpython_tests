"""
MIT License

Copyright (c) 2026 Roger Cheng

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
Waveshare ESP32-S3-POE-ETH-8DI-8DO Exploration

On the wiki page for this product, Waveshare published example 01_MAIN_WIFI_AP
which is an "Everything App" that exercises all of the functionality
on board. It sets up a WiFi access point and, once connected, serves up a HTML
control panel that lets the user do things like toggle output pins.
https://www.waveshare.com/wiki/ESP32-S3-POE-ETH-8DI-8DO#01_MAIN_WIFI_AP

01_MAIN_WIFI_AP is an Arduino sketch and quite a large one. This project uses
CircuitPython and will not replicate the full set of functionality. I'm only
planning to play with features that have a specific interest to me. I welcome
contribution by others who wish to fill in the gaps.

Code within will be one of three catagories:
1.  Infrastructure code that sets up generic support for a peripheral on board.
2.  Configuration code that adapts generic infrastructure for a use.
3.  Application code that performs a task.

As an example, the section that serves up a HTML control panel will have:
1.  Infrastructure code that sets up WiFi networking stack, then runs a web
    server upon that networking stack.
2.  Configuration code for the IP address of that web server, and the path for
    the HTML assets to be served.
3.  Server-side code that listens for messages sent by the HTML control panel
    running on user browser, and makes hardware calls in response.

Reusability by other projects:
1.  Infrastructure code should be reusable in other projects without changes.
2.  Configuration code can be copied and edited for use in other projects.
3.  Application code will be different for other projects.
"""

"""
As of this writing there is no CircuitPython built binary specific to the
ESP32-S3-POE-ETH-8DI-8DO. I'm using the binary built for one of the ESP32-S3
dev boards and it seems to be good enough to get started with exploration.
https://circuitpython.org/board/espressif_esp32s3_devkitc_1_n8r8/

Since this is a dev board, there aren't many predefined pins. dir(board) shows
just NEOPIXEL, RX, and TX. Serial RX(44) and TX(43) seems to match but NEOPIXEL
differs. The dev board has it on IO48 and ESP32-S3-POE-ETH-8DI-8DO uses IO38.

I've defined a supporting 'board2' class to label such pins. If I embark on a
project to provide actual CircuitPython prebuilt binary support, 'board2' is
what 'board' will look like.
"""

import time

from esp32_s3_poe_eth_8di_8do import rgb_led
from esp32_s3_poe_eth_8di_8do import digital_outputs

led = rgb_led()

dout = digital_outputs()

counter = 0


def increment_counter(counter: int) -> int:
    if counter == 255:
        counter = 0
    else:
        counter += 1
    print(counter)
    for bit in range(8):
        val = ((counter >> bit) & 0x1) == 0
        dout.open_output_circuit(bit, val)
    return counter


while True:
    led.rgb((16, 0, 0))
    time.sleep(0.5)
    led.rgb((0, 0, 0))
    counter = increment_counter(counter)
    time.sleep(0.5)
