import adafruit_fancyled.adafruit_fancyled as fancy
import board
import displayio
import gc

display = board.DISPLAY

# print(gc.mem_free())

cat_bitmap = displayio.OnDiskBitmap("/images/cutecat_indexed.bmp")

THERMAL_COLORS = 128
THERMAL_FADE = 0.1
thermal_blockmap = displayio.Bitmap(THERMAL_COLORS,1,THERMAL_COLORS)
thermal_palette = displayio.Palette(THERMAL_COLORS, dither=False)

tile_grid = displayio.TileGrid(cat_bitmap, pixel_shader=cat_bitmap.pixel_shader)
thermal_grid = displayio.TileGrid(bitmap=thermal_blockmap, pixel_shader=thermal_palette)

group = displayio.Group()

for color in range(THERMAL_COLORS):
    hue = 1.0
    saturation = 1.0
    value = 1.0
    color_fraction = color/THERMAL_COLORS
    if color_fraction < THERMAL_FADE:
        # Fade from blue to black
        hue = -1/3
        value = (color_fraction/THERMAL_FADE)
    elif color_fraction > (1-THERMAL_FADE):
        # Glow from yellow to white
        hue = 1/6
        fade_fraction = color_fraction - (1-THERMAL_FADE)
        saturation = (THERMAL_FADE-fade_fraction)/THERMAL_FADE
    else:
        # Full saturation and full value, but with hue somewhere in the range
        # of blue -> purple -> red -> orange -> yellow
        # We want hue from +1/6 to -1/3
        # Scale number to between 0.5 and 0.0
        # Then drop by 1/3
        hue_range = 1-(THERMAL_FADE*2)
        hue = ((color_fraction-THERMAL_FADE)/(hue_range*2))-(1/3)

    # Obtain hue from HSV spectrum, then convert to RGB with pack()
    thermal_palette[color] = fancy.CHSV(hue, saturation, value).pack()
    thermal_blockmap[color] = color

group.append(tile_grid)
group.append(thermal_grid)

# Add the Group to the Display
display.root_group = group

# Loop forever so you can enjoy your image
while True:
    pass