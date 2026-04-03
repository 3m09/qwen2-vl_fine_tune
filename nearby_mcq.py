import json
import random
from pathlib import Path
import math

from utils.utils import haversine

DATASET_DIR =  Path("dataset")
IMAGE_DIR = DATASET_DIR / "images"
META_DIR = DATASET_DIR / "metadata_refined"

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
        'amenity': 'amenity',
        'commercial.health_and_beauty.optician': 'doctor\'s office'
    }
    
    for cat in categories:
        for key, value in priority_categories.items():
            if cat.startswith(key):
                return value
    
    return categories[0].split('.')[0] if categories else 'location'

def generate_4_options_names(correct_name, distractors):
    """Generate 4 unique name options with correct answer"""
    options = [correct_name]
    
    # Add distractors
    for distractor in distractors:
        if distractor not in options and len(options) < 4:
            options.append(distractor)
    
    # Fill with generic names if not enough distractors
    generic_names = ["Central Plaza", "Main Street", "City Center", "Grand Mall", "Park Avenue", "Broadway"]
    for name in generic_names:
        if name not in options and len(options) < 4:
            options.append(name)
    
    # Ensure exactly 4 options
    options = options[:4]
    
    # Shuffle options and return with correct answer index
    random.shuffle(options)
    correct_index = options.index(correct_name)
    return options, correct_index


def convert_category_to_human_readable(category):
    if not category:
        return "location"
    return category.replace('_', ' ')
# -------------------------
# Nearby MCQ generators
# -------------------------

def nearest_restaurant_mcq(image_id, pois):
    """I stayed at [location]. Can you recommend the nearest restaurant?"""
    # Find a base location (non-restaurant)
    base_candidates = [p for p in pois if valid_name(p.get("name", "")) and 
                      not any("catering" in cat for cat in p.get("category", []))]
    
    # Find restaurants
    restaurants = [p for p in pois if valid_name(p.get("name", "")) and 
                  any("catering" in cat for cat in p.get("category", []))]

    # restaurants = [p for p in pois if valid_name(p.get("name", "")) and 
    #                any("restaurant" in [cat.split('.')[-1].split('_')[-1] for cat in p.get("category", [])])]
    # base_candidates = [p for p in pois if valid_name(p.get("name", "")) and 
    #               not any("restaurant" in [cat.split('.')[-1].split('_')[-1] for cat in p.get("category", [])])]
    
    if not base_candidates or len(restaurants) < 2:
        return None
    
    base = random.choice(base_candidates)
    
    # Calculate distances to all restaurants
    distances = []
    for restaurant in restaurants:
        try:
            distance = haversine(base["lat"], base["lon"], restaurant["lat"], restaurant["lon"])
            distances.append((distance, restaurant["name"]))
        except (KeyError, TypeError):
            continue
    
    if not distances:
        return None
        
    distances.sort()  # Sort by distance
    closest_restaurant = distances[0][1]
    
    # Get distractors (other restaurants, not necessarily closest)
    distractors = [name for _, name in distances[1:]]
    
    options, correct_index = generate_4_options_names(closest_restaurant, distractors)
    
    contexts = [
        f"I stayed at {base['name']}. Can you recommend the nearest restaurant to my location?",
        f"I'm at {base['name']} and looking for the closest restaurant. Any suggestions?",
        f"I'm staying at {base['name']}. What's the nearest restaurant I can walk to?",
        f"From {base['name']}, which restaurant is the closest?"
    ]
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": random.choice(contexts),
        "option_count": "4",
        "options": "\n".join([f"{i+1}){opt}" for i, opt in enumerate(options)]),
        "answer": str(correct_index + 1),
        "classification": "nearby"
    }

def nearest_service_mcq(image_id, pois):
    """What is the closest [service] to me? I am at [location]."""
    # Find a base location
    base_candidates = [p for p in pois if valid_name(p.get("name", ""))]
    
    # Find service locations
    service_types = {
        'commercial.health_and_beauty': 'doctor\'s office',
        'service.beauty': 'beauty salon',
        'service.cleaning': 'laundry service',
        'commercial.convenience': 'store'
    }
    
    service_pois = []
    for poi in pois:
        if valid_name(poi.get("name", "")):
            for cat in poi.get("category", []):
                for service_cat, service_name in service_types.items():
                    if service_cat in cat:
                        service_pois.append((poi, service_name))
                        break
    
    if not base_candidates or len(service_pois) < 2:
        return None
    
    base = random.choice(base_candidates)
    service_type = service_pois[0][1]  # Get service type
    same_type_services = [poi for poi, stype in service_pois if stype == service_type]
    
    if len(same_type_services) < 2:
        return None
    
    # Calculate distances to services of same type
    distances = []
    for service_poi in same_type_services:
        try:
            distance = haversine(base["lat"], base["lon"], service_poi["lat"], service_poi["lon"])
            distances.append((distance, service_poi["name"]))
        except (KeyError, TypeError):
            continue
    
    if not distances:
        return None
        
    distances.sort()
    closest_service = distances[0][1]
    distractors = [name for _, name in distances[1:]]
    
    options, correct_index = generate_4_options_names(closest_service, distractors)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"What is the closest {convert_category_to_human_readable(service_type)} to me? I am at {base['name']}.",
        "option_count": "4",
        "options": "\n".join([f"{i+1}.{opt}" for i, opt in enumerate(options)]),
        "answer": str(correct_index + 1),
        "classification": "nearby"
    }

def nearest_landmark_mcq(image_id, pois):
    """Which landmark is located closest to [location]?"""
    named_pois = [p for p in pois if valid_name(p.get("name", "")) and 
                  p.get("lat") is not None and p.get("lon") is not None]
    
    if len(named_pois) < 3:
        return None
    
    base = random.choice(named_pois)
    other_pois = [p for p in named_pois if p["name"] != base["name"]]
    
    if len(other_pois) < 2:
        return None
    
    # Calculate distances to all other POIs
    distances = []
    for poi in other_pois:
        try:
            distance = haversine(base["lat"], base["lon"], poi["lat"], poi["lon"])
            distances.append((distance, poi["name"]))
        except (KeyError, TypeError):
            continue
    
    if not distances:
        return None
        
    distances.sort()
    closest_landmark = distances[0][1]
    distractors = [name for _, name in distances[1:]]
    
    options, correct_index = generate_4_options_names(closest_landmark, distractors)
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": f"Which landmark is located closest to {base['name']}?",
        "option_count": "4",
        "options": "\n".join([f"{i+1}){opt}" for i, opt in enumerate(options)]),
        "answer": str(correct_index + 1),
        "classification": "nearby"
    }

def contextual_nearest_mcq(image_id, pois):
    """Contextual questions about finding nearest services"""
    # Find different types of locations
    schools = [p for p in pois if valid_name(p.get("name", "")) and 
               p.get("lat") is not None and p.get("lon") is not None and
               any("education" in cat.lower() or "school" in p["name"].lower() for cat in p.get("category", []))]
    
    hotels = [p for p in pois if valid_name(p.get("name", "")) and 
              p.get("lat") is not None and p.get("lon") is not None and
              any("hotel" in p["name"].lower() or "marriott" in p["name"].lower() for cat in p.get("category", []))]
    
    restaurants = [p for p in pois if valid_name(p.get("name", "")) and 
                  p.get("lat") is not None and p.get("lon") is not None and
                  any("catering" in cat for cat in p.get("category", []))]
    
    base_location = None
    context_type = ""
    target_pois = None
    
    if schools and len(restaurants) >= 2:
        base_location = random.choice(schools)
        context_type = "student"
        target_pois = restaurants
        service_name = "restaurant"
    elif hotels and len(restaurants) >= 2:
        base_location = random.choice(hotels)
        context_type = "guest"
        target_pois = restaurants
        service_name = "restaurant"
    else:
        return None
    
    if not base_location or not target_pois or len(target_pois) < 2:
        return None
    
    # Calculate distances
    distances = []
    for poi in target_pois:
        try:
            distance = haversine(base_location["lat"], base_location["lon"], poi["lat"], poi["lon"])
            distances.append((distance, poi["name"]))
        except (KeyError, TypeError):
            continue
    
    if not distances:
        return None
        
    distances.sort()
    closest_service = distances[0][1]
    distractors = [name for _, name in distances[1:]]
    
    options, correct_index = generate_4_options_names(closest_service, distractors)
    
    if context_type == "student":
        question = f"I am a student at {base_location['name']}. What's the nearest {service_name} for lunch?"
    else:
        question = f"I'm staying at {base_location['name']}. Which {service_name} is closest to my hotel?"
    
    return {
        "image_path": f"images/{image_id}.png",
        "question": question,
        "option_count": "4",
        "options": "\n".join([f"{i+1}){opt}" for i, opt in enumerate(options)]),
        "answer": str(correct_index + 1),
        "classification": "nearby"
    }

# -------------------------
# Main driver
# -------------------------

def generate_nearby_mcqs():
    mcqs = []
    
    for meta_file in META_DIR.glob("*.json"):
        image_id = meta_file.stem
        
        try:
            with open(meta_file, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {meta_file}")
            continue
        
        pois = data.get("pois", [])
        if not pois:
            continue
            
        generators = [
            nearest_restaurant_mcq,
            nearest_service_mcq,
            nearest_landmark_mcq,
            contextual_nearest_mcq
        ]
        
        # Try each generator and pick the first successful one
        for generator in generators:
            try:
                mcq = generator(image_id, pois)
                if mcq:
                    mcqs.append(mcq)
                    break  # Only generate one MCQ per image for nearby questions
            except Exception as e:
                print(f"Error in {generator.__name__} for image {image_id}: {e}")
                continue
    
    with open(OUT_DIR / "nearby_mcqs.json", "w") as f:
        json.dump(mcqs, f, indent=2)
    
    print(f"Generated {len(mcqs)} nearby MCQs")
    return mcqs


if __name__ == "__main__":
    generate_nearby_mcqs()
