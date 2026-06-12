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
Waveshare ESP32-S3-POE-ETH-8DI-8DO

This class provides information and helper classes for a CircuitPython sketch
running on a Waveshare ESP32-S3-POE-ETH-8DI-8DO controller designed for
industrial use. It's an ESP32-S3 surrounded by a lot of electrically isolated
interface components all inside a DIN rail mountable enclosure.
https://www.waveshare.com/esp32-s3-poe-eth-8di-8do.htm
"""

import board

# Base libraries and why they were introduced
import pwmio  # To pulse piezo buzzer
import keypad  # To debounce input ports

# Additional librarie files from the Adafruit library bundle
import neopixel  # neopixel.mpy for rgb_led class


class board2:
    """
    Until there is CircuitPython prebuilt binary for this hardware, we would
    have to use one built for some other piece of ESP32-S3 hardware such as
    espressif_esp32s3_devkitc_1_n8r8. Because the hardware does not match,
    the predefined pins of 'board' class would not match, either.

    This 'board2' class defines pins in terms of board.IOXX assuming XX
    matches the Espressif ESP32-S3 pinout numbers. The items are sorted by
    IO pin number which might not be the most intuitive, but it is the best
    way to clearly see when there are multiple names for the same pin.

    It feels like Python would have given us a more elegant way to extend
    the 'board' class but I'm too much of a Python novice to know of it.
    """

    IN1 = board.IO4
    IN2 = board.IO5
    IN3 = board.IO6
    IN4 = board.IO7
    IN5 = board.IO8
    IN6 = board.IO9
    IN7 = board.IO10
    IN8 = board.IO11
    RGB_LED = board.IO38  # Single WS2812 (or compatible) RGB LED
    NEOPIXEL = board.IO38  # "NeoPixel" is Adafruit branding for WS2812
    BUZZER = board.IO46  # Piezo buzzer for audio feedback.


class rgb_led:
    """
    A RGB LED is on board and available to display diagonistic information
    located next to the USB-C port. It is a WS2812-style individually
    addressible LED that requires only a single data pin to control RGB
    channels on a string of LEDs. In this case there seems to be only a single
    unit so not much of a 'string' but at least it only takes one GPIO port.
    """

    def __init__(self, brightness: float = 1.0, auto_write: bool = True):
        """
        Creates a NeoPixel class to communicate with a single pixel over the
        correct pin and color order.
        Brightness defaults to full bright and can be reduced.
        Auto write defaults to on (True) but can be turned off (False).
            If turned off, show() must be explicitly called for an update.
        """
        self.pixel = neopixel.NeoPixel(
            board2.NEOPIXEL,
            1,
            bpp=3,
            brightness=brightness,
            auto_write=auto_write,
            pixel_order=neopixel.RGB,
        )

    def rgb(self, rgb_tuple):
        """
        Sets the pixel to specified color specified as a tuple with three
        values 0-255 for red, green, blue channel.
        """
        self.pixel[0] = rgb_tuple

    def show(self):
        self.pixel.show()


class buzzer:
    """
    A piezo buzzer is on board and available to generate audio feedback.
    """

    # Predefine frequencies for one octave from middle C to tenor C
    # https://en.wikipedia.org/wiki/Piano_key_frequencies
    middle_C = 261
    middle_D = 294
    middle_E = 329
    middle_F = 349
    middle_G = 392
    middle_A = 440
    middle_B = 493
    tenor_C = 523

    def __init__(self):
        """
        Creates a PWM class with 50% duty cycle and variable frequency
        """

        # Duty cycle is specified as a 16-bit value. 0 is 0% and 65535 is 100%
        # so 2^15 or 32768 represents 50% duty cycle
        self.duty50 = 2**15

        # Create the PWM object running at zero duty cycle (no sound) until
        # tone() is called. Not sure if frequency is important when duty cycle
        # is zero but set it to middle_C just in case.
        # variable_frequency must be TRUE for us to adjust tone afterwards.
        self.buzz = pwmio.PWMOut(
            board2.BUZZER,
            duty_cycle=0,
            frequency=self.middle_C,
            variable_frequency=True,
        )

    def tone(self, frequency):
        """
        Turn the buzzer on to 50% duty cycle and specified frequency
        """
        self.buzz.frequency = frequency
        self.buzz.duty_cycle = self.duty50

    def stop(self):
        """
        Stop the buzzer by turning duty cycle to 0%
        """
        self.buzz.duty_cycle = 0


class digital_inputs:
    """
    Eight digital input ports with bidirectional optocoupler isolation are
    connected to eight ESP32-S3 GPIO pins. Uses the CircuitPython keypad class
    to handle debouncing.
    """

    def __init__(self):
        self.input_ports = keypad.Keys(
            (
                board2.IN1,
                board2.IN2,
                board2.IN3,
                board2.IN4,
                board2.IN5,
                board2.IN6,
                board2.IN7,
                board2.IN8,
            ),
            value_when_pressed=False,
            pull=True,
        )
        self.input_value: int = 0x00

    def update(self) -> int:
        previous_value = self.input_value
        input_event = self.input_ports.events.get()
        while input_event:
            bit_mask = 0x1 << input_event.key_number
            if input_event.pressed:
                self.input_value |= bit_mask
            else:
                self.input_value &= ~bit_mask
            input_event = self.input_ports.events.get()
        if self.input_value != previous_value:
            # print(f"New value {self.input_value:#04X}") # Debug
            # TODO: Raise changed event
            pass
        return self.input_value

    def get_value(self, port_number: int) -> bool:
        if port_number in range(1, 9):
            bit_mask = 0x1 << (port_number - 1)
            return (self.input_value & bit_mask) != 0
        else:
            raise ValueError("Port number must be 1 through 8 inclusive")

    def get_inputs_as_byte(self) -> int:
        return self.input_value
