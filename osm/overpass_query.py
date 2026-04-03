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

# import requests, json

# OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# QUERY = """
# [out:json];
# (
#   node(around:500,{lat},{lon})["amenity"];
#   node(around:500,{lat},{lon})["shop"];
#   node(around:500,{lat},{lon})["highway"];
#   node(around:500,{lat},{lon})["public_transport"];
# );
# out center;
# """

# def fetch_metadata(lat, lon):
#     q = QUERY.format(lat=lat, lon=lon)
#     r = requests.post(OVERPASS_URL, data=q, timeout=60)
#     r.raise_for_status()
#     # return r.json()

#     data = r.json()["elements"]

#     print(f"Fetched {len(data)} elements for ({lat}, {lon})")
#     print(data[:5])  # Print first 5 elements for debugging

#     metadata = {
#         "amenity": [],
#         "shop": [],
#         "highway": [],
#         "public_transport": []
#     }

#     for el in data:
#         tags = el.get("tags", {})
#         print(tags)
#         for key in metadata:
#             if key in tags:
#                 metadata[key].append(tags[key])

#     return {
#         "counts": {k: len(v) for k, v in metadata.items()},
#         "types": {k: list(set(v)) for k, v in metadata.items()}
#     }

import requests
import time

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",   # Mirror 1
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",  # Mirror 2
]

def fetch_pois_overpass(lon_min, lat_min, lon_max, lat_max, timeout=60):
    query = f"""
    [out:json][timeout:{timeout}][maxsize:33554432];
    (
      node["name"]["amenity"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["name"]["shop"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["name"]["tourism"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["name"]["leisure"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["name"]["aeroway"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["name"]["railway"]({lat_min},{lon_min},{lat_max},{lon_max});
      node["highway"~"bus_stop"]["name"]({lat_min},{lon_min},{lat_max},{lon_max});
    );
    out body;
    """
    
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(3):  # 3 retries per mirror
            try:
                print(f"Trying {mirror} (attempt {attempt+1})")
                response = requests.post(
                    mirror,
                    data={"data": query},
                    timeout=timeout + 10  # requests-level timeout slightly higher
                )
                response.raise_for_status()
                elements = response.json().get("elements", [])
                print(f"Found {len(elements)} POIs")
                return parse_elements(elements)

            except requests.exceptions.HTTPError as e:
                if response.status_code == 504:
                    wait = (attempt + 1) * 10  # 10s, 20s, 30s
                    print(f"504 timeout. Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    print(f"HTTP error: {e}")
                    break  # Non-timeout error, try next mirror immediately

            except requests.exceptions.Timeout:
                print(f"Request-level timeout. Trying next mirror...")
                break

    print("All mirrors failed.")
    return []


# def parse_elements(elements):
#     print(f"Parsing {len(elements)} elements...")
#     print(elements)
#     pois = []
#     for el in elements:
#         tags = el.get("tags", {})
#         lat = el.get("lat")
#         lon = el.get("lon")
#         if not lat or not lon:
#             continue
#         pois.append({
#             "name": tags.get("name", "Unnamed"),
#             "amenity": tags.get("amenity"),
#             "shop": tags.get("shop"),
#             "tourism": tags.get("tourism"),
#             "highway": tags.get("highway"),
#             "lat": lat,
#             "lon": lon,
#             "osm_id": el.get("id"),
#         })
#     return pois

def parse_elements(elements):
    """
    Returns POIs matching the record structure:
    poi["category"] is always a list, consistent with:
      set(cat for poi in pois for cat in poi["category"])
    """
    # Maps OSM tag keys to human-readable category prefixes
    CATEGORY_TAG_KEYS = ["amenity", "leisure", "shop", "tourism", "aeroway", "railway", "highway"]

    pois = []
    for el in elements:
        if el.get("type") != "node":
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue

        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand") or "Unnamed"

        # Build category list from all relevant OSM tag keys present
        # e.g. amenity=restaurant      -> ["amenity.restaurant"]
        #      railway=station         -> ["railway.station"]
        #      leisure=fitness_centre  -> ["leisure.fitness_centre"]
        category = []
        for key in CATEGORY_TAG_KEYS:
            value = tags.get(key)
            if value:
                category.append(f"{key}.{value}")

        if not category:
            continue  # skip nodes with no recognizable category

        pois.append({
            "name":         name,
            "category":     category,           # list — matches your record structure
            "lat":          lat,
            "lon":          lon,
            "osm_id":       el.get("id"),
            "osm_type":     el.get("type"),
            "address":      tags.get("addr:street"),
            "road_geometry": None               # kept for structural compatibility
        })

    return pois