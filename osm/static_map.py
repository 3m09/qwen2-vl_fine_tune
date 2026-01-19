import requests
from pathlib import Path

def download_osm_image(
    lat, lon,
    zoom=17,
    size=512,
    out_dir="dataset/images"
):
    url = (
        "https://staticmap.openstreetmap.de/staticmap.php"
        f"?center={lat},{lon}"
        f"&zoom={zoom}"
        f"&size={size}x{size}"
        f"&maptype=mapnik"
    )

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{lat:.5f}_{lon:.5f}.png"
    path = Path(out_dir) / filename

    r = requests.get(url, timeout=30)
    with open(path, "wb") as f:
        f.write(r.content)

    return filename
