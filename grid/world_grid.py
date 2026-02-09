import math

def km_to_lat(km):
    return km / 111.0

def km_to_lon(km, lat):
    return km / (111.0 * math.cos(math.radians(lat)))

def generate_world_grid(
    lat_min=40.800, lat_max=40.880,
    lon_min=-74.000, lon_max=-73.930,
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
