"""
generate_routing_mcqs.py
------------------------
Generates routing-type MCQs from geospatial metadata JSON files produced by
build_dataset.py.  Each metadata record contains a map image path and a list
of POIs with names, categories, and coordinates.

Question sub-types generated
─────────────────────────────
1.  shortest_route          – Which of N step-by-step routes is the shortest?
2.  distance                – What is the distance between A and B via a route?
3.  direction               – Which cardinal direction is B from A?
4.  total_distance_waypoints– Total distance A→B→C→D via intermediate waypoints
5.  landmark_between        – Which landmark lies between A and B?
6.  time_calculation        – How long at speed X to travel distance Y?
7.  nearby_poi              – Which POI of category X is nearest to anchor POI?
8.  poi_on_route            – Which POI is found along the route from A to B?
9.  poi_at_intersection     – Which POI is at the intersection of route A and route B?
10. navigate_to_nearest     – Give directions to the nearest POI of a given category

Routing backend: OSRM public demo server (no API key needed).
Geoapify routing used as fallback when OSRM is unavailable.

Usage
─────
    python generate_routing_mcqs.py \
        --metadata_dir  dataset/metadata \
        --output        routing_mcqs.json \
        --mcqs_per_cell 3 \
        --limit         200
"""

import argparse
import json
import math
import os
import random
import time
from pathlib import Path

import requests


# ══════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════

GEOAPIFY_API_KEY = "REMOVED_API_KEY"
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
GEOAPIFY_ROUTING = "https://api.geoapify.com/v1/routing"

CARDINAL_DIRS = [
    "North", "Northeast", "East", "Southeast",
    "South", "Southwest", "West", "Northwest",
]

# Category labels used for human-readable question phrasing
CATEGORY_LABELS = {
    "catering.restaurant":    "restaurant",
    "catering.cafe":          "café",
    "catering.fast_food":     "fast food outlet",
    "amenity.fuel":           "filling station",
    "amenity.hospital":       "hospital",
    "amenity.pharmacy":       "pharmacy",
    "amenity.school":         "school",
    "amenity.bank":           "bank",
    "amenity.place_of_worship": "place of worship",
    "leisure.park":           "park",
    "leisure.sports_centre":  "sports centre",
    "commercial.shopping_mall": "shopping mall",
    "commercial.supermarket": "supermarket",
    "tourism.museum":         "museum",
    "tourism.attraction":     "tourist attraction",
    "tourism.hotel":          "hotel",
    "accommodation.hotel":    "hotel",
}


# ══════════════════════════════════════════════════════════════════
# Geometry / math helpers
# ══════════════════════════════════════════════════════════════════

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Bearing from (lat1,lon1) to (lat2,lon2) in degrees [0,360)."""
    dlon = math.radians(lon2 - lon1)
    r1, r2 = math.radians(lat1), math.radians(lat2)
    x = math.sin(dlon) * math.cos(r2)
    y = math.cos(r1) * math.sin(r2) - math.sin(r1) * math.cos(r2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_to_cardinal(bearing: float) -> str:
    return CARDINAL_DIRS[round(bearing / 45) % 8]


def point_to_segment_dist(px, py, ax, ay, bx, by) -> float:
    """Euclidean distance (degrees) from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def poi_near_polyline(poi_lat: float, poi_lon: float,
                      coords: list[tuple], threshold_deg: float = 0.0009) -> bool:
    """Return True if POI is within threshold_deg of any segment in coords."""
    for i in range(len(coords) - 1):
        a, b = coords[i], coords[i + 1]
        if point_to_segment_dist(poi_lat, poi_lon, a[0], a[1], b[0], b[1]) < threshold_deg:
            return True
    return False


def add_noise(value: float, pct_range=(0.06, 0.28)) -> float:
    """Add ±noise to value for distractor generation."""
    lo, hi = pct_range
    delta = random.uniform(lo, hi) * random.choice([-1, 1])
    return round(value * (1 + delta), 2)


def make_distractors(true_val: float, n: int = 3,
                     pct_range=(0.06, 0.28)) -> list[float]:
    """Generate n unique distractors around true_val."""
    seen = {true_val}
    result = []
    attempts = 0
    while len(result) < n and attempts < 50:
        d = add_noise(true_val, pct_range)
        if d not in seen and d > 0:
            seen.add(d)
            result.append(d)
        attempts += 1
    return result


# ══════════════════════════════════════════════════════════════════
# OSRM routing helpers
# ══════════════════════════════════════════════════════════════════

def _osrm_request(coords_list: list[tuple], alternatives: bool = True,
                  steps: bool = True, timeout: int = 10) -> dict | None:
    """
    Make a single OSRM request.
    coords_list: list of (lat, lon) tuples – minimum 2.
    Returns the parsed JSON dict or None on failure.
    """
    waypoints = ";".join(f"{lon},{lat}" for lat, lon in coords_list)
    url = f"{OSRM_BASE}/{waypoints}"
    params = {
        "alternatives": "true" if alternatives else "false",
        "steps": "true" if steps else "false",
        "geometries": "geojson",
        "overview": "full",
    }
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "Ok":
            return data
    except Exception as exc:
        print(f"  [OSRM] Error: {exc}")
    return None


def get_routes_osrm(src_lat, src_lon, dst_lat, dst_lon,
                    max_alternatives: int = 3) -> list[dict]:
    """Return up to max_alternatives OSRM route objects."""
    data = _osrm_request([(src_lat, src_lon), (dst_lat, dst_lon)])
    if data:
        return data.get("routes", [])[:max_alternatives]
    return []


def get_route_via_waypoints_osrm(waypoints: list[tuple]) -> dict | None:
    """Get single route through ordered waypoints [(lat,lon), ...]."""
    data = _osrm_request(waypoints, alternatives=False)
    if data:
        routes = data.get("routes", [])
        return routes[0] if routes else None
    return None


def osrm_polyline(route: dict) -> list[tuple]:
    """Extract (lat, lon) polyline from an OSRM route."""
    geom = route.get("geometry", {})
    if geom.get("type") == "LineString":
        return [(c[1], c[0]) for c in geom["coordinates"]]
    return []


def osrm_steps_text(route: dict, max_steps: int = 8) -> list[str]:
    """
    Return human-readable step strings from an OSRM route.
    Format mirrors the sample MCQ options in routing.json.
    """
    lines = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            name = step.get("name", "").strip()
            if not name:
                continue
            maneuver = step.get("maneuver", {})
            m_type = maneuver.get("type", "")
            modifier = maneuver.get("modifier", "")

            if m_type == "depart":
                lines.append(f"Head {modifier} on {name}" if modifier else f"Start on {name}")
            elif m_type == "arrive":
                lines.append(f"Arrive at destination via {name}")
            elif m_type == "turn":
                lines.append(f"Turn {modifier} onto {name}")
            elif m_type == "roundabout":
                exit_n = step.get("maneuver", {}).get("exit", "")
                lines.append(f"At roundabout take exit {exit_n} onto {name}" if exit_n else f"Take roundabout onto {name}")
            elif m_type in ("new name", "continue"):
                lines.append(f"Continue on {name}")
            else:
                lines.append(f"{name}")

            if len(lines) >= max_steps:
                break
        if len(lines) >= max_steps:
            break
    return lines


# ══════════════════════════════════════════════════════════════════
# POI helpers
# ══════════════════════════════════════════════════════════════════

def category_label(poi: dict) -> str:
    """Return a human-readable category label for a POI."""
    cats = poi.get("category", [])
    for c in cats:
        if c in CATEGORY_LABELS:
            return CATEGORY_LABELS[c]
    # Fallback: use last segment of the first category
    if cats:
        return cats[0].split(".")[-1].replace("_", " ")
    return "place"


def named_pois(pois: list[dict]) -> list[dict]:
    """Filter to POIs with a non-empty name and valid coordinates."""
    return [
        p for p in pois
        if p.get("name") and p["name"].strip().lower() != "unnamed"
        and p.get("lat") is not None and p.get("lon") is not None
    ]


def pick_pair(pois: list[dict], min_dist_km: float = 0.15,
              max_dist_km: float = 5.0) -> tuple[dict, dict] | None:
    """Pick two named POIs that are an appropriate distance apart."""
    pool = named_pois(pois)
    random.shuffle(pool)
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            d = haversine(a["lat"], a["lon"], b["lat"], b["lon"])
            if min_dist_km <= d <= max_dist_km:
                return a, b
    return None


def pois_by_category_prefix(pois: list[dict], prefix: str) -> list[dict]:
    """Return named POIs whose category starts with prefix."""
    result = []
    for p in named_pois(pois):
        for c in p.get("category", []):
            if c.startswith(prefix):
                result.append(p)
                break
    return result


def shuffle_with_answer(correct: dict, distractors: list[dict]) -> tuple[list[dict], int]:
    """Shuffle [correct]+distractors and return (shuffled_list, 1-based correct index)."""
    all_opts = [correct] + distractors
    random.shuffle(all_opts)
    idx = next(i for i, p in enumerate(all_opts) if p is correct) + 1
    return all_opts, idx


def format_options(items: list, formatter) -> str:
    return "\n".join(f"{i + 1}. {formatter(item)}" for i, item in enumerate(items))


# ══════════════════════════════════════════════════════════════════
# MCQ sub-type generators
# Each function accepts (metadata: dict, image_path: str)
# and returns a dict matching the routing.json schema, or None.
# ══════════════════════════════════════════════════════════════════

def gen_shortest_route(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: shortest_route
    Ask which of 2–3 OSRM alternative routes is the shortest.
    """
    pair = pick_pair(metadata["pois"], min_dist_km=0.3)
    if not pair:
        return None

    src, dst = pair
    routes = get_routes_osrm(src["lat"], src["lon"], dst["lat"], dst["lon"], max_alternatives=3)
    if len(routes) < 2:
        return None

    routes = routes[:3]
    shortest_idx = min(range(len(routes)), key=lambda i: routes[i]["distance"])

    options_text = []
    for idx, r in enumerate(routes):
        dist_km = round(r["distance"] / 1000, 2)
        dur_min = round(r["duration"] / 60, 1)
        steps = osrm_steps_text(r, max_steps=6)
        step_block = "\n".join(steps) if steps else "(direct)"
        options_text.append(
            f"{idx + 1}. {src['name']}\n{step_block}\n{dst['name']}"
            f" ({dist_km} km, {dur_min} min)"
        )

    return {
        "image_path": image_path,
        "question": f"What is the shortest route from {src['name']} to {dst['name']}?",
        "option_count": str(len(routes)),
        "options": "\n\n".join(options_text),
        "answer": str(shortest_idx + 1),
        "classification": "routing",
    }


def gen_distance(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: distance
    Ask the route distance between two POIs; 4 numerical options.
    """
    pair = pick_pair(metadata["pois"], min_dist_km=0.2)
    if not pair:
        return None

    src, dst = pair
    routes = get_routes_osrm(src["lat"], src["lon"], dst["lat"], dst["lon"], max_alternatives=1)

    if routes:
        true_dist = round(routes[0]["distance"] / 1000, 2)
        steps = osrm_steps_text(routes[0], max_steps=4)
        route_desc = " → ".join(
            s.split(" onto ")[-1] for s in steps if "onto" in s
        )[:80] or "the direct route"
    else:
        true_dist = round(haversine(src["lat"], src["lon"], dst["lat"], dst["lon"]), 2)
        route_desc = "the direct path"

    distractors = make_distractors(true_dist, n=3)
    all_opts = [true_dist] + distractors
    random.shuffle(all_opts)
    answer_idx = all_opts.index(true_dist) + 1

    return {
        "image_path": image_path,
        "question": (
            f"What is the distance between {src['name']} and {dst['name']} "
            f"via {route_desc}?"
        ),
        "option_count": "4",
        "options": "\n".join(f"({i + 1}) {d} km" for i, d in enumerate(all_opts)),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_direction(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: direction
    Ask the cardinal direction to travel from A to reach B.
    """
    pair = pick_pair(metadata["pois"], min_dist_km=0.1)
    if not pair:
        return None

    src, dst = pair
    bearing = compute_bearing(src["lat"], src["lon"], dst["lat"], dst["lon"])
    true_dir = bearing_to_cardinal(bearing)

    wrong_dirs = [d for d in CARDINAL_DIRS if d != true_dir]
    distractors = random.sample(wrong_dirs, 3)
    all_opts = [true_dir] + distractors
    random.shuffle(all_opts)
    answer_idx = all_opts.index(true_dir) + 1

    return {
        "image_path": image_path,
        "question": f"Which direction should I travel from {src['name']} to reach {dst['name']}?",
        "option_count": "4",
        "options": "\n".join(f"{i + 1}. {d}" for i, d in enumerate(all_opts)),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_total_distance_waypoints(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: total_distance_waypoints
    Calculate total route distance A→B→C→D via intermediate waypoints.
    Uses OSRM with multiple waypoints when available.
    """
    pool = named_pois(metadata["pois"])
    if len(pool) < 4:
        return None

    random.shuffle(pool)
    waypoints = pool[:4]

    # Try OSRM multi-waypoint route
    route = get_route_via_waypoints_osrm(
        [(p["lat"], p["lon"]) for p in waypoints]
    )

    if route:
        true_dist = round(route["distance"] / 1000, 1)
    else:
        # Fall back to summed haversine segments
        true_dist = round(
            sum(
                haversine(waypoints[i]["lat"], waypoints[i]["lon"],
                          waypoints[i + 1]["lat"], waypoints[i + 1]["lon"])
                for i in range(len(waypoints) - 1)
            ),
            1,
        )

    distractors = [round(add_noise(true_dist, (0.005, 0.02)), 1) for _ in range(3)]
    all_opts = [true_dist] + distractors
    random.shuffle(all_opts)
    answer_idx = all_opts.index(true_dist) + 1

    names = " → ".join(p["name"] for p in waypoints)

    return {
        "image_path": image_path,
        "question": (
            f"Calculate the total distance of the route: {names}."
        ),
        "option_count": "4",
        "options": "\n".join(f"({i + 1}) {d} km" for i, d in enumerate(all_opts)),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_landmark_between(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: landmark_between
    Identify which POI lies geographically between two anchor POIs.
    """
    pois = metadata["pois"]
    pair = pick_pair(pois, min_dist_km=0.3)
    if not pair:
        return None

    src, dst = pair
    lat_lo = min(src["lat"], dst["lat"])
    lat_hi = max(src["lat"], dst["lat"])
    lon_lo = min(src["lon"], dst["lon"])
    lon_hi = max(src["lon"], dst["lon"])
    pad = 0.003

    between, outside = [], []
    for p in named_pois(pois):
        if p["name"] in {src["name"], dst["name"]}:
            continue
        if (lat_lo - pad <= p["lat"] <= lat_hi + pad
                and lon_lo - pad <= p["lon"] <= lon_hi + pad):
            between.append(p)
        else:
            outside.append(p)

    if not between or len(outside) < 3:
        return None

    correct = random.choice(between)
    distractors = random.sample(outside, 3)
    all_opts, answer_idx = shuffle_with_answer(correct, distractors)

    return {
        "image_path": image_path,
        "question": (
            f"Identify a landmark that is located between {src['name']} and {dst['name']}."
        ),
        "option_count": "4",
        "options": format_options(all_opts, lambda p: p["name"]),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_time_calculation(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: time_calculation
    Given speed and distance, calculate travel time.
    """
    pair = pick_pair(metadata["pois"], min_dist_km=0.2)
    if not pair:
        return None

    src, dst = pair
    routes = get_routes_osrm(src["lat"], src["lon"], dst["lat"], dst["lon"], max_alternatives=1)
    dist_km = round(routes[0]["distance"] / 1000, 2) if routes else round(
        haversine(src["lat"], src["lon"], dst["lat"], dst["lon"]), 2
    )

    # Realistic speed options
    speed = random.choice([4.5, 5.0, 5.4, 6.0, 12.0, 15.0, 20.0, 30.0])
    true_time = round(dist_km / speed * 60, 2)  # minutes

    distractors = make_distractors(true_time, n=3, pct_range=(0.05, 0.15))
    all_opts = [true_time] + distractors
    random.shuffle(all_opts)
    answer_idx = all_opts.index(true_time) + 1

    return {
        "image_path": image_path,
        "question": (
            f"If traveling at a constant speed of {speed} km/h, how long will it take "
            f"to travel from {src['name']} to {dst['name']} if the distance is {dist_km} km?"
        ),
        "option_count": "4",
        "options": "\n".join(f"({i + 1}) {t} minutes" for i, t in enumerate(all_opts)),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_nearby_poi(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: nearby_poi
    Given an anchor POI, which named POI of a certain category is nearest?
    """
    pois = metadata["pois"]
    pool = named_pois(pois)
    if len(pool) < 5:
        return None

    anchor = random.choice(pool)
    others = sorted(
        [p for p in pool if p["name"] != anchor["name"]],
        key=lambda p: haversine(anchor["lat"], anchor["lon"], p["lat"], p["lon"]),
    )
    if not others:
        return None

    nearest = others[0]
    # Distractors chosen from the far end of the sorted list to be clearly wrong
    far_pool = others[max(1, len(others) // 2):]
    if len(far_pool) < 3:
        far_pool = others[1:4]
    distractors = random.sample(far_pool, min(3, len(far_pool)))

    all_opts, answer_idx = shuffle_with_answer(nearest, distractors)
    cat = category_label(nearest)

    return {
        "image_path": image_path,
        "question": f"I am at {anchor['name']}. Which {cat} is located nearest to me?",
        "option_count": "4",
        "options": format_options(all_opts, lambda p: p["name"]),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_poi_on_route(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: poi_on_route
    Which POI of a given category can be found on the route between A and B?
    """
    pois = metadata["pois"]
    pair = pick_pair(pois, min_dist_km=0.3)
    if not pair:
        return None

    src, dst = pair
    routes = get_routes_osrm(src["lat"], src["lon"], dst["lat"], dst["lon"], max_alternatives=1)
    if not routes:
        return None

    polyline = osrm_polyline(routes[0])
    if not polyline:
        return None

    others = [p for p in named_pois(pois)
              if p["name"] not in {src["name"], dst["name"]}]
    on_route = [p for p in others if poi_near_polyline(p["lat"], p["lon"], polyline)]
    off_route = [p for p in others if not poi_near_polyline(p["lat"], p["lon"], polyline)]

    if not on_route or len(off_route) < 3:
        return None

    correct = random.choice(on_route)
    distractors = random.sample(off_route, 3)
    all_opts, answer_idx = shuffle_with_answer(correct, distractors)
    cat = category_label(correct)

    return {
        "image_path": image_path,
        "question": f"Which {cat} can be found on the way from {src['name']} to {dst['name']}?",
        "option_count": "4",
        "options": format_options(all_opts, lambda p: p["name"]),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_poi_at_intersection(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: poi_at_intersection
    Which POI is closest to the geographic midpoint between two areas/routes?
    Mirrors 'Which landmark is at the intersection of X and Y?' questions.
    """
    pois = metadata["pois"]
    pool = named_pois(pois)
    if len(pool) < 6:
        return None

    # Pick two "route" anchors and find the poi nearest their midpoint
    a, b = random.sample(pool, 2)
    mid_lat = (a["lat"] + b["lat"]) / 2
    mid_lon = (a["lon"] + b["lon"]) / 2

    others = [p for p in pool if p["name"] not in {a["name"], b["name"]}]
    if len(others) < 4:
        return None

    sorted_others = sorted(others, key=lambda p: haversine(mid_lat, mid_lon, p["lat"], p["lon"]))
    correct = sorted_others[0]
    # Distractors are from the far end
    distractors = random.sample(sorted_others[max(1, len(sorted_others) // 2):], min(3, len(sorted_others) - 1))
    if len(distractors) < 3:
        distractors = sorted_others[1:4]

    all_opts, answer_idx = shuffle_with_answer(correct, distractors)
    cat = category_label(correct)

    return {
        "image_path": image_path,
        "question": (
            f"Which {cat} is located at the intersection of the area around "
            f"{a['name']} and {b['name']}?"
        ),
        "option_count": "4",
        "options": format_options(all_opts, lambda p: p["name"]),
        "answer": str(answer_idx),
        "classification": "routing",
    }


def gen_navigate_to_nearest(metadata: dict, image_path: str) -> dict | None:
    """
    Sub-type: navigate_to_nearest
    Give step-by-step directions from an anchor to the nearest POI of a category.
    Options are 4 different route descriptions; only the correct one actually
    reaches the nearest POI via valid OSRM steps.
    """
    pois = metadata["pois"]
    # Look for a category cluster
    category_prefixes = ["catering", "amenity", "tourism", "leisure", "commercial"]
    random.shuffle(category_prefixes)

    anchor = None
    target = None
    distractors = []

    for prefix in category_prefixes:
        cat_pois = pois_by_category_prefix(pois, prefix)
        rest_pois = named_pois(pois)
        if len(cat_pois) < 4 or len(rest_pois) < 1:
            continue

        anchor_candidates = [p for p in rest_pois if p not in cat_pois]
        if not anchor_candidates:
            continue

        anchor = random.choice(anchor_candidates)
        sorted_cats = sorted(
            cat_pois,
            key=lambda p: haversine(anchor["lat"], anchor["lon"], p["lat"], p["lon"]),
        )
        target = sorted_cats[0]       # nearest – correct answer
        distractors = sorted_cats[1:4]  # further ones – wrong
        break

    if not anchor or not target or len(distractors) < 3:
        return None

    cat_label_str = category_label(target)

    # Get OSRM steps for correct route
    routes = get_routes_osrm(anchor["lat"], anchor["lon"], target["lat"], target["lon"], max_alternatives=1)
    if not routes:
        return None

    def route_option_text(dest_poi, route_obj):
        steps = osrm_steps_text(route_obj, max_steps=5)
        step_block = "\n".join(steps) if steps else "(direct path)"
        dist_km = round(route_obj["distance"] / 1000, 2)
        return f"{anchor['name']}\n{step_block}\n{dest_poi['name']} ({dist_km} km)"

    # Build plausible-sounding but wrong options for distractors
    # (fabricate a short step description based on bearing)
    def fake_option_text(dest_poi, idx):
        bearing = compute_bearing(anchor["lat"], anchor["lon"], dest_poi["lat"], dest_poi["lon"])
        direction = bearing_to_cardinal(bearing)
        dist = round(haversine(anchor["lat"], anchor["lon"], dest_poi["lat"], dest_poi["lon"]), 2)
        return (
            f"{anchor['name']}\n"
            f"Head {direction.lower()} toward {dest_poi['name']}\n"
            f"{dest_poi['name']} ({dist} km)"
        )

    correct_text = route_option_text(target, routes[0])
    distractor_texts = [fake_option_text(d, i) for i, d in enumerate(distractors)]

    all_texts = [correct_text] + distractor_texts
    correct_idx_in_list = 0  # index before shuffle
    combined = list(zip(all_texts, [True] + [False] * 3))
    random.shuffle(combined)
    all_texts_shuffled = [t for t, _ in combined]
    answer_idx = next(i for i, (_, is_c) in enumerate(combined) if is_c) + 1

    return {
        "image_path": image_path,
        "question": (
            f"Navigate me to the nearest {cat_label_str} located near {anchor['name']}."
        ),
        "option_count": "4",
        "options": "\n\n".join(f"{i + 1}. {t}" for i, t in enumerate(all_texts_shuffled)),
        "answer": str(answer_idx),
        "classification": "routing",
    }


# ══════════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════════

GENERATORS = {
    "shortest_route":            gen_shortest_route,
    "distance":                  gen_distance,
    "direction":                 gen_direction,
    "total_distance_waypoints":  gen_total_distance_waypoints,
    "landmark_between":          gen_landmark_between,
    "time_calculation":          gen_time_calculation,
    "nearby_poi":                gen_nearby_poi,
    "poi_on_route":              gen_poi_on_route,
    "poi_at_intersection":       gen_poi_at_intersection,
    "navigate_to_nearest":       gen_navigate_to_nearest,
}


# ══════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════

def generate_routing_mcqs(
    metadata_dir: str = "dataset/metadata_refined",
    output_file: str = "dataset/output_mcqs/routing_mcqs.json",
    mcqs_per_cell: int = 3,
    limit: int | None = None,
    question_types: list[str] | None = None,
    osrm_delay: float = 0.15,
    seed: int = 42,
) -> list[dict]:
    """
    Main entry point. Iterates over metadata JSON files and generates MCQs.

    Parameters
    ----------
    metadata_dir    : Directory containing <N>.json metadata files.
    output_file     : Path to write the generated MCQ JSON array.
    mcqs_per_cell   : How many MCQs to attempt per metadata cell.
    limit           : Maximum number of metadata files to process (None = all).
    question_types  : Subset of GENERATORS keys to use (None = all).
    osrm_delay      : Seconds to wait between OSRM calls (be polite to the server).
    seed            : Random seed for reproducibility.
    """
    random.seed(seed)

    active_generators = {
        k: v for k, v in GENERATORS.items()
        if question_types is None or k in question_types
    }
    gen_keys = list(active_generators.keys())

    metadata_path = Path(metadata_dir)
    files = sorted(metadata_path.glob("*.json"))
    if limit:
        files = files[:limit]

    print(f"Processing {len(files)} metadata files, "
          f"up to {mcqs_per_cell} MCQs each, "
          f"types: {gen_keys}")

    all_mcqs: list[dict] = []
    type_counts: dict[str, int] = {k: 0 for k in gen_keys}

    for meta_file in files:
        try:
            with open(meta_file, encoding="utf-8") as fh:
                metadata = json.load(fh)
        except Exception as exc:
            print(f"  [SKIP] {meta_file.name}: {exc}")
            continue

        if not metadata.get("pois"):
            continue

        # Determine image path
        image_path = metadata.get("image") or str(
            meta_file.parent.parent / "images" / (meta_file.stem + ".png")
        )

        # Attempt mcqs_per_cell different question types (no repeats per cell)
        attempted_types = random.sample(gen_keys, min(mcqs_per_cell, len(gen_keys)))
        cell_count = 0

        for qtype in attempted_types:
            gen_fn = active_generators[qtype]
            try:
                mcq = gen_fn(metadata, image_path)
            except Exception as exc:
                print(f"  [ERROR] {qtype} on {meta_file.name}: {exc}")
                mcq = None

            if mcq:
                all_mcqs.append(mcq)
                type_counts[qtype] += 1
                cell_count += 1
                print(f"  ✓ {meta_file.name}  [{qtype}]")
            else:
                print(f"  – {meta_file.name}  [{qtype}] skipped (insufficient data)")

            time.sleep(osrm_delay)

        if cell_count == 0:
            print(f"  [WARN] No MCQs generated for {meta_file.name}")

    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(all_mcqs, fh, indent=2, ensure_ascii=False)

    print(f"\n{'─' * 50}")
    print(f"Generated {len(all_mcqs)} MCQs  →  {output_file}")
    print("Breakdown by type:")
    for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {k:<30} {v}")

    return all_mcqs


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate routing MCQs from map metadata.")
    parser.add_argument("--metadata_dir",  default="dataset/metadata_refined",
                        help="Directory of metadata JSON files (default: dataset/metadata_refined)")
    parser.add_argument("--output",        default="dataset/output_mcqs/routing_mcqs.json",
                        help="Output JSON file (default: dataset/output_mcqs/routing_mcqs.json)")
    parser.add_argument("--mcqs_per_cell", type=int, default=3,
                        help="MCQs to attempt per metadata cell (default: 3)")
    parser.add_argument("--limit",         type=int, default=None,
                        help="Max metadata files to process (default: all)")
    parser.add_argument("--types",         nargs="+", choices=list(GENERATORS.keys()),
                        default=None,
                        help="Specific question types to generate (default: all)")
    parser.add_argument("--osrm_delay",    type=float, default=0.15,
                        help="Seconds between OSRM calls (default: 0.15)")
    parser.add_argument("--seed",          type=int, default=42,
                        help="Random seed (default: 42)")

    args = parser.parse_args()

    generate_routing_mcqs(
        metadata_dir  = args.metadata_dir,
        output_file   = args.output,
        mcqs_per_cell = args.mcqs_per_cell,
        limit         = args.limit,
        question_types= args.types,
        osrm_delay    = args.osrm_delay,
        seed          = args.seed,
    )