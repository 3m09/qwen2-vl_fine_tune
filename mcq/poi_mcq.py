import random

def generate_poi_mcq(meta, global_poi_pool):
    pois = meta["pois"]
    correct = random.choice(pois)["name"]

    same_type = [
        p for p in global_poi_pool
        if p["name"] != correct
    ]

    distractors = random.sample(same_type, 3)
    options = [correct] + [d["name"] for d in distractors]
    random.shuffle(options)

    return {
        "question": "Which of the following POIs is visible in the map?",
        "options": options,
        "answer": options.index(correct),
        "classification": "poi"
    }
