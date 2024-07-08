# MIT License

# Copyright (c) 2024 Roger Cheng

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Thermal Memento
============================================================
Adafruit's Memento (a.k.a. PyCamera) working with AMG8833 thermal camera
by rendering a thermal overlay on top of Memento's camera viewfinder.

Memento camera: https://www.adafruit.com/product/5420

AMG8833 breakout board: https://www.adafruit.com/product/3538

Created on CircuitPython 9.0.5
"""

import adafruit_amg88xx
import adafruit_fancyled.adafruit_fancyled as fancy
import adafruit_pycamera
import bitmaptools
import displayio
import time
from ulab import numpy as np

pycam = adafruit_pycamera.PyCamera()
amg = adafruit_amg88xx.AMG88XX(pycam._i2c)

# AMG8833 has a 8x8 sensor
SENSOR_SIZE = 8
interpolation_size = (SENSOR_SIZE*2)-1

# Palette of colors representing thermal range
THERMAL_COLORS = 64
THERMAL_FADE = 0.1

# Allocate memory for data structures
thermal_sensor_data = np.array(range(SENSOR_SIZE**2)).reshape((SENSOR_SIZE, SENSOR_SIZE))
interpolation_grid = np.array(range(interpolation_size**2)).reshape((interpolation_size, interpolation_size)) / (interpolation_size**2)
thermal_overlay = np.array(range(interpolation_size**2),dtype=np.uint16).reshape((interpolation_size, interpolation_size))
output_bitmap = displayio.Bitmap(pycam.display.width, pycam.display.height, 65535)
thermal_color_lookup = [] # How to pre-allocate to THERMAL_COLORS?

# Build a color palette that covers the color range commonly
# used to convey temperature, conveniently half of hue wheel in
# HSV (hue/saturation/value) colorspace.
#
# Coolest = blue -> purple -> red -> orange -> yellow = hottest
print("Building color lookup table...")
for color in range(THERMAL_COLORS):
    color_fraction = color/THERMAL_COLORS
    if color_fraction < THERMAL_FADE:
        # Fade from blue to black
        hue = -1/3
        saturation = 1.0
        value = (color_fraction/THERMAL_FADE)
    elif color_fraction > (1-THERMAL_FADE):
        # Glow from yellow to white
        hue = 1/6
        fade_fraction = color_fraction - (1-THERMAL_FADE)
        saturation = (THERMAL_FADE-fade_fraction)/THERMAL_FADE
        value = 1.0
    else:
        # Full saturation and full value, but with hue somewhere in the range
        # of blue -> purple -> red -> orange -> yellow
        # We want hue from +1/6 to -1/3
        # Scale number to between 0.5 and 0.0
        # Then drop by 1/3
        hue_range = 1-(THERMAL_FADE*2)
        hue = ((color_fraction-THERMAL_FADE)/(hue_range*2))-(1/3)
        saturation = 1.0
        value = 1.0

    # Obtain hue from HSV spectrum, then convert to RGB with pack()
    rgb = fancy.CHSV(hue, saturation, value).pack()

    # Extract each color channel and drop lower bits
    red =   (rgb & 0xFF0000) >> 19
    green_h3 = (rgb & 0x00FF00) >> 13
    green_l3 = (rgb & 0x003800) >> 11
    blue =  (rgb & 0x0000FF) >> 3
    # Pack bits into RGB565_SWAPPED format
    thermal_color_lookup.append((red << 3) + (green_h3) + (green_l3 << 13) + (blue << 8))

print("Starting!")

# Switch camera to black & white mode so all colors mean temperature
pycam.effect = pycam.effects.index("B&W")

while True:
    start = time.monotonic_ns() >> 10 # Performance measurement timestamp

    # Each call to 'pixels' property getter triggers I2C operation to read from sensor.
    sensor_pixels = amg.pixels

    read = time.monotonic_ns() >> 10  # Performance measurement timestamp

    thermal_sensor_data = np.array(sensor_pixels)

    # Scale temperature readings to values between 0.0 and 1.0
    thermal_sensor_max  = np.max(thermal_sensor_data)
    thermal_sensor_min  = np.min(thermal_sensor_data)
    thermal_sensor_data = (thermal_sensor_data-thermal_sensor_min) / (thermal_sensor_max - thermal_sensor_min)

    scaled = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # interplate 8x8 thermal_raw array to 15x15 thanks to
    # https://learn.adafruit.com/improved-amg8833-pygamer-thermal-camera
    interpolation_grid[::2, ::2] = thermal_sensor_data

    """2x bilinear interpolation to upscale the sensor data array; by @v923z
    and @David.Glaude."""
    interpolation_grid[1::2, ::2] = thermal_sensor_data[:-1, :]
    interpolation_grid[1::2, ::2] += thermal_sensor_data[1:, :]
    interpolation_grid[1::2, ::2] /= 2
    interpolation_grid[::, 1::2] = interpolation_grid[::, :-1:2]
    interpolation_grid[::, 1::2] += interpolation_grid[::, 2::2]
    interpolation_grid[::, 1::2] /= 2

    interpolate = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Scale interpolated data to range of color palette index
    thermal_indices = np.array(np.clip(interpolation_grid * THERMAL_COLORS,0,THERMAL_COLORS-1), dtype=np.int8)

    # Then map color indices to colors in the palette
    # TODO: Figure out how to do this faster via numpy.
    for y in range(thermal_overlay.shape[0]):
        for x in range(thermal_overlay.shape[1]):
            thermal_overlay[x,y] = thermal_color_lookup[thermal_indices[x,y]]

    mapped = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Grab a snapshot from OV5640 camera
    bitmaptools.blit(output_bitmap, pycam.continuous_capture(), 0, 32)

    blit = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Transfer thermal data, mapped via color table, into thermal overlay.
    output_bitmap_np = np.frombuffer(output_bitmap, dtype=np.uint16).reshape((240,240))

    for y in range(0,15,3):
        for x in range(0,15,3):
            output_bitmap_np[x::16,y::16] = thermal_overlay

    grid = time.monotonic_ns() >> 10  # Performance measurement timestamp

    pycam.blit(output_bitmap,0,0)

    refresh = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Print performance timer deltas
    # print("read {} scaled {} interpolated {} mapped {} blit {} grid {} refresh {} total {}".format(read-start, scaled-read, interpolate-scaled, mapped-interpolate, blit-mapped, grid-blit, refresh-grid, refresh-start))
