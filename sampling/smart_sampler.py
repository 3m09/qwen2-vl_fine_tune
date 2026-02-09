import json
import os
from collections import Counter

METADATA_DIR = "dataset/metadata"

def load_metadata(idx):
    with open(os.path.join(METADATA_DIR, f"{idx}.json")) as f:
        return json.load(f)

def poi_density_bucket(poi_count):
    if poi_count <= 5:
        return "very_low"
    elif poi_count <= 20:
        return "low"
    elif poi_count <= 60:
        return "medium"
    elif poi_count <= 120:
        return "high"
    else:
        return "very_high"

def category_diversity(pois):
    cats = set()
    for p in pois:
        cats.update(p.get("category", []))
    return len(cats)

def smart_sample(indices, max_per_bucket=200):
    buckets = {k: [] for k in ["very_low","low","medium","high","very_high"]}

    for idx in indices:
        meta = load_metadata(idx)
        bucket = poi_density_bucket(meta["poi_count"])
        diversity = len(meta["unique_categories"])

        if diversity >= 3:  # diversity filter
            buckets[bucket].append(idx)

    selected = []
    for bucket, items in buckets.items():
        selected.extend(items[:max_per_bucket])

    return selected
