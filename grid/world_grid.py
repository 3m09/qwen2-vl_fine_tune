import math

BBOX_LIST = [
    # --- PREVIOUS LOCATIONS ---
    # # Part of Manhattan (Upper Manhattan/Harlem)
    # (40.800, -74.000, 40.880, -73.930),
    # # Whole Dhaka City
    # (23.663, 90.328, 23.892, 90.519),
    # Tokyo (Shibuya Crossing Area)
    (35.654, 139.696, 35.663, 139.707),
    # London (The City / Financial District)
    (51.505, -0.100, 51.518, -0.075),
    # Paris (Le Marais / 1st Arrondissement)
    (48.855, 2.335, 48.865, 2.355),
    # Mumbai (Fort / Colaba)
    (18.920, 72.825, 18.945, 72.840),
    # Shanghai (Lujiazui Financial District)
    (31.230, 121.490, 31.245, 121.515),
    # Seoul (Gangnam Station Area)
    (37.493, 127.022, 37.503, 127.033),
    # São Paulo (Avenida Paulista)
    (-23.570, -46.665, -23.555, -46.645),
    # Singapore (Orchard Road)
    (1.298, 103.825, 1.310, 103.845),

    # --- ADDITIONAL DENSE AREAS ---
    # Hong Kong (Central / Tsim Sha Tsui) - Extreme vertical density
    (22.275, 114.160, 22.300, 114.185),
    # Istanbul, Turkey (Sultanahmet / Eminönü) - Massive density of historical & tourism POIs
    (41.000, 28.960, 41.025, 28.990),
    # Mexico City, Mexico (Centro Histórico) - High density of commerce and landmarks
    (19.425, -99.145, 19.440, -99.125),
    # Dubai, UAE (Downtown / Dubai Mall Area) - Modern ultra-high density
    (25.190, 55.265, 25.210, 55.285),
    # Sydney, Australia (CBD / Circular Quay) - Major southern hemisphere hub
    (-33.875, 151.200, -33.855, 151.220),
    # San Francisco, USA (Financial District / Union Square) - Dense tech and retail hub
    (37.780, -122.410, 37.800, -122.390),
    # Berlin, Germany (Mitte / Alexanderplatz) - Historic and commercial heart
    (52.510, 13.380, 52.530, 13.420)
]

def km_to_lat(km):
    return km / 111.0

def km_to_lon(km, lat):
    return km / (111.0 * math.cos(math.radians(lat)))

def generate_world_grid(cell_km=0.25):
    world_grid = []
    for bbox in BBOX_LIST:
        grid = generate_grid(
            lat_min=bbox[0],
            lon_min=bbox[1],
            lat_max=bbox[2],
            lon_max=bbox[3],
            cell_km=cell_km
        )
        world_grid.extend(grid)
    return world_grid

def generate_grid(
    # Part of Tokyo
    lat_min=35.654, lat_max=35.663,
    lon_min=139.696, lon_max=139.707,
    cell_km=0.25
):
    grid = []

    lat = lat_min
    while lat < lat_max:
        dlat = km_to_lat(cell_km)
        dlon = km_to_lon(cell_km, lat)

        lon = lon_min
        while lon < lon_max:
            grid.append({
                "center_lat": lat + dlat / 2,
                "center_lon": lon + dlon / 2,
                "bbox": (
                    lon,
                    lat,
                    lon + dlon,
                    lat + dlat
                )
            })
            lon += dlon
        lat += dlat

    return grid
