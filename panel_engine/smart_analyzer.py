from __future__ import annotations
import re
from typing import Dict

class SmartLayoutAnalyzer:
    X_POSITION_PATTERNS = [
        (r'\b(left|left side|left of|bên trái|trái)\b', 'left', 10),
        (r'\b(right|right side|right of|bên phải|phải)\b', 'right', 10),
        (r'\b(center|centre|middle|giữa|trung tâm)\b', 'center', 9),
    ]
    
    Y_POSITION_PATTERNS = [
        (r'\b(top|upper|above|trên|phía trên)\b', 'top', 10),
        (r'\b(bottom|lower|below|ground|floor|dưới|phía dưới)\b', 'bottom', 10),
        (r'\b(middle|mid|center|giữa)\b', 'middle', 9),
    ]
    
    DEPTH_PATTERNS = [
        (r'\b(foreground|close-up|closeup|extreme\s+close-up|cận cảnh|gần)\b', 'foreground', 10),
        (r'\b(background|far|distant|far\s+away|xa|phía sau)\b', 'background', 10),
        (r'\b(mid|middle|midground|giữa)\b', 'mid', 9),
    ]

def analyze_layout_clues_smart(panel_prompt: str, layout_hint: str | None = None) -> dict:
    analyzer = SmartLayoutAnalyzer()
    prompt_lower = panel_prompt.lower()
    
    x_align = "center"
    y_align = "middle"
    depth = "mid"
    zoom_out = False
    zoom_in = False
    
    for pattern, value, priority in analyzer.X_POSITION_PATTERNS:
        if re.search(pattern, prompt_lower):
            x_align = value
            break
    
    for pattern, value, priority in analyzer.Y_POSITION_PATTERNS:
        if re.search(pattern, prompt_lower):
            y_align = value
            break
    
    for pattern, value, priority in analyzer.DEPTH_PATTERNS:
        if re.search(pattern, prompt_lower):
            depth = value
            if value == "foreground":
                zoom_in = True
            elif value == "background":
                zoom_out = True
            break
    
    return {
        "x_align": x_align,
        "y_align": y_align,
        "depth": depth,
        "zoom_out": zoom_out,
        "zoom_in": zoom_in,
    }

def infer_emotion_from_dialogues_smart(dialogues) -> str:
    if not dialogues:
        return ""
    
    emotion_keywords = {
        "happy": ["vui", "hạnh phúc", "yay", "great", "wonderful"],
        "sad": ["buồn", "sad", "cry", "tears"],
        "angry": ["giận", "angry", "mad", "furious"],
        "surprised": ["ngạc nhiên", "surprised", "wow", "what"],
        "scared": ["sợ", "scared", "afraid", "fear"],
    }
    
    text = " ".join([d.text if hasattr(d, 'text') else str(d) for d in dialogues]).lower()
    
    for emotion, keywords in emotion_keywords.items():
        if any(kw in text for kw in keywords):
            return emotion
    
    return ""

