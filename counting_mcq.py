import json
import random
from pathlib import Path

DATASET_DIR = Path("dataset")
IMAGE_DIR = DATASET_DIR / "images"
META_DIR = DATASET_DIR / "metadata"

OUT_DIR = DATASET_DIR / "output_mcqs"
OUT_DIR.mkdir(parents=True, exist_ok=True)



# -------------------------
# Utility functions
# -------------------------

def normalize_category(cat):
    """Take only the first part before dot"""
    return cat.split(".")[0]


def valid_name(name):
    return name and name.lower() != "unnamed"


def generate_4_options(true_count):
    """
    Always generate exactly 4 unique numeric options
    """
    candidates = set([true_count])

    if true_count > 0:
        candidates.add(true_count - 1)
        candidates.add(true_count + 1)
        candidates.add(true_count + 2)
    else:
        candidates.add(true_count + 1)
        candidates.add(true_count + 2)
        candidates.add(true_count + 3)

    # delta = 1
    # while len(candidates) < 4:
    #     candidates.add(max(0, true_count - delta))
    #     candidates.add(true_count + delta)
    #     delta += 1

    options = list(candidates)[:4]
    random.shuffle(options)
    return options


# -------------------------
# Counting MCQ generators
# -------------------------

def category_count_mcq(image_id, pois):
    category_map = {}

    for poi in pois:
        for cat in poi.get("category", []):
            base = normalize_category(cat)
            category_map.setdefault(base, 0)
            category_map[base] += 1

    if not category_map:
        return None

    category, true_count = random.choice(list(category_map.items()))

    options = generate_4_options(true_count)

    return {
        "image_path": f"images/{image_id}.png",
        "question": f"How many {category}s are shown?",
        "option_count": "4",
        "options": "\n".join(
            [f"{i+1}) {opt}" for i, opt in enumerate(options)]
        ),
        "answer": str(options.index(true_count) + 1),
        "classification": "counting"
    }


def name_count_mcq(image_id, pois):
    name_map = {}

    for poi in pois:
        name = poi.get("name", "")
        if valid_name(name):
            name_map.setdefault(name, 0)
            name_map[name] += 1

    if not name_map:
        return None

    name, true_count = random.choice(list(name_map.items()))
    options = generate_4_options(true_count)

    return {
        "image_path": f"images/{image_id}.png",
        "question": f"Count how many {name} locations are there?",
        "option_count": "4",
        "options": "\n".join(
            [f"{i+1}) {opt}" for i, opt in enumerate(options)]
        ),
        "answer": str(options.index(true_count) + 1),
        "classification": "counting"
    }


def contextual_count_mcq(image_id, pois):
    named_pois = [p for p in pois if valid_name(p.get("name", ""))]
    if len(named_pois) < 2:
        return None

    anchor = random.choice(named_pois)

    category_map = {}
    for poi in pois:
        for cat in poi.get("category", []):
            base = normalize_category(cat)
            category_map.setdefault(base, 0)
            category_map[base] += 1

    if not category_map:
        return None

    target_cat, true_count = random.choice(list(category_map.items()))
    options = generate_4_options(true_count)

    templates = [
        f"I am at {anchor['name']}. How many {target_cat}s are there near me?",
        f"After visiting {anchor['name']}, how many {target_cat}s are around?",
        f"Presently I am at {anchor['name']}. How many nearby {target_cat}s exist?"
    ]

    return {
        "image_path": f"images/{image_id}.png",
        "question": random.choice(templates),
        "option_count": "4",
        "options": "\n".join(
            [f"{i+1}) {opt}" for i, opt in enumerate(options)]
        ),
        "answer": str(options.index(true_count) + 1),
        "classification": "counting"
    }


# -------------------------
# Main driver
# -------------------------

def generate_counting_mcqs():
    mcqs = []

    for meta_file in META_DIR.glob("*.json"):
        image_id = meta_file.stem

        with open(meta_file, "r") as f:
            data = json.load(f)

        pois = data.get("pois", [])
        generators = [
            category_count_mcq,
            name_count_mcq,
            contextual_count_mcq
        ]

        generator = random.choice(generators)
        mcq = generator(image_id, pois)

        if mcq:
            mcqs.append(mcq)

    with open(OUT_DIR / "counting_mcqs.json", "w") as f:
        json.dump(mcqs, f, indent=2)

    print(f"Generated {len(mcqs)} counting MCQs")
    return mcqs


if __name__ == "__main__":
    generate_counting_mcqs()
