import json
from pathlib import Path

STATE_PATH = Path("data/scene_state.json")

def init_scene_state():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        save_scene_state({
            "current_chapter": 1,
            "last_page_rendered": 0,
            "time_of_day": "Day",
            "location": "Unknown",
            "character_positions": {},
            "character_held_items": {},
            "ongoing_action": "Starting the story"
        })

def get_scene_state() -> dict:
    if not STATE_PATH.exists():
        init_scene_state()
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_scene_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
