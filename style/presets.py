from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class StylePreset:
    name: str
    prompt_tags: List[str]
    negative_tags: List[str]


STYLE_PRESETS: Dict[str, StylePreset] = {
    "neutral": StylePreset(
        name="neutral",
        prompt_tags=["cinematic lighting", "highly detailed illustration"],
        negative_tags=["blurry", "low quality", "distorted anatomy"],
    ),
    "american_modern": StylePreset(
        name="american_modern",
        prompt_tags=[
            "modern american comic style",
            "bold inks",
            "dynamic classroom scene",
        ],
        negative_tags=[
            "manga",
            "anime",
            "greyscale",
            "3d render",
        ],
    ),
    "japanese_manga": StylePreset(
        name="japanese_manga",
        prompt_tags=[
            "japanese manga panel",
            "inked line art",
            "expressive characters",
        ],
        negative_tags=[
            "color photo",
            "western comic",
            "oil painting",
        ],
    ),
    "school_slice_of_life": StylePreset(
        name="school_slice_of_life",
        prompt_tags=[
            "slice of life comic",
            "bright daylight classroom",
            "warm color palette",
            "natural facial expressions",
        ],
        negative_tags=[
            "dark horror",
            "sci-fi background",
            "empty classroom",
        ],
    ),
}


def get_style_preset(name: str | None) -> StylePreset:
    if not name:
        return STYLE_PRESETS["neutral"]
    return STYLE_PRESETS.get(name, STYLE_PRESETS["neutral"])

