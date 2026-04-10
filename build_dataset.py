import json
from grid.world_grid import generate_world_grid
# from osm.overpass_query import query_osm_metadata
from osm.overpass_query import fetch_pois_overpass
# from osm.static_map import download_tile
from osm.static_map import download_and_stitch_bbox
from osm.geoapify import fetch_pois_in_bbox
from osm.geoapify_maps import download_static_map
from pathlib import Path

def build_dataset(limit=1000):
    grid = generate_world_grid()
    print('generated grid')
    print(f"Total grid cells: {len(grid)}. Processing first {limit} cells...")
    Path("dataset/metadata").mkdir(parents=True, exist_ok=True)

    for i, cell in enumerate(grid[:limit]):
        lat = cell["center_lat"]
        lon = cell["center_lon"]

        # metadata = query_osm_metadata(cell["bbox"])
        image_name = "dataset/images/{}.png".format(i)
        download_static_map(cell["bbox"][0], cell["bbox"][1], cell["bbox"][2], cell["bbox"][3], image_name)
        # metadata = fetch_metadata(lat, lon)
        pois = fetch_pois_overpass(
            cell["bbox"][0], cell["bbox"][1],
            cell["bbox"][2], cell["bbox"][3],
            # categories="amenity,commercial,tourism,catering,highway"
        )
        # pois = fetch_pois(
        #     cell["bbox"][0], cell["bbox"][1],
        #     cell["bbox"][2], cell["bbox"][3],
        # )
        # image_name = download_tile(lat, lon)

        record = {
            "image": image_name,
            "center_lat": lat,
            "center_lon": lon,
            "bbox": cell["bbox"],
            "unique_categories": list(set(cat for poi in pois for cat in poi["category"])), 
            "poi_count_per_category": {
                cat: sum(1 for poi in pois if cat in poi["category"])
                for cat in set(cat for poi in pois for cat in poi["category"])
            },
            "poi_count": len(pois),
            "pois": pois
        }

        with open(f"dataset/metadata/{i}.json", "w") as f:
            json.dump(record, f, indent=2)

if __name__ == "__main__":
    build_dataset(limit=2000)
