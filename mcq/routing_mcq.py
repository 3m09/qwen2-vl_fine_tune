import random

def generate_routing_mcq(meta):
    roads = meta.get("roads", [])
    if len(roads) < 2:
        return None

    correct_road = random.choice(roads)["name"]

    other_roads = [
        r["name"] for r in roads
        if r["name"] != correct_road
    ]

    if len(other_roads) < 2:
        return None

    distractors = random.sample(other_roads, 2)
    options = [correct_road] + distractors
    random.shuffle(options)

    return {
        "question": "Which road shown on the map would be used in the route?",
        "options": options,
        "answer": options.index(correct_road),
        "classification": "routing"
    }
