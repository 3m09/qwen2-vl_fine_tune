import requests
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEOAPIFY_API_KEY")
PLACES_URL = "https://api.geoapify.com/v2/places"
DETAILS_URL = "https://api.geoapify.com/v2/place-details"

def fetch_pois_in_bbox(lon_min, lat_min, lon_max, lat_max, categories="amenity"):
    """
    Fetches POIs within a rectangle.
    Categories can be 'amenity', 'commercial', 'tourism', 'catering', etc.
    """
    params = {
        "categories": categories,
        "filter": f"rect:{lon_min},{lat_min},{lon_max},{lat_max}",
        "limit": 100,  # Max POIs per request
        "apiKey": API_KEY
    }

    try:
        response = requests.get(PLACES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Geoapify returns GeoJSON FeatureCollection
        features = data.get("features", [])
        print(f"Found {len(features)} POIs in this cell.")
        
        pois = []
        for feat in features:
            props = feat["properties"]
            place_id = props.get("place_id")
            main_category = props.get("categories", [None])[0]

            poi_data = {
                "name": props.get("name", "Unnamed"),
                "category": props.get("categories", []),
                "lat": props.get("lat"),
                "lon": props.get("lon"),
                "place_id": place_id,
                "geometry_type": feat["geometry"]["type"],
                "road_geometry": None
            }

            if "highway" in str(main_category):
                # print(f"Fetching geometry for road: {poi_data['name']}")
                
                details_params = {
                    "id": place_id,
                    "apiKey": API_KEY
                }
                
                # Fetch details (Note: This costs extra credits)
                details_res = requests.get(DETAILS_URL, params=details_params)
                if details_res.status_code == 200:
                    # print(f"Successfully fetched details for {poi_data['name']}")
                    details_data = details_res.json()
                    # Store the actual path/line of the road
                    poi_data["road_geometry"] = details_data.get("features", [{}])[0].get("geometry")
                    # print(f"Geometry for {poi_data['name']}: {poi_data['road_geometry']}")
            
                time.sleep(0.1)
            pois.append(poi_data)
        
        # RESPECT RATE LIMIT: 5 requests per second (0.2s delay)
        time.sleep(0.2) 
        return pois

    except Exception as e:
        print(f"Error fetching POIs: {e}")
        return []

# Example Test Case (Manhattan 1km block)
# results = fetch_pois_in_bbox(-74.006, 40.712, -73.996, 40.722)