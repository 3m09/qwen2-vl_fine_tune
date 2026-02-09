import json
import os
from sampling.smart_sampler import smart_sample
from mcq.poi_mcq import generate_poi_mcq
from mcq.nearby_mcq import generate_nearby_mcq
from mcq.counting_mcq import generate_counting_mcqs
from mcq.routing_mcq import generate_routing_mcq

META_DIR = "dataset/metadata"
OUT_DIR = "dataset/output_mcqs"

os.makedirs(OUT_DIR, exist_ok=True)

indices = [int(f.split(".")[0]) for f in os.listdir(META_DIR)]
selected = smart_sample(indices)

all_mcqs = []

for idx in selected:
    with open(f"{META_DIR}/{idx}.json") as f:
        meta = json.load(f)

    # mcqs = [
    #     generate_poi_mcq(meta, meta["pois"]),
    #     generate_nearby_mcq(meta),
    #     generate_counting_mcq(meta),
    #     generate_routing_mcq(meta)
    # ]

    mcqs = [
        generate_counting_mcqs(),
    ]

    for mcq in mcqs:
        if mcq:
            # mcq["image_path"] = f"images/{idx}.png"
            all_mcqs.extend(mcq)

with open(f"{OUT_DIR}/mcqs.json", "w") as f:
    json.dump(all_mcqs, f, indent=2)
