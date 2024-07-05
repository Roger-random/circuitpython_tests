import adafruit_fancyled.adafruit_fancyled as fancy
import board
import displayio

display = board.DISPLAY

cat_bitmap = displayio.OnDiskBitmap("/images/cutecat_indexed.bmp")

THERMAL_BLOCK_SIZE = 8 # Prefer even numbers
THERMAL_COLORS = 64
THERMAL_FADE = 0.1
thermal_blockmap = displayio.Bitmap(THERMAL_COLORS*THERMAL_BLOCK_SIZE,THERMAL_BLOCK_SIZE,THERMAL_COLORS)
thermal_palette = displayio.Palette(THERMAL_COLORS, dither=False)

tile_grid = displayio.TileGrid(cat_bitmap, pixel_shader=cat_bitmap.pixel_shader)
thermal_grid = displayio.TileGrid(bitmap=thermal_blockmap,
                                  pixel_shader=thermal_palette,
                                  width = display.width//THERMAL_BLOCK_SIZE,
                                  height = display.height//THERMAL_BLOCK_SIZE,
                                  tile_width = THERMAL_BLOCK_SIZE,
                                  tile_height = THERMAL_BLOCK_SIZE)

group = displayio.Group()

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
    thermal_palette[color] = fancy.CHSV(hue, saturation, value).pack()
thermal_palette.make_transparent(0)

thermal_blockmap.fill(0)
for y in range(0,thermal_blockmap.height,2):
    for x in range(0,thermal_blockmap.width,2):
        thermal_blockmap[x,y] = x//THERMAL_BLOCK_SIZE

for y in range(thermal_grid.height):
    y_offset = thermal_grid.width*y
    for x in range(thermal_grid.width):
        thermal_grid[x,y] = 1+(x+y_offset)%(THERMAL_COLORS-1)

group.append(tile_grid)
group.append(thermal_grid)

# Add the Group to the Display
display.root_group = group

# Loop forever so you can enjoy your image
while True:
    pass