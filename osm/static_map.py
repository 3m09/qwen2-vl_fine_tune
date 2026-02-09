# import requests, time, os
# from utils.utils import latlon_to_tile

# TILE_URL = "https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=vJEdOzBe3hYvvFnvdRgv"
# HEADERS = {
#     "User-Agent": "AcademicResearch-Qwen2VL/1.0 (2005012@ugrad.cse.buet.ac.bd)"
# }

# def download_tile(lat, lon, zoom=17):
#     x, y = latlon_to_tile(lat, lon, zoom)
#     url = TILE_URL.format(z=zoom, x=x, y=y)

#     os.makedirs(f"tiles/z{zoom}", exist_ok=True)
#     path = f"tiles/z{zoom}/{x}_{y}.png"

#     if os.path.exists(path):
#         return path

#     r = requests.get(url, headers=HEADERS, timeout=30)
#     r.raise_for_status()

#     with open(path, "wb") as f:
#         f.write(r.content)

#     time.sleep(0.2)  # REQUIRED: rate limiting
#     return path

import requests
import time
import os
from PIL import Image
from utils.utils import latlon_to_tile

TILE_URL = "https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=vJEdOzBe3hYvvFnvdRgv"
HEADERS = {
    "User-Agent": "AcademicResearch-Qwen2VL/1.0 (2005012@ugrad.cse.buet.ac.bd)"
}
TILE_SIZE = 256  # Standard for MapTiler/Google/OSM

def download_and_stitch_bbox(lon_min, lat_min, lon_max, lat_max, output_path, zoom=17):
    # 1. Determine tile ranges
    x_start, y_start = latlon_to_tile(lat_max, lon_min, zoom) # Top-left
    x_end, y_end = latlon_to_tile(lat_min, lon_max, zoom)     # Bottom-right

    grid_width = (x_end - x_start) + 1
    grid_height = (y_end - y_start) + 1

    print(f"Creating {grid_width}x{grid_height} tile grid ({grid_width*TILE_SIZE}x{grid_height*TILE_SIZE} px)")

    # 2. Create a blank canvas
    stitched_image = Image.new('RGB', (grid_width * TILE_SIZE, grid_height * TILE_SIZE))

    # 3. Download and paste tiles
    for i, x in enumerate(range(x_start, x_end + 1)):
        for j, y in enumerate(range(y_start, y_end + 1)):
            url = TILE_URL.format(z=zoom, x=x, y=y)
            
            # Simple local cache to avoid re-downloading during debugging
            cache_dir = "tile_cache"
            os.makedirs(cache_dir, exist_ok=True)
            tile_path = os.path.join(cache_dir, f"{zoom}_{x}_{y}.png")

            if not os.path.exists(tile_path):
                try:
                    r = requests.get(url, headers=HEADERS, timeout=30)
                    r.raise_for_status()
                    with open(tile_path, "wb") as f:
                        f.write(r.content)
                    time.sleep(0.1) # Be kind to the API
                except Exception as e:
                    print(f"Error downloading tile {x},{y}: {e}")
                    continue

            # Open tile and paste into canvas
            with Image.open(tile_path) as tile:
                # i is horizontal offset, j is vertical offset
                stitched_image.paste(tile, (i * TILE_SIZE, j * TILE_SIZE))

    # 4. Save the final result
    stitched_image.save(output_path)
    print(f"Success! Image saved to {output_path}")

# Example Usage for a 1km block in Manhattan:
# download_and_stitch_bbox(-74.006, 40.712, -73.996, 40.722, "manhattan_1km.png")