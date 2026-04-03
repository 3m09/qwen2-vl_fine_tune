# google_poi_fetcher.py
import requests
import math
import time
import os
import json
from pathlib import Path

API_KEY    = "REMOVED_API_KEY"
PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
OUTPUT_DIR = "dataset/metadata"

# ── Valid Table A types only ───────────────────────────────────────────────────
INCLUDED_TYPES = [
    # Automotive
    "car_dealer", "car_rental", "car_repair", "car_wash", "ebike_charging_station", 
    "electric_vehicle_charging_station", "gas_station", "parking", "parking_garage", 
    "parking_lot", "rest_stop", "tire_shop", "truck_dealer",

    # Business
    "business_center", "corporate_office", "coworking_space", "farm", 
    "manufacturer", "ranch", "supplier", "television_studio",

    # Culture
    "art_gallery", "art_museum", "art_studio", "auditorium", "castle", 
    "cultural_landmark", "fountain", "historical_place", "history_museum", 
    "monument", "museum", "performing_arts_theater", "sculpture",

    # Education
    "academic_department", "educational_institution", "library", "preschool", 
    "primary_school", "research_institute", "school", "secondary_school", "university",

    # Entertainment and Recreation
    "adventure_sports_center", "amphitheatre", "amusement_center", "amusement_park", 
    "aquarium", "banquet_hall", "barbecue_area", "botanical_garden", "bowling_alley", 
    "casino", "childrens_camp", "city_park", "comedy_club", "community_center", 
    "concert_hall", "convention_center", "cultural_center", "cycling_park", 
    "dance_hall", "dog_park", "event_venue", "ferris_wheel", "garden", "hiking_area", 
    "historical_landmark", "indoor_playground", "internet_cafe", "karaoke", 
    "live_music_venue", "marina", "miniature_golf_course", "movie_rental", 
    "movie_theater", "national_park", "night_club", "observation_deck", "off_roading_area", 
    "opera_house", "paintball_center", "park", "philharmonic_hall", "picnic_ground", 
    "planetarium", "plaza", "roller_coaster", "tourist_attraction", "video_arcade", 
    "vineyard", "visitor_center", "water_park", "wedding_venue", "wildlife_park", 
    "wildlife_refuge", "zoo",

    # Facilities
    "public_bath", "public_bathroom", "stable",

    # Finance
    "accounting", "atm", "bank",

    # Food and Drink (Includes broad categories and specific cuisines)
    "acai_shop", "afghani_restaurant", "african_restaurant", "american_restaurant", 
    "argentinian_restaurant", "asian_fusion_restaurant", "asian_restaurant", 
    "australian_restaurant", "austrian_restaurant", "bagel_shop", "bakery", 
    "bangladeshi_restaurant", "bar", "bar_and_grill", "barbecue_restaurant", 
    "basque_restaurant", "bavarian_restaurant", "beer_garden", "dessert_restaurant", 
    "dessert_shop", "dim_sum_restaurant", "diner", "dog_cafe", "donut_shop", 
    "dumpling_restaurant", "dutch_restaurant", "eastern_european_restaurant", 
    "ethiopian_restaurant", "european_restaurant", "falafel_restaurant", 
    "family_restaurant", "fast_food_restaurant", "filipino_restaurant", 
    "fine_dining_restaurant", "moroccan_restaurant", "noodle_shop", 
    "north_indian_restaurant", "oyster_bar_restaurant", "pakistani_restaurant", 
    "pastry_shop", "persian_restaurant", "peruvian_restaurant", "pizza_delivery", 
    "pizza_restaurant", "polish_restaurant", "portuguese_restaurant", "pub", 
    "ramen_restaurant", "restaurant", "romanian_restaurant", "russian_restaurant",

    # Geographical Areas
    "administrative_area_level_1", "administrative_area_level_2", "country", 
    "locality", "postal_code", "school_district",

    # Government
    "city_hall", "courthouse", "embassy", "fire_station", "government_office", 
    "local_government_office", "neighborhood_police_station", "police", "post_office"
]

FIELD_MASK = "places.displayName,places.types,places.primaryType,places.location,places.id,places.shortFormattedAddress"

def bbox_to_circle(lon_min, lat_min, lon_max, lat_max):
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    R = 6371000  
    dlat = math.radians(lat_max - center_lat)
    dlon = math.radians(lon_max - center_lon)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(center_lat)) *
         math.cos(math.radians(lat_max)) *
         math.sin(dlon / 2) ** 2)
    radius = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return center_lat, center_lon, radius

def fetch_pois(lon_min, lat_min, lon_max, lat_max) -> list[dict]:
    center_lat, center_lon, radius = bbox_to_circle(lon_min, lat_min, lon_max, lat_max)
    all_pois = []
    seen_ids = set()

    # THE FIX: We query in tiny batches (e.g., 2 types at a time) to ensure 
    # we don't hit the 20-result ceiling for dense areas.
    BATCH_SIZE = 2 
    batches = [INCLUDED_TYPES[i:i + BATCH_SIZE] for i in range(0, len(INCLUDED_TYPES), BATCH_SIZE)]

    for batch_idx, batch in enumerate(batches):
        payload = {
            "includedTypes": batch,
            "maxResultCount": 20, 
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": center_lat, "longitude": center_lon},
                    "radius": radius,
                }
            },
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            response = requests.post(PLACES_URL, json=payload, headers=headers)
            
            if not response.ok:
                print(f"  [error] HTTP {response.status_code} on batch {batch_idx}: {batch}")
                continue

            data = response.json()
            places = data.get("places", [])

            for place in places:
                place_id = place.get("id")
                if not place_id or place_id in seen_ids:
                    continue
                seen_ids.add(place_id)

                loc = place.get("location", {})
                lat, lon = loc.get("latitude"), loc.get("longitude")

                if lat is None or lon is None:
                    continue
                if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                    continue

                types = place.get("types", [])
                primary_type = place.get("primaryType") or (types[0] if types else "unknown")
                name = place.get("displayName", {}).get("text", "Unnamed")

                all_pois.append({
                    "name": name,
                    "category": [f"google.{t}" for t in types],
                    "primary_type": primary_type,
                    "lat": lat,
                    "lon": lon,
                    "place_id": place_id,
                    "address": place.get("shortFormattedAddress"),
                })

        except Exception as e:
            print(f"  [error] Unexpected error on batch {batch_idx}: {e}")

        # Sleep slightly longer to respect quota if making many micro-requests
        time.sleep(0.1)

    print(f"  Found {len(all_pois)} unique POIs inside bbox")
    return all_pois

def process_grid(grid: list, output_dir: str = OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)

    for i, cell in enumerate(grid):
        out_path = Path(output_dir) / f"{i}.json"
        if out_path.exists():
            print(f"[{i}] Already exists, skipping.")
            continue

        bbox       = cell["bbox"]
        lon_min, lat_min, lon_max, lat_max = bbox
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2

        print(f"[{i}] Fetching POIs...")
        pois = fetch_pois(lon_min, lat_min, lon_max, lat_max)

        record = {
            "image":       f"{i}.png",
            "center_lat":  center_lat,
            "center_lon":  center_lon,
            "bbox": {
                "lon_min": lon_min, "lat_min": lat_min,
                "lon_max": lon_max, "lat_max": lat_max,
            },
            "unique_categories": list(set(
                cat for poi in pois for cat in poi["category"]
            )),
            "poi_count_per_category": {
                cat: sum(1 for poi in pois if cat in poi["category"])
                for cat in set(cat for poi in pois for cat in poi["category"])
            },
            "poi_count": len(pois),
            "pois":       pois,
        }

        with open(out_path, "w") as f:
            json.dump(record, f, indent=2)
        print(f"  ✓ Saved {out_path}")

        time.sleep(0.1)


if __name__ == "__main__":
    test_grid = [{"bbox": (-74.006, 40.712, -74.003, 40.715)}]
    process_grid(test_grid)