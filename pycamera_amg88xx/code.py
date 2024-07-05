import adafruit_amg88xx
import adafruit_fancyled.adafruit_fancyled as fancy
import adafruit_pycamera
import bitmaptools
import displayio
import math

pycam = adafruit_pycamera.PyCamera()
amg = adafruit_amg88xx.AMG88XX(pycam._i2c)

# AMG8833 has a 8x8 sensor
SENSOR_SIZE_X = 8
SENSOR_SIZE_Y = 8

# AMG8833 reports temperature values within range of 0-80C
SENSOR_MIN_C = 0
SENSOR_MAX_C = 80

# Allocate all buffers
thermal_overlay = displayio.Bitmap(pycam.camera.width, pycam.camera.height, 65535)
combined_view = displayio.Bitmap(pycam.camera.width, pycam.camera.height, 65535)
thermal_raw = displayio.Bitmap(SENSOR_SIZE_X,SENSOR_SIZE_Y,65535)

# Without interpolation, thermal_mapped is the same size
thermal_mapped = displayio.Bitmap(thermal_raw.width,thermal_raw.height,65535)

# Build a color lookup table that covers the color range commonly
# used to convey temperature, conveniently half of hue wheel in
# HSV (hue/saturation/value) colorspace.
#
# Coolest = blue -> purple -> red -> orange -> yellow = hottest
print("Building color lookup table...")

# With an 8x8 sensor array, and in the absence of interpolation, we would
# never need more than 8*8=64 distinct colors.
COLORS=64
color_lookup=[] # Can I preallocate it to be COLORS in size?

for color in range(COLORS):
    # We want hue from +1/6 to -1/3
    # Scale number to between 0.5 and 0.0
    # Then drop by 1/3
    hue = (color/(COLORS*2))-(1/3)
    # Obtain hue from HSV spectrum, then convert to RGB with pack()
    rgb = fancy.CHSV(hue).pack()
    # Extract each color channel and drop lower bits
    red =   (rgb & 0xFF0000) >> 19
    green_h3 = (rgb & 0x00FF00) >> 13
    green_l3 = (rgb & 0x003800) >> 11
    blue =  (rgb & 0x0000FF) >> 3
    # Pack bits into RGB565_SWAPPED format
    color_lookup.append((red << 3) + (green_h3) + (green_l3 << 13) + (blue << 8))

print("Starting!")

while True:
    # Multiply so we can work in integer space via bitmap buffer.
    # Also find min & max so we know range across them.
    max_now = 0
    min_now = SENSOR_MAX_C*100
    scan_y = 0
    for row in amg.pixels:
        scan_x = 0
        for temp in row:
            # Turns 30.42 degrees C to 3042
            temp_multiplied = math.floor(temp*100)
            thermal_raw[scan_x,scan_y] = temp_multiplied
            max_now = max(max_now, temp_multiplied)
            min_now = min(min_now, temp_multiplied)
            scan_x += 1
        scan_y += 1
    range_now = max_now - min_now

    # Clear overlay to black
    thermal_overlay.fill(0)

    # Proceed only if we actually have a range of sensor values.
    if (range_now > 0):
        # TODO: interplate 8x8 thermal_raw array to something bigger
        # https://learn.adafruit.com/adafruit-amg8833-8x8-thermal-camera-sensor/raspberry-pi-thermal-camera

        # Given the min/max values, we can map raw values across range of
        # available values in color lookup table
        for y in range(thermal_raw.height):
            for x in range(thermal_raw.width):
                raw = thermal_raw[x,y]
                raw = raw - min_now
                raw = raw/range_now
                mapped = math.floor(raw*(COLORS-1))
                thermal_mapped[x,y] = color_lookup[mapped]

        # Transfer thermal data, mapped via color table, into thermal overlay.
        y_offset = math.floor((pycam.display.height - pycam.camera.height)/2)
        x_offset = math.floor((pycam.display.width - pycam.camera.width)/2)
        x_block_size = math.floor(pycam.display.width/SENSOR_SIZE_X)
        y_block_size = math.floor(pycam.display.height/SENSOR_SIZE_Y)
        for y in range(0,pycam.camera.height,4):
            for x in range(0,pycam.camera.width,4):
                # Adjust for physical sensor orientation and field of view
                x_lookup = (y+y_offset)//y_block_size
                y_lookup = SENSOR_SIZE_X-1-(x//x_block_size)
                thermal_overlay[x,y] = thermal_mapped[x_lookup,y_lookup]

    # Blend camera view with thermal overlay, and blit to screen
    bitmaptools.alphablend(
        combined_view, pycam.continuous_capture(), thermal_overlay, displayio.Colorspace.RGB565_SWAPPED
    )
    pycam.blit(combined_view)
