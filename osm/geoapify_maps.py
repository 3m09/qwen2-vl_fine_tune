import requests

API_KEY = "REMOVED_API_KEY"
STATIC_MAP_URL = "https://maps.geoapify.com/v1/staticmap"


def download_static_map(lon_min, lat_min, lon_max, lat_max, output_file):
    # Geoapify 'rect' format: min_lon,min_lat,max_lon,max_lat
    params = {
        "style": "osm-bright", # You can use 'osm-bright', 'klokantech-basic', etc.
        "area": f"rect:{lon_min},{lat_min},{lon_max},{lat_max}",
        "zoom" : 18,
        "scaleFactor": 2,    
        "width": 1024,  # Adjust size (Max 2048 for free tier)
        "height": 1024,
        "apiKey": API_KEY
    }

    response = requests.get(STATIC_MAP_URL, params=params)

    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        print(f"Successfully saved map to {output_file}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)