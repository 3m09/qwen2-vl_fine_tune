import json
from grid.world_grid import generate_world_grid
from osm.overpass_query import query_osm_metadata
from osm.static_map import download_osm_image
from pathlib import Path

def build_dataset(limit=1000):
    grid = generate_world_grid()
    print('generated grid')
    # Path("dataset/metadata").mkdir(parents=True, exist_ok=True)

    # for i, cell in enumerate(grid[:limit]):
    #     lat = cell["center_lat"]
    #     lon = cell["center_lon"]

    #     metadata = query_osm_metadata(cell["bbox"])
    #     image_name = download_osm_image(lat, lon)

    #     record = {
    #         "image": image_name,
    #         "center_lat": lat,
    #         "center_lon": lon,
    #         "bbox": cell["bbox"],
    #         "poi_counts": metadata["counts"],
    #         "poi_types": metadata["types"]
    #     }

    #     with open(f"dataset/metadata/{image_name}.json", "w") as f:
    #         json.dump(record, f, indent=2)

if __name__ == "__main__":
    build_dataset(limit=500)
