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
interpolation_grid = np.zeros((interpolation_size, interpolation_size))
thermal_overlay_repeated = np.zeros((interpolation_size*4,interpolation_size*4), dtype=np.uint16)
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
    thermal_indices = np.array(np.clip(interpolation_grid * THERMAL_COLORS,0,THERMAL_COLORS-1), dtype=np.uint8)

    # This utterly inscrutible chunk of code generates an array of colors as
    # our thermal overlay. It maps just-calculated thermal color indices to
    # actual colors in in the thermal color lookup list.
    #
    # Earlier version may be easier to understand conceptually:
    #
    #   for y:
    #     for x:
    #       thermal_overlay[x,y] = thermal_color_lookup[thermal_indices[x,y]]
    #
    # But that nested loop ran order of magnitude slower than code below:
    #
    #   1. Flatten square array of thermal indices to a linear list.
    #   2. Generate a list comprehension using that array as index for color.
    #      https://docs.python.org/3/tutorial/datastructures.html#list-comprehensions
    #      (Personally dislike list comprehension on code readability grounds,
    #       using it for the sake of performance, under protest.)
    #   3. Create a NumPy array from the list comprehension.
    #   4. Rearrange that one-dimensional array back into a square.
    thermal_overlay = np.array(
        [thermal_color_lookup[i] for i in \
            thermal_indices.reshape((interpolation_size**2))], \
        dtype=np.uint16) \
        .reshape((interpolation_size, interpolation_size))

    mapped = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Grab a snapshot from OV5640 camera
    bitmaptools.blit(output_bitmap, pycam.continuous_capture(), 0, 32)

    blit = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Expand thermal overlay by 4X along both axis in preparation for bulk transfer.
    # On full NumPy this can be accomplished via
    #
    #   thermal_overlay_repeated = np.repeat(np.repeat(thermal_overlay,4,axis=0),4,axis=1)
    #
    # But there is no ulab.numpy.repeat() so this copies bits the long way.
    thermal_overlay_repeated[::4,::4] = thermal_overlay
    thermal_overlay_repeated[2::4,::4] = thermal_overlay
    thermal_overlay_repeated[1::2,::4] = thermal_overlay_repeated[::2,::4]
    thermal_overlay_repeated[:,2::4] = thermal_overlay_repeated[:,::4]
    thermal_overlay_repeated[:,1::2] = thermal_overlay_repeated[:,::2]

    # Generate a NumPy view of OV5640 camera sensor data bitmap
    output_bitmap_np = np.frombuffer(output_bitmap, dtype=np.uint16).reshape((240,240))

    # Bulk transfer thermal overlay
    output_bitmap_np[::4,::4] = thermal_overlay_repeated

    grid = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Send results of all our hard work to screen
    pycam.blit(output_bitmap,0,0)

    refresh = time.monotonic_ns() >> 10  # Performance measurement timestamp

    # Print performance timer deltas
    print("read {} scaled {} interpolated {} mapped {} blit {} grid {} refresh {} total {}".format(read-start, scaled-read, interpolate-scaled, mapped-interpolate, blit-mapped, grid-blit, refresh-grid, refresh-start))
