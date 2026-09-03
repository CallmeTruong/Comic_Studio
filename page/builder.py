from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageFilter
import json
import re
from config import CONFIG

from .layouts import LAYOUT_SETTINGS, compute_layout_placements, select_layout_name

def load_panels(panels_dir: str) -> Dict[str, Image.Image]:
    panels = {}
    panel_path = Path(panels_dir)
    
    panel_files = sorted(panel_path.glob("panel_*.png"))
    if not panel_files:
        panel_files = sorted(panel_path.glob("*.png"))
    
    for panel_file in panel_files:
        panel_id = panel_file.stem
        panels[panel_id] = Image.open(panel_file).convert("RGB")
    
    return panels

def get_panel_list_ordered(panels_dict: Dict[str, Image.Image]) -> List[Image.Image]:
    panel_ids = sorted(panels_dict.keys(), key=lambda x: (
        int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 999,
        x
    ))
    return [panels_dict[pid] for pid in panel_ids]

def preserve_aspect_resize(
    image: Image.Image,
    target_width: int,
    target_height: int,
    method: Image.Resampling = Image.Resampling.LANCZOS,
    fill_mode: str = "crop",
    important_region: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    original_width, original_height = image.size
    original_aspect = original_width / original_height
    target_aspect = target_width / target_height
    
    if fill_mode == "crop":
        if original_aspect > target_aspect:
            new_height = target_height
            new_width = int(target_height * original_aspect)
        else:
            new_width = target_width
            new_height = int(target_width / original_aspect)
        
        resized = image.resize((new_width, new_height), method)
        
        if new_width != target_width or new_height != target_height:
            if important_region:
                char_left, char_top, char_width, char_height = important_region
                scale_x = new_width / original_width
                scale_y = new_height / original_height
                
                scaled_char_center_x = int(char_left * scale_x + char_width * scale_x / 2)
                scaled_char_center_y = int(char_top * scale_y + char_height * scale_y / 2)
                
                crop_x = max(0, min(scaled_char_center_x - target_width // 2, new_width - target_width))
                crop_y = max(0, min(scaled_char_center_y - target_height // 2, new_height - target_height))
            else:
                crop_x = (new_width - target_width) // 2
                crop_y = (new_height - target_height) // 2
            
            result = resized.crop((crop_x, crop_y, crop_x + target_width, crop_y + target_height))
            return result
        
        return resized
    elif fill_mode == "smart_pad":
        scale = min(target_width / original_width, target_height / original_height)
        new_width = max(1, int(original_width * scale))
        new_height = max(1, int(original_height * scale))

        resized = image.resize((new_width, new_height), method)
        blurred_bg = (
            image.resize((target_width, target_height), Image.Resampling.BILINEAR)
            .filter(ImageFilter.GaussianBlur(radius=25))
        )

        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        blurred_bg.paste(resized, (paste_x, paste_y))
        return blurred_bg
    else:
        if original_aspect > target_aspect:
            new_width = target_width
            new_height = int(target_width / original_aspect)
        else:
            new_width = int(target_height * original_aspect)
            new_height = target_height
        
        resized = image.resize((new_width, new_height), method)
        
        if new_width != target_width or new_height != target_height:
            result = Image.new("RGB", (target_width, target_height), (255, 255, 255))
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            result.paste(resized, (paste_x, paste_y))
            return result
        
        return resized

def build_comic_page_with_grid(
    panels: List[Image.Image],
    layout_name: str = "Layout1",
    page_width: int = None,
    page_height: int = None,
    margin: int = None,
    gutter: int = None,
) -> Tuple[Image.Image, List[Tuple[int, int, int, int]]]:
    page_width = page_width or CONFIG.page.width
    page_height = page_height or CONFIG.page.height
    margin = margin or CONFIG.page.margin
    gutter = gutter or CONFIG.page.gutter
    if layout_name not in LAYOUT_SETTINGS:
        layout_name = "Layout1"

    placements = compute_layout_placements(
        layout_name,
        len(panels),
        page_width=page_width,
        page_height=page_height,
        margin=margin,
        gutter=gutter,
    )

    page = Image.new("RGB", (page_width, page_height), (255, 255, 255))
    panel_positions: List[Tuple[int, int, int, int]] = []

    for placement, panel_img in zip(placements, panels):
        panel_width = placement["width"]
        panel_height = placement["height"]
        x = placement["x"]
        y = placement["y"]

        from bubbles.injector import find_character_bounding_box

        character_bbox = find_character_bounding_box(panel_img)
        important_region = character_bbox if character_bbox else None

        resized_panel = preserve_aspect_resize(
            panel_img,
            panel_width,
            panel_height,
            fill_mode="smart_pad",
            important_region=important_region,
        )

        idx = placement["idx"]
        print(
            f"[PAGE] Panel {idx+1}: placed at grid ({placement['row']},{placement['col']}), "
            f"size {panel_width}x{panel_height}, pos ({x},{y})"
        )
        page.paste(resized_panel, (x, y))
        panel_positions.append((x, y, panel_width, panel_height))

    return page, panel_positions

def build_comic_page(
    panels_dir: str = "Panels_image",
    output_path: str = "comic_page.png",
    schema_path: Optional[str] = None,
    inject_bubbles: bool = True,
    use_adaptive_layout: bool = True,
    layout_name: str = "Layout1",
) -> Image.Image:
    panels_dict = load_panels(panels_dir)
    
    if not panels_dict:
        raise ValueError(f"Không tìm thấy panels trong {panels_dir}")
    
    num_panels = len(panels_dict)
    print(f"[INFO] Tìm thấy {num_panels} panels")
    
    panel_list = get_panel_list_ordered(panels_dict)
    
    if use_adaptive_layout:
        if layout_name not in LAYOUT_SETTINGS:
            layout_name = select_layout_name(num_panels)
        print(f"[PAGE] Using layout: {layout_name}")
        page, panel_positions = build_comic_page_with_grid(
            panel_list,
            layout_name=layout_name,
        )
    else:
        page_width = CONFIG.page.width
        page_height = CONFIG.page.height
        margin = CONFIG.page.margin
        gutter = CONFIG.page.gutter
        
        page = Image.new("RGB", (page_width, page_height), (255, 255, 255))
        panel_positions = []
        
        if num_panels == 1:
            resized = preserve_aspect_resize(panel_list[0], page_width - margin * 2, page_height - margin * 2)
            x = margin
            y = margin
            page.paste(resized, (x, y))
            panel_positions.append((x, y, resized.width, resized.height))
        elif num_panels == 2:
            panel_height = (page_height - margin * 2 - gutter) // 2
            panel_width = page_width - margin * 2
            
            for i, panel_img in enumerate(panel_list):
                resized = preserve_aspect_resize(panel_img, panel_width, panel_height)
                y = margin + i * (panel_height + gutter)
                x = margin + (panel_width - resized.width) // 2
                page.paste(resized, (x, y))
                panel_positions.append((x, y, resized.width, resized.height))
        elif num_panels == 3:
            top_height = (page_height - margin * 2 - gutter * 2) // 3
            top_width = page_width - margin * 2
            
            for i, panel_img in enumerate(panel_list):
                resized = preserve_aspect_resize(panel_img, top_width, top_height)
                y = margin + i * (top_height + gutter)
                x = margin + (top_width - resized.width) // 2
                page.paste(resized, (x, y))
                panel_positions.append((x, y, resized.width, resized.height))
        else:
            panel_height = (page_height - margin * 2 - gutter * 3) // 4
            panel_width = page_width - margin * 2
            
            for i, panel_img in enumerate(panel_list[:4]):
                resized = preserve_aspect_resize(panel_img, panel_width, panel_height)
                y = margin + i * (panel_height + gutter)
                x = margin + (panel_width - resized.width) // 2
                page.paste(resized, (x, y))
                panel_positions.append((x, y, resized.width, resized.height))
    
    if inject_bubbles and schema_path:
        try:
            from bubbles.injector import inject_bubbles_to_page
            page = inject_bubbles_to_page(page, schema_path, panels_dir, panel_positions)
        except Exception as e:
            print(f"[WARN] Bubble injection failed: {e}")
    
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    page.save(output_path_obj, quality=95)
    
    return page
