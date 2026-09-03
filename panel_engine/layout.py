from __future__ import annotations
from .smart_analyzer import analyze_layout_clues_smart

def analyze_layout_clues(panel_prompt: str, layout_hint: str | None = None) -> dict:
    return analyze_layout_clues_smart(panel_prompt, layout_hint)

