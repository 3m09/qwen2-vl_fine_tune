# google_map_downloader.py
import requests
import math
import os
import time
from pathlib import Path

API_KEY      = "REMOVED_API_KEY"
STATIC_URL   = "https://maps.googleapis.com/maps/api/staticmap"
OUTPUT_DIR   = "g_dataset/images"
IMG_SIZE     = 640          # max without special approval
SCALE        = 2            # gives 1280x1280 effective resolution
MAP_TYPE     = "roadmap"    # roadmap | satellite | terrain | hybrid


def bbox_to_center_zoom(lon_min, lat_min, lon_max, lat_max, img_size=640, scale=2):
    """
    Google Static Maps uses center+zoom, not bbox.
    This computes the tightest zoom level that fits the bbox.
    """
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    # Effective pixels after scale factor
    pixels = img_size * scale

    # Find zoom level where bbox fits within image
    # Google tiles are 256px, world width = 256 * 2^zoom px
    for zoom in range(21, 0, -1):
        world_px = 256 * (2 ** zoom)

        # Longitude span → pixels
        lon_span_px = (lon_max - lon_min) / 360.0 * world_px

        # Latitude span → pixels (Mercator projection)
        def lat_to_mercator(lat):
            sin_lat = math.sin(math.radians(lat))
            return math.log((1 + sin_lat) / (1 - sin_lat)) / 2

        lat_span_px = (lat_to_mercator(lat_max) - lat_to_mercator(lat_min)) / (2 * math.pi) * world_px

        if lon_span_px <= pixels and lat_span_px <= pixels:
            return center_lat, center_lon, zoom

    return center_lat, center_lon, 1


def download_map(lon_min, lat_min, lon_max, lat_max, output_path):
    """Download a static map image for the given bbox."""
    center_lat, center_lon, zoom = bbox_to_center_zoom(
        lon_min, lat_min, lon_max, lat_max, IMG_SIZE, SCALE
    )

    params = {
        "center":   f"{center_lat},{center_lon}",
        "zoom":     zoom,
        "size":     f"{IMG_SIZE}x{IMG_SIZE}",
        "scale":    SCALE,
        "maptype":  MAP_TYPE,
        "key":      API_KEY,
    }

    response = requests.get(STATIC_URL, params=params)

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"  ✓ Saved {output_path}  (center={center_lat:.5f},{center_lon:.5f} zoom={zoom})")
        return True
    else:
        print(f"  ✗ Error {response.status_code}: {response.text[:200]}")
        return False


def download_grid(grid: list, output_dir: str = OUTPUT_DIR):
    """
    Downloads map images for all cells in the grid.
    grid is a list of dicts with bbox: (lon_min, lat_min, lon_max, lat_max)
    """
    os.makedirs(output_dir, exist_ok=True)

    for i, cell in enumerate(grid):
        output_path = Path(output_dir) / f"{i}.png"

        if output_path.exists():
            print(f"[{i}] Already exists, skipping.")
            continue

        bbox = cell["bbox"]
        lon_min, lat_min, lon_max, lat_max = bbox

        print(f"[{i}] Downloading map...")
        download_map(lon_min, lat_min, lon_max, lat_max, str(output_path))

        time.sleep(0.1)   # 10 req/s well within quota


if __name__ == "__main__":
    # Test with a single cell
    test_grid = [{
        "bbox": (-74.006, 40.712, -74.003, 40.715)
    }]
    download_grid(test_grid)