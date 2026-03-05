import json
import random
from pathlib import Path

from utils.utils import haversine

DATASET_DIR = Path("dataset")
IMAGE_DIR = DATASET_DIR / "images"
META_DIR = DATASET_DIR / "metadata"

OUT_DIR = DATASET_DIR / "output_mcqs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Utility functions
# -------------------------

def valid_name(name):
    return name and name.lower() != "unnamed"

def get_category_type(categories):
    """Extract the main category type from POI categories"""
    priority_categories = {
        'catering.restaurant': 'restaurant',
        'catering.cafe': 'cafe',
        'catering.bar': 'bar',
        'commercial.health_and_beauty': 'salon',
        'service.beauty': 'salon',
        'commercial.convenience': 'store',
        'commercial': 'store',
        'service.cleaning': 'laundry',
        'highway': 'road',
        'amenity': 'amenity'
    }
    
    for cat in categories:
        for key, value in priority_categories.items():
            if cat.startswith(key):
                return value
    
    return categories[0].split('.')[0] if categories else 'location'

def generate_4_options_names(correct_name, all_pois):
    """Generate 4 unique name options"""
    candidates = [correct_name]
    
    # Get other valid names
    other_names = [poi["name"] for poi in all_pois 
                   if valid_name(poi["name"]) and poi["name"] != correct_name]
    
    if len(other_names) >= 3:
        candidates.extend(random.sample(other_names, 3))
    else:
        # Add some generic names if not enough real names
        generic_names = ["Central Plaza", "Main Street", "City Center", "Grand Mall"]
        candidates.extend(other_names)
        remaining = 4 - len(candidates)
        candidates.extend(random.sample(generic_names, min(remaining, len(generic_names))))
    
    # Ensure exactly 4 options
    candidates = candidates[:4]
    random.shuffle(candidates)
    return candidates

def get_direction(from_poi, to_poi):
    """Calculate the cardinal direction from one POI to another"""
    lat_diff = to_poi["lat"] - from_poi["lat"]
    lon_diff = to_poi["lon"] - from_poi["lon"]
    
    # Determine primary direction based on larger difference
    if abs(lat_diff) > abs(lon_diff):
        # North/South is dominant
        if lat_diff > 0:
            return "north of"
        else:
            return "south of"
    else:
        # East/West is dominant
        if lon_diff > 0:
            return "east of"
        else:
            return "west of"

def get_direction_detailed(from_poi, to_poi):
    """Calculate direction with possible compound directions (e.g., northeast)"""
    lat_diff = to_poi["lat"] - from_poi["lat"]
    lon_diff = to_poi["lon"] - from_poi["lon"]
    
    # Threshold for considering a direction significant
    threshold_ratio = 0.3
    
    ns_dir = "north" if lat_diff > 0 else "south"
    ew_dir = "east" if lon_diff > 0 else "west"
    
    # Check if one direction is much more dominant
    if abs(lat_diff) < 0.0001 and abs(lon_diff) < 0.0001:
        return "near"
    
    if abs(lon_diff) < threshold_ratio * abs(lat_diff):
        return f"{ns_dir} of"
    elif abs(lat_diff) < threshold_ratio * abs(lon_diff):
        return f"{ew_dir} of"
    else:
        return f"{ns_dir}{ew_dir} of"

# -------------------------
# POI MCQ generators
# -------------------------

def simple_poi_existence_mcq(image_id, pois, all_pois):
    """Does the image portray a [category]? If so, what is the name?"""
    named_pois = [p for p in pois if valid_name(p.get("name", ""))]
    if not named_pois:
        return None
    
    target_poi = random.choice(named_pois)
    category_type = get_category_type(target_poi.get("category", []))
    
    options = generate_4_options_names(target_poi["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"Does the image portray a {category_type}? If so, what is the name of this {category_type}?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(target_poi["name"]) + 1),
        "classification": "poi"
    }

def location_based_mcq(image_id, pois, all_pois):
    """What [category] is located [direction] of [landmark]?"""
    # Filter POIs that have valid names AND coordinates
    named_pois = [p for p in pois if valid_name(p.get("name", "")) and 
                  p.get("lat") is not None and p.get("lon") is not None]
    
    if len(named_pois) < 2:
        return None
    
    target_poi, reference_poi = random.sample(named_pois, 2)
    category_type = get_category_type(target_poi.get("category", []))
    
    # Calculate actual direction from reference to target
    direction = get_direction(reference_poi, target_poi)
    
    options = generate_4_options_names(target_poi["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"What {category_type} is located {direction} {reference_poi['name']}?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(target_poi["name"]) + 1),
        "classification": "poi"
    }

def specific_poi_question_mcq(image_id, pois, all_pois):
    """Is there a [category] depicted in the image? If so, what is the name?"""
    named_pois = [p for p in pois if valid_name(p.get("name", ""))]
    if not named_pois:
        return None
    
    target_poi = random.choice(named_pois)
    categories = target_poi.get("category", [])
    
    # Try to find a more specific category
    specific_categories = [cat for cat in categories if '.' in cat and not cat.endswith('.')]
    if specific_categories:
        category = specific_categories[0].split('.')[-1]
    else:
        category = get_category_type(categories)
    
    options = generate_4_options_names(target_poi["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"Is there a {category} depicted in the image? If so, what is the name of this {category}?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(target_poi["name"]) + 1),
        "classification": "poi"
    }

def neighboring_poi_mcq(image_id, pois, all_pois):
    """What is the neighboring [category] to [landmark]?"""
    named_pois = [p for p in pois if valid_name(p.get("name", ""))]
    if len(named_pois) < 2:
        return None
    
    landmark_poi, neighbor_poi = random.sample(named_pois, 2)
    category_type = get_category_type(neighbor_poi.get("category", []))
    
    options = generate_4_options_names(neighbor_poi["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"What is the neighboring {category_type} to {landmark_poi['name']}?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(neighbor_poi["name"]) + 1),
        "classification": "poi"
    }

def contextual_recommendation_mcq(image_id, pois, all_pois):
    """Contextual question asking for recommendations"""
    restaurants = [p for p in pois if valid_name(p.get("name", "")) and 
                   any("catering" in cat for cat in p.get("category", []))]
    other_pois = [p for p in pois if valid_name(p.get("name", "")) and 
                  not any("catering" in cat for cat in p.get("category", []))]
    
    if not restaurants or not other_pois:
        return None
    
    workplace = random.choice(other_pois)
    restaurant = random.choice(restaurants)
    
    contexts = [
        f"I work at {workplace['name']} and I'm looking for a good place to have lunch. Can you recommend a restaurant?",
        f"After visiting {workplace['name']}, I want to grab some food. What restaurant would you suggest?",
        f"I'm near {workplace['name']} and feeling hungry. Which restaurant should I go to?",
        f"I have a meeting at {workplace['name']} and need a place for dinner afterwards. Any restaurant recommendations?"
    ]
    
    options = generate_4_options_names(restaurant["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": random.choice(contexts),
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(restaurant["name"]) + 1),
        "classification": "poi"
    }

def service_finder_mcq(image_id, pois, all_pois):
    """I need a [service type]. Can you help me find one?"""
    service_pois = [p for p in pois if valid_name(p.get("name", "")) and 
                    any("service" in cat or "commercial" in cat for cat in p.get("category", []))]
    
    if not service_pois:
        return None
    
    service_poi = random.choice(service_pois)
    categories = service_poi.get("category", [])
    
    service_type = "service"
    if any("beauty" in cat for cat in categories):
        service_type = "beauty salon"
    elif any("cleaning" in cat for cat in categories):
        service_type = "laundry service"
    elif any("health" in cat for cat in categories):
        service_type = "health service"
    
    contexts = [
        f"I need a {service_type}. Can you help me find one?",
        f"I'm looking for a good {service_type} in this area. Any suggestions?",
        f"Can you recommend a {service_type} nearby?"
    ]
    
    options = generate_4_options_names(service_poi["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": random.choice(contexts),
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(service_poi["name"]) + 1),
        "classification": "poi"
    }

def landmark_identification_mcq(image_id, pois, all_pois):
    """What is the name of the [landmark type] in this picture?"""
    named_pois = [p for p in pois if valid_name(p.get("name", ""))]
    if not named_pois:
        return None
    
    landmark = random.choice(named_pois)
    category_type = get_category_type(landmark.get("category", []))
    
    landmark_types = ["landmark", "building", "establishment", category_type]
    landmark_type = random.choice(landmark_types)
    
    options = generate_4_options_names(landmark["name"], all_pois)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"What is the name of the {landmark_type} in this picture?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(options.index(landmark["name"]) + 1),
        "classification": "poi"
    }

# -------------------------
# Main driver
# -------------------------

def generate_poi_mcqs():
    mcqs = []
    all_pois = []
    
    # First, collect all POIs for generating distractors
    for meta_file in META_DIR.glob("*.json"):
        print(f"Collecting POIs from {meta_file}")
        with open(meta_file, "r") as f:
            data = json.load(f)
        all_pois.extend(data.get("pois", []))
    
    for meta_file in META_DIR.glob("*.json"):
        image_id = meta_file.stem
        
        with open(meta_file, "r") as f:
            data = json.load(f)
        
        pois = data.get("pois", [])
        generators = [
            simple_poi_existence_mcq,
            location_based_mcq,
            specific_poi_question_mcq,
            neighboring_poi_mcq,
            contextual_recommendation_mcq,
            service_finder_mcq,
            landmark_identification_mcq
        ]
        
        # Generate 1-2 MCQs per image
        num_mcqs = random.choice([1, 2])
        selected_generators = random.sample(generators, min(num_mcqs, len(generators)))
        
        for generator in selected_generators:
            print(f"Generating MCQ for image {image_id} using {generator.__name__}")
            mcq = generator(image_id, pois, all_pois)
            if mcq:
                mcqs.append(mcq)
    
    with open(OUT_DIR / "poi_mcqs.json", "w") as f:
        json.dump(mcqs, f, indent=2)
    
    print(f"Generated {len(mcqs)} POI MCQs")
    return mcqs


if __name__ == "__main__":
    generate_poi_mcqs()
