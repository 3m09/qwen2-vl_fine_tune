import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def query_osm_metadata(bbox):
    west, south, east, north = bbox

    query = f"""
    [out:json];
    (
      node({south},{west},{north},{east})[amenity];
      node({south},{west},{north},{east})[shop];
      node({south},{west},{north},{east})[highway];
      node({south},{west},{north},{east})[public_transport];
    );
    out tags;
    """

    r = requests.post(OVERPASS_URL, data=query)
    data = r.json()["elements"]

    metadata = {
        "amenity": [],
        "shop": [],
        "highway": [],
        "public_transport": []
    }

    for el in data:
        tags = el.get("tags", {})
        for key in metadata:
            if key in tags:
                metadata[key].append(tags[key])

    return {
        "counts": {k: len(v) for k, v in metadata.items()},
        "types": {k: list(set(v)) for k, v in metadata.items()}
    }
