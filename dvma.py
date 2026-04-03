from google import genai
from google.genai import types
import base64
import json
import os
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
IMAGES_DIR   = "dataset/images"
METADATA_DIR = "dataset/metadata"
OUTPUT_DIR   = "dataset/metadata_refined"
MAX_RETRIES  = 3
SLEEP_BETWEEN = 1.0   # seconds between API calls (rate limit safety)
# ─────────────────────────────────────────────────────────────────────────────

client = genai.Client(api_key="REMOVED_API_KEY")
MODEL = "gemini-2.5-flash"



def encode_image(image_path: str) -> tuple[str, str]:
    """Returns (base64_data, media_type)."""
    suffix = Path(image_path).suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), media_type


def build_prompt(pois: list[dict]) -> str:
    """
    Builds the verification prompt.
    Passes only name + category to keep token count low.
    """
    poi_list = "\n".join(
        f"{i+1}. name: \"{p['name']}\"  |  categories: {p['category']}"
        for i, p in enumerate(pois)
    )
    return f"""You are a map-label auditor. I will show you a static map image.
Below is a list of POIs (points of interest) that were fetched from OpenStreetMap for the area shown in this map.

Your task:
- Look carefully at ALL visible text labels, icons, and symbols on the map.
- For each POI in the list, decide if it is VISIBLE on the map image.
  A POI is visible if its name (or a clear abbreviation/icon for it) appears on the map.
- Return ONLY a JSON object — no explanation, no markdown fences.

Output format (strict):
{{
  "visible": [1, 3, 5],       // 1-based indices of POIs visible on the map
  "not_visible": [2, 4, 6]    // 1-based indices of POIs NOT visible on the map
}}

POI list:
{poi_list}"""


import google.api_core.exceptions
from PIL import Image

def verify_pois_with_vision(image_path: str, pois: list[dict]) -> list[int]:
    if not pois:
        return []

    prompt = build_prompt(pois)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            suffix = Path(image_path).suffix.lower()
            mime_type = "image/png" if suffix == ".png" else "image/jpeg"

            response = client.models.generate_content(
                model=MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    types.Part.from_text(text=prompt),
                ],
                config=types.GenerateContentConfig(temperature=0),
            )

            raw = response.text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            return result.get("visible", [])

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "exhausted" in err.lower():
                print(f"  [quota] Daily limit hit — waiting 60s (attempt {attempt})...")
                time.sleep(60)
            elif "json" in err.lower():
                print(f"  [warn] JSON parse error on attempt {attempt}: {e}")
                time.sleep(3)
            else:
                print(f"  [error] Attempt {attempt}: {e}")
                time.sleep(attempt * 3)

    print("  [warn] All retries failed — keeping all POIs.")
    return list(range(1, len(pois) + 1))
    
def refine_metadata(metadata: dict, visible_indices: set[int]) -> dict:
    """
    Returns a new metadata dict keeping only visible POIs
    and recomputing derived fields.
    """
    original_pois = metadata.get("pois", [])

    # visible_indices are 1-based
    refined_pois = [
        poi for i, poi in enumerate(original_pois, start=1)
        if i in visible_indices
    ]

    all_cats = [cat for poi in refined_pois for cat in poi.get("category", [])]
    unique_cats = list(set(all_cats))

    return {
        **metadata,                          # keep image, center_lat, center_lon, bbox
        "poi_count":             len(refined_pois),
        "unique_categories":     unique_cats,
        "poi_count_per_category": {
            cat: sum(1 for poi in refined_pois if cat in poi.get("category", []))
            for cat in unique_cats
        },
        "pois":                  refined_pois,
        # audit trail
        "refinement": {
            "original_poi_count": len(original_pois),
            "removed_count":      len(original_pois) - len(refined_pois),
            "model":              MODEL,
        }
    }


def process_all(images_dir: str, metadata_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    meta_files = sorted(Path(metadata_dir).glob("*.json"))
    print(f"Found {len(meta_files)} metadata files.\n")

    total_original = 0
    total_refined  = 0

    for meta_path in meta_files:
        stem = meta_path.stem                          # e.g. "42"
        image_path = Path(images_dir) / f"{stem}.png"

        if not image_path.exists():
            # try .jpg fallback
            image_path = Path(images_dir) / f"{stem}.jpg"
        if not image_path.exists():
            print(f"[skip] No image found for {stem}")
            continue

        with open(meta_path) as f:
            metadata = json.load(f)

        pois = metadata.get("pois", [])
        print(f"[{stem}] {len(pois)} POIs → verifying against {image_path.name}...")

        visible_indices = verify_pois_with_vision(str(image_path), pois)
        visible_set     = set(visible_indices)

        refined = refine_metadata(metadata, visible_set)

        out_path = Path(output_dir) / meta_path.name
        with open(out_path, "w") as f:
            json.dump(refined, f, indent=2)

        kept    = refined["poi_count"]
        removed = refined["refinement"]["removed_count"]
        print(f"  ✓ kept {kept}, removed {removed} → {out_path}")

        total_original += len(pois)
        total_refined  += kept

        time.sleep(SLEEP_BETWEEN)

    print(f"\n── Summary ──────────────────────────────")
    print(f"  Total POIs before : {total_original}")
    print(f"  Total POIs after  : {total_refined}")
    print(f"  Total removed     : {total_original - total_refined}")
    print(f"  Retention rate    : {total_refined/max(total_original,1)*100:.1f}%")


if __name__ == "__main__":
    process_all(IMAGES_DIR, METADATA_DIR, OUTPUT_DIR)

