from utils.utils import haversine

def generate_nearby_mcq(meta):
    pois = meta["pois"]
    if len(pois) < 2:
        return None

    base = pois[0]
    distances = []

    for p in pois[1:]:
        d = haversine(base["lat"], base["lon"], p["lat"], p["lon"])
        distances.append((d, p["name"]))

    distances.sort()
    correct = distances[0][1]

    distractors = [name for _, name in distances[1:4]]
    options = [correct] + distractors

    return {
        "question": f"Which landmark is located closest to {base['name']}?",
        "options": options,
        "answer": 0,
        "classification": "nearby"
    }
