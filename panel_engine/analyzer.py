import json
from pathlib import Path
from typing import Dict, Optional
from PIL import Image

def analyze_panels_for_layout(
    panels: Dict[str, Image.Image],
    panel_sizes_metadata_path: Optional[str] = None,
) -> Dict:
    if panel_sizes_metadata_path and Path(panel_sizes_metadata_path).exists():
        with open(panel_sizes_metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return {
            "panel_sizes": metadata,
            "num_panels": len(panels),
        }
    
    return {
        "panel_sizes": {},
        "num_panels": len(panels),
    }

def suggest_layout(
    panel_analysis: Dict,
    available_layouts: Dict,
) -> str:
    num_panels = panel_analysis.get("num_panels", 4)
    
    if num_panels <= 1:
        return "Layout0"
    elif num_panels <= 2:
        return "Layout1"
    else:
        return "Layout1"

