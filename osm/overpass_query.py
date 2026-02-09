# import requests

# OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# def query_osm_metadata(bbox):
#     west, south, east, north = bbox

#     query = f"""
#     [out:json];
#     (
#       node({south},{west},{north},{east})[amenity];
#       node({south},{west},{north},{east})[shop];
#       node({south},{west},{north},{east})[highway];
#       node({south},{west},{north},{east})[public_transport];
#     );
#     out tags;
#     """

#     r = requests.post(OVERPASS_URL, data=query)

#     print(r)

#     if r.status_code != 200:
#         raise Exception(f"Overpass API error: {r.reason}")
    
#     data = r.json()["elements"]

#     metadata = {
#         "amenity": [],
#         "shop": [],
#         "highway": [],
#         "public_transport": []
#     }

#     for el in data:
#         tags = el.get("tags", {})
#         for key in metadata:
#             if key in tags:
#                 metadata[key].append(tags[key])

#     return {
#         "counts": {k: len(v) for k, v in metadata.items()},
#         "types": {k: list(set(v)) for k, v in metadata.items()}
#     }

import requests, json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json];
(
  node(around:500,{lat},{lon})["amenity"];
  node(around:500,{lat},{lon})["shop"];
  node(around:500,{lat},{lon})["highway"];
  node(around:500,{lat},{lon})["public_transport"];
);
out center;
"""

def fetch_metadata(lat, lon):
    q = QUERY.format(lat=lat, lon=lon)
    r = requests.post(OVERPASS_URL, data=q, timeout=60)
    r.raise_for_status()
    # return r.json()

    data = r.json()["elements"]

    print(f"Fetched {len(data)} elements for ({lat}, {lon})")
    print(data[:5])  # Print first 5 elements for debugging

    metadata = {
        "amenity": [],
        "shop": [],
        "highway": [],
        "public_transport": []
    }

    for el in data:
        tags = el.get("tags", {})
        print(tags)
        for key in metadata:
            if key in tags:
                metadata[key].append(tags[key])

    return {
        "counts": {k: len(v) for k, v in metadata.items()},
        "types": {k: list(set(v)) for k, v in metadata.items()}
    }

