import json
import math
import re
import textwrap
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Set
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from .segment import detect_character_bbox_mediapipe
from style.fonts import load_font, get_font_name_for_emotion

BUBBLE_STYLES: Dict[str, Dict] = {
    "default": {"shape": "oval", "line": "smooth"},
    "surprise": {"shape": "rounded", "line": "smooth"},
    "angry": {"shape": "burst", "line": "jagged"},
    "whisper": {"shape": "rounded", "line": "smooth"},
    "thought": {"shape": "oval", "line": "smooth"},
}


def choose_bubble_style(emotion: Optional[str]) -> Dict:
    if not emotion:
        return BUBBLE_STYLES["default"]
    emotion_lower = emotion.lower()
    if any(key in emotion_lower for key in ["shock", "surpris", "panic"]):
        return BUBBLE_STYLES["surprise"]
    if any(key in emotion_lower for key in ["angry", "shout", "furious"]):
        return BUBBLE_STYLES["angry"]
    if any(key in emotion_lower for key in ["sad", "soft", "apolog"]):
        return BUBBLE_STYLES["whisper"]
    if "thought" in emotion_lower:
        return BUBBLE_STYLES["thought"]
    return BUBBLE_STYLES["default"]

def wrap_text_to_lines(
    text: str, 
    font: ImageFont.FreeTypeFont, 
    max_width: int,
    safety_margin: int = 10  # Add safety margin
) -> List[str]:
    """
    Wrap text to fit within max_width with safety margin.
    CRITICAL: This must be called with EXACT same max_width as bubble interior.
    """
    max_width = max(60, max_width - safety_margin)  # Minimum 60px, with safety margin
    lines: List[str] = []
    
    # Split by existing line breaks first
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        words = paragraph.split()
        current_line: List[str] = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width or not current_line:
                current_line.append(word)
            else:
                # Line is full, save it and start new line
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        
        # Add remaining words
        if current_line:
            lines.append(" ".join(current_line))
    
    # Fallback if something went wrong
    if not lines:
        lines = [text]
    
    return lines


class ZoneManager:
    """Quản lý việc phân bổ bubbles vào các zones"""
    def __init__(self, zones: List[Tuple[int, int, int, int, int]]):
        self.zones = zones  # List[(x, y, w, h, priority)]
        self.zone_assignments: Dict[int, List[Tuple[int, int, int, int]]] = {i: [] for i in range(len(zones))}
        self.used_zones: Set[int] = set()
    
    def get_next_available_zone(self) -> Optional[int]:
        """Lấy zone tiếp theo chưa được sử dụng"""
        for i, zone in enumerate(self.zones):
            if i not in self.used_zones:
                return i
        return None
    
    def mark_zone_used(self, zone_idx: int, bubble_rect: Tuple[int, int, int, int]):
        """Đánh dấu zone đã được sử dụng"""
        self.used_zones.add(zone_idx)
        self.zone_assignments[zone_idx].append(bubble_rect)


def create_zones_from_panel(
    panel_bounds: Tuple[int, int, int, int],
    character_bbox: Optional[Tuple[int, int, int, int]],
    all_character_bboxes: List[Tuple[int, int, int, int]],
    border_padding: int = 20
) -> List[Tuple[int, int, int, int, int]]:
    """
    Tạo các zones KHÔNG OVERLAP nhau trong panel
    Priority càng nhỏ = càng ưu tiên
    """
    panel_x, panel_y, panel_w, panel_h = panel_bounds
    zones = []
    
    # Merge all characters
    all_chars = list(all_character_bboxes) if all_character_bboxes else []
    if character_bbox and character_bbox not in all_chars:
        all_chars.append(character_bbox)
    
    if not all_chars:
        # Không có character - chia panel thành 6 vùng (2x3 grid)
        cell_w = panel_w // 3
        cell_h = panel_h // 2
        
        priority = 1
        for row in range(2):
            for col in range(3):
                x = panel_x + col * cell_w + border_padding
                y = panel_y + row * cell_h + border_padding
                w = cell_w - border_padding * 2
                h = cell_h - border_padding * 2
                
                if w > 80 and h > 60:
                    zones.append((x, y, w, h, priority))
                    priority += 1
        
        return zones
    
    # Có character - tạo zones xung quanh từng character
    char_margin = 85  # Tăng margin lên 85px
    
    for char_idx, char_bbox in enumerate(all_chars):
        if not char_bbox:
            continue
        
        char_left, char_top, char_width, char_height = char_bbox
        char_right = char_left + char_width
        char_bottom = char_top + char_height
        
        # Zone 1: Phía TRÊN character (ưu tiên cao nhất)
        top_zone_y = panel_y + border_padding
        top_zone_h = char_top - top_zone_y - char_margin
        
        if top_zone_h > 80:
            # Chia phía trên thành 2 zones: trái và phải
            mid_x = (panel_x + panel_x + panel_w) // 2
            
            # Top-Left
            if char_left > panel_x + 100:
                zones.append((
                    panel_x + border_padding,
                    top_zone_y,
                    min(char_left - panel_x - char_margin, mid_x - panel_x),
                    top_zone_h,
                    1 + char_idx * 10  # Priority 1, 11, 21...
                ))
            
            # Top-Right
            if panel_x + panel_w - char_right > 100:
                zones.append((
                    max(char_right + char_margin, mid_x),
                    top_zone_y,
                    (panel_x + panel_w) - max(char_right + char_margin, mid_x) - border_padding,
                    top_zone_h,
                    2 + char_idx * 10  # Priority 2, 12, 22...
                ))
        
        # Zone 2: Trái character (full height)
        left_zone_w = char_left - panel_x - char_margin - border_padding
        if left_zone_w > 100:
            zones.append((
                panel_x + border_padding,
                panel_y + border_padding,
                left_zone_w,
                panel_h - border_padding * 2,
                3 + char_idx * 10  # Priority 3, 13, 23...
            ))
        
        # Zone 3: Phải character (full height)
        right_zone_x = char_right + char_margin
        right_zone_w = (panel_x + panel_w) - right_zone_x - border_padding
        if right_zone_w > 100:
            zones.append((
                right_zone_x,
                panel_y + border_padding,
                right_zone_w,
                panel_h - border_padding * 2,
                4 + char_idx * 10  # Priority 4, 14, 24...
            ))
        
        # Zone 4: Dưới character
        bottom_zone_y = char_bottom + char_margin
        bottom_zone_h = (panel_y + panel_h) - bottom_zone_y - border_padding
        
        if bottom_zone_h > 80:
            # Chia phía dưới thành 2 zones
            mid_x = (panel_x + panel_x + panel_w) // 2
            
            # Bottom-Left
            if char_left > panel_x + 100:
                zones.append((
                    panel_x + border_padding,
                    bottom_zone_y,
                    min(char_left - panel_x - border_padding, mid_x - panel_x),
                    bottom_zone_h,
                    5 + char_idx * 10
                ))
            
            # Bottom-Right
            if panel_x + panel_w - char_right > 100:
                zones.append((
                    max(char_right + border_padding, mid_x),
                    bottom_zone_y,
                    (panel_x + panel_w) - max(char_right + border_padding, mid_x) - border_padding,
                    bottom_zone_h,
                    6 + char_idx * 10
                ))
    
    # Loại bỏ zones quá nhỏ
    zones = [z for z in zones if z[2] >= 90 and z[3] >= 70]
    
    # Loại bỏ zones overlap nhau
    final_zones = []
    for i, zone1 in enumerate(zones):
        x1, y1, w1, h1, p1 = zone1
        overlaps = False
        
        for j, zone2 in enumerate(zones):
            if i >= j:
                continue
            x2, y2, w2, h2, p2 = zone2
            
            # Kiểm tra overlap
            if not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1):
                # Có overlap - giữ zone có priority cao hơn
                if p1 > p2:
                    overlaps = True
                    break
        
        if not overlaps:
            final_zones.append(zone1)
    
    # Sắp xếp theo priority
    final_zones.sort(key=lambda z: z[4])
    
    return final_zones


def find_position_in_zone(
    zone: Tuple[int, int, int, int, int],
    bubble_width: int,
    bubble_height: int,
    existing_bubbles: List[Tuple[int, int, int, int]],
    all_character_bboxes: List[Tuple[int, int, int, int]],
    page_width: int,
    page_height: int,
    border_padding: int = 20
) -> Optional[Tuple[int, int]]:
    """Tìm vị trí trong zone cụ thể"""
    zone_x, zone_y, zone_w, zone_h, priority = zone
    
    # Kiểm tra zone đủ lớn
    if zone_w < bubble_width + 20 or zone_h < bubble_height + 20:
        return None
    
    def is_valid(x: int, y: int) -> bool:
        # 1. Trong bounds
        if (x < border_padding or y < border_padding or
            x + bubble_width > page_width - border_padding or
            y + bubble_height > page_height - border_padding):
            return False
        
        # 2. Trong zone
        if (x < zone_x or y < zone_y or
            x + bubble_width > zone_x + zone_w or
            y + bubble_height > zone_y + zone_h):
            return False
        
        # 3. Không đè character (75px margin)
        for char_bbox in all_character_bboxes:
            if not char_bbox:
                continue
            char_left, char_top, char_width, char_height = char_bbox
            margin = 75
            
            if not (x + bubble_width + margin <= char_left or
                    char_left + char_width + margin <= x or
                    y + bubble_height + margin <= char_top or
                    char_top + char_height + margin <= y):
                return False
        
        # 4. Không đè existing bubbles (70px margin)
        margin = 70
        for ex, ey, ew, eh in existing_bubbles:
            if not (x + bubble_width + margin <= ex or
                    ex + ew + margin <= x or
                    y + bubble_height + margin <= ey or
                    ey + eh + margin <= y):
                return False
        
        return True
    
    # Quét zone theo grid
    grid_step = 12
    best_position = None
    best_score = float('inf')
    
    for y in range(zone_y, min(zone_y + zone_h - bubble_height + 1, zone_y + zone_h), grid_step):
        for x in range(zone_x, min(zone_x + zone_w - bubble_width + 1, zone_x + zone_w), grid_step):
            if is_valid(x, y):
                # Tính điểm: ưu tiên góc trên trái của zone
                score = (x - zone_x) ** 2 + (y - zone_y) ** 2
                if score < best_score:
                    best_score = score
                    best_position = (x, y)
    
    return best_position


def find_bubble_position(
    bubble_width: int,
    bubble_height: int,
    panel_bounds: Tuple[int, int, int, int],
    character_bbox: Optional[Tuple[int, int, int, int]],
    existing_bubbles: List[Tuple[int, int, int, int]],
    page_width: int,
    page_height: int,
    attempts: int = 200,
) -> Tuple[int, int]:
    """Tìm vị trí cho bubble với zone-based approach"""
    panel_x, panel_y, panel_w, panel_h = panel_bounds
    border_padding = 20
    
    all_chars = [character_bbox] if character_bbox else []
    
    # Tạo zones
    zones = create_zones_from_panel(panel_bounds, character_bbox, all_chars, border_padding)
    
    # Tạo zone manager
    zone_manager = ZoneManager(zones)
    
    # Thử tìm trong zone chưa dùng
    zone_idx = zone_manager.get_next_available_zone()
    if zone_idx is not None:
        zone = zones[zone_idx]
        position = find_position_in_zone(
            zone, bubble_width, bubble_height,
            existing_bubbles, all_chars,
            page_width, page_height, border_padding
        )
        if position:
            return position
    
    # Fallback: thử tất cả zones
    for zone in zones:
        position = find_position_in_zone(
            zone, bubble_width, bubble_height,
            existing_bubbles, all_chars,
            page_width, page_height, border_padding
        )
        if position:
            return position
    
    # Fallback cuối: góc panel
    fallback_x = max(panel_x + border_padding, border_padding)
    fallback_y = max(panel_y + border_padding, border_padding)
    fallback_x = min(fallback_x, page_width - bubble_width - border_padding)
    fallback_y = min(fallback_y, page_height - bubble_height - border_padding)
    
    return (fallback_x, fallback_y)


def sample_bubble_position(
    panel_bounds: Tuple[int, int, int, int],
    bubble_width: int,
    bubble_height: int,
    character_bbox: Optional[Tuple[int, int, int, int]],
    border_padding: int,
    all_character_bboxes: List[Tuple[int, int, int, int]],
    existing_bubbles: List[Tuple[int, int, int, int]],
    page_width: int,
    page_height: int,
    max_attempts: int = 150,
) -> Tuple[int, int, int, int]:
    """Sample position với zone management"""
    panel_x, panel_y, panel_w, panel_h = panel_bounds
    
    all_chars = list(all_character_bboxes) if all_character_bboxes else []
    if character_bbox and character_bbox not in all_chars:
        all_chars.append(character_bbox)
    
    # Tạo zones
    zones = create_zones_from_panel(panel_bounds, character_bbox, all_chars, border_padding)
    
    # Thử từng zone
    for zone in zones:
        position = find_position_in_zone(
            zone, bubble_width, bubble_height,
            existing_bubbles, all_chars,
            page_width, page_height, border_padding
        )
        
        if position:
            x, y = position
            
            # Verify 70% trong panel
            overlap_left = max(x, panel_x)
            overlap_right = min(x + bubble_width, panel_x + panel_w)
            overlap_top = max(y, panel_y)
            overlap_bottom = min(y + bubble_height, panel_y + panel_h)
            
            if overlap_right > overlap_left and overlap_bottom > overlap_top:
                overlap_area = (overlap_right - overlap_left) * (overlap_bottom - overlap_top)
                bubble_area = bubble_width * bubble_height
                
                if (overlap_area / bubble_area) >= 0.7:
                    return (x, y, bubble_width, bubble_height)
    
    # Fallback
    fallback_x = max(panel_x + border_padding, border_padding)
    fallback_y = max(panel_y + border_padding, border_padding)
    fallback_x = min(fallback_x, page_width - bubble_width - border_padding, 
                     panel_x + panel_w - bubble_width - border_padding)
    fallback_y = min(fallback_y, page_height - bubble_height - border_padding,
                     panel_y + panel_h - bubble_height - border_padding)
    
    return (max(border_padding, fallback_x), max(border_padding, fallback_y), 
            bubble_width, bubble_height)

def find_character_bounding_box(image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    bbox = detect_character_bbox_mediapipe(image)
    if bbox:
        return bbox

    try:
        from rembg import remove
        import io

        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        output_bytes = remove(img_bytes.getvalue())
        mask_image = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
        mask_array = np.array(mask_image.split()[3])

        foreground_pixels = np.where(mask_array > 128)

        if len(foreground_pixels[0]) == 0:
            return None

        min_y = np.min(foreground_pixels[0])
        max_y = np.max(foreground_pixels[0])
        min_x = np.min(foreground_pixels[1])
        max_x = np.max(foreground_pixels[1])

        width, height = image.size
        padding_x = int((max_x - min_x) * 0.1)
        padding_y = int((max_y - min_y) * 0.1)

        left = max(0, min_x - padding_x)
        top = max(0, min_y - padding_y)
        right = min(width, max_x + padding_x)
        bottom = min(height, max_y + padding_y)

        return (left, top, right - left, bottom - top)
    except Exception as e:
        print(f"[WARN] Character detection failed: {e}")
        return None

def split_text_into_bubbles(text: str) -> List[str]:
    """
    Keep entire dialogue text in ONE bubble.
    Comic script should already have short, concise dialogue per character.
    """
    # Option 1: Never split - one dialogue = one bubble
    return [text.strip()] if text.strip() else []
    
    # Option 2: Only split if EXTREMELY long (>100 chars)
    # if len(text) > 100:
    #     # Split on sentence endings only
    #     sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    #     return [s.strip() for s in sentences if s.strip()]
    # return [text.strip()] if text.strip() else []

def is_rect_overlapping(
    rect1: Tuple[int, int, int, int],
    rect2: Tuple[int, int, int, int]
) -> bool:
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    
    return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)

def calculate_bubble_locations(
    bubble_texts: List[str],
    image_width: int,
    image_height: int,
    character_bbox: Optional[Tuple[int, int, int, int]] = None,
    existing_bubbles: List[Tuple[int, int, int, int]] = None,
) -> List[Tuple[int, int, int, int]]:
    if existing_bubbles is None:
        existing_bubbles = []
    
    padding = 50
    border_padding = max(10, int(min(image_width, image_height) * 0.1))
    available_width = image_width - border_padding * 2
    available_height = image_height - border_padding * 2
    max_attempts = 100
    
    font_size = max(20, min(image_width, image_height) // 36)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    bubble_locations = []
    
    for i, text in enumerate(bubble_texts):
        text_bbox = font.getbbox(text)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        bubble_padding = 24
        max_bubble_width = min(available_width, int(image_width * 0.33))
        bubble_width = min(max(text_width + bubble_padding * 2, 100), max_bubble_width)
        bubble_height = min(max(text_height + bubble_padding * 2, 50), available_height)
        
        x, y = 0, 0
        attempts = 0
        
        while attempts < max_attempts:
            if character_bbox:
                char_left, char_top, char_width, char_height = character_bbox
                character_middle_x = char_left + char_width // 2
                
                if attempts < 30:
                    left_side = border_padding + np.random.random() * (character_middle_x - border_padding - bubble_width)
                    right_side = character_middle_x + np.random.random() * (image_width - character_middle_x - border_padding - bubble_width)
                    x = left_side if np.random.random() < 0.5 else right_side
                else:
                    x = border_padding + np.random.random() * (available_width - bubble_width)
                
                y = border_padding + (i / len(bubble_texts)) * available_height
            else:
                x = border_padding + np.random.random() * (available_width - bubble_width)
                y = border_padding + (i / len(bubble_texts)) * available_height
            
            bubble_rect = (int(x), int(y), bubble_width, bubble_height)
            
            overlap_with_character = False
            if character_bbox:
                char_left, char_top, char_width, char_height = character_bbox
                char_rect = (char_left, char_top, char_width, char_height)
                if is_rect_overlapping(bubble_rect, char_rect):
                    overlap_with_character = True
            
            overlap_with_bubbles = any(is_rect_overlapping(bubble_rect, existing_bubble) for existing_bubble in existing_bubbles)
            
            if not overlap_with_character and not overlap_with_bubbles:
                bubble_locations.append(bubble_rect)
                existing_bubbles.append(bubble_rect)
                break
            
            attempts += 1
        
        if attempts >= max_attempts:
            x = border_padding + (i % 3) * (available_width // 3)
            y = border_padding + (i // 3) * (available_height // max(1, (len(bubble_texts) + 2) // 3))
            bubble_rect = (int(x), int(y), bubble_width, bubble_height)
            bubble_locations.append(bubble_rect)
            existing_bubbles.append(bubble_rect)
    
    return bubble_locations

def adjust_bubble_location(
    location: Tuple[int, int, int, int],
    character_bbox: Optional[Tuple[int, int, int, int]],
    image_width: int,
    image_height: int,
    border_padding: int,
    all_character_bboxes: List[Tuple[int, int, int, int]] = None,
) -> Tuple[int, int, int, int]:
    x, y, width, height = location
    center_x = x + width // 2
    center_y = y + height // 2
    
    if all_character_bboxes is None:
        all_character_bboxes = []
    if character_bbox:
        all_character_bboxes = [character_bbox] + [cb for cb in all_character_bboxes if cb != character_bbox]
    
    if character_bbox:
        char_left, char_top, char_width, char_height = character_bbox
        character_middle_x = char_left + char_width // 2
        if abs(center_x - character_middle_x) < width // 2 + char_width // 2:
            if center_x < character_middle_x:
                center_x = max(width // 2 + border_padding, char_left - width // 2 - 20)
            else:
                center_x = min(image_width - width // 2 - border_padding, char_left + char_width + width // 2 + 20)
    
    center_x = max(width // 2 + border_padding, min(image_width - width // 2 - border_padding, center_x))
    center_y = max(height // 2 + border_padding, min(image_height - height // 2 - border_padding, center_y))
    
    bubble_rect = (int(center_x - width // 2), int(center_y - height // 2), width, height)
    
    for char_bbox in all_character_bboxes:
        if char_bbox == character_bbox:
            continue
        char_left, char_top, char_width, char_height = char_bbox
        char_rect = (char_left, char_top, char_width, char_height)
        
        if is_rect_overlapping(bubble_rect, char_rect):
            char_center_x = char_left + char_width // 2
            if center_x < char_center_x:
                center_x = max(width // 2 + border_padding, char_left - width // 2 - 20)
            else:
                center_x = min(image_width - width // 2 - border_padding, char_left + char_width + width // 2 + 20)
            bubble_rect = (int(center_x - width // 2), int(center_y - height // 2), width, height)
    
    return bubble_rect


def _draw_bubble_shape(
    draw: ImageDraw.Draw,
    rect: Tuple[int, int, int, int],
    shape: str,
    fill_color: Optional[Tuple[int, int, int]],
    outline_color: Tuple[int, int, int],
    outline_width: int = 3,
):
    x, y, w, h = rect
    bbox = [x, y, x + w, y + h]
    if shape == "rounded":
        radius = max(10, min(w, h) // 5)
        draw.rounded_rectangle(
            bbox,
            radius=radius,
            fill=fill_color if fill_color is not None else None,
            outline=outline_color,
            width=outline_width,
        )
    elif shape == "cloud":
        radius = max(12, min(w, h) // 4)
        draw.rounded_rectangle(bbox, radius=radius, fill=fill_color, outline=outline_color, width=outline_width)
    elif shape == "burst":
        center = (x + w // 2, y + h // 2)
        spikes = 10
        r_outer = min(w, h) // 2
        r_inner = int(r_outer * 0.6)
        points = []
        for i in range(spikes):
            angle = 2 * math.pi * i / spikes
            radius = r_outer if i % 2 == 0 else r_inner
            px = center[0] + int(radius * math.cos(angle))
            py = center[1] + int(radius * math.sin(angle))
            points.append((px, py))
        draw.polygon(points, fill=fill_color if fill_color is not None else None, outline=outline_color)
    else:
        draw.ellipse(
            bbox,
            fill=fill_color if fill_color is not None else None,
            outline=outline_color,
            width=outline_width,
        )


def draw_bubble_tail(
    draw: ImageDraw.Draw,
    rect: Tuple[int, int, int, int],
    target: Optional[Tuple[int, int]],
    outline_color: Tuple[int, int, int],
    shape: str,
):
    if not target:
        return
    x, y, w, h = rect
    tx, ty = target
    cx = x + w / 2
    cy = y + h / 2

    dx = tx - cx
    dy = ty - cy
    if dx == 0 and dy == 0:
        return

    rx = w / 2
    ry = h / 2
    norm = math.hypot(dx / rx, dy / ry)
    if norm == 0:
        norm = 1
    anchor_x = cx + (dx / norm) * rx
    anchor_y = cy + (dy / norm) * ry

    ux = dx
    uy = dy
    length = math.hypot(ux, uy)
    if length == 0:
        length = 1
    ux /= length
    uy /= length

    shrink = 3
    anchor_x -= ux * shrink
    anchor_y -= uy * shrink

    if shape == "thought":
        mid_x = (anchor_x + tx) / 2
        mid_y = (anchor_y + ty) / 2
        draw.ellipse([anchor_x - 6, anchor_y - 6, anchor_x + 6, anchor_y + 6], fill=outline_color)
        draw.ellipse([mid_x - 4, mid_y - 4, mid_x + 4, mid_y + 4], fill=outline_color)
        draw.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill=outline_color)
        return

    base_half = max(8, min(w, h) // 8)
    tail_length = min(80, math.hypot(tx - anchor_x, ty - anchor_y))
    tx = anchor_x + ux * tail_length
    ty = anchor_y + uy * tail_length

    perp_x = -uy
    perp_y = ux
    base1 = (anchor_x + perp_x * base_half, anchor_y + perp_y * base_half)
    base2 = (anchor_x - perp_x * base_half, anchor_y - perp_y * base_half)
    draw.polygon([base1, base2, (tx, ty)], fill=(255, 255, 255), outline=outline_color)


def draw_speech_bubble(
    draw: ImageDraw.Draw,
    bbox: Tuple[int, int, int, int],
    text_lines: List[str],
    font: ImageFont.FreeTypeFont,
    style: Dict,
    character_bbox: Optional[Tuple[int, int, int, int]] = None,
):
    x, y, width, height = bbox
    fill_color = (255, 255, 255)
    outline_color = (20, 20, 20)

    outline_width = 3 if style.get("line") != "handdrawn" else 2
    _draw_bubble_shape(
        draw,
        (x, y, width, height),
        style.get("shape", "oval"),
        fill_color,
        outline_color,
        outline_width=outline_width,
    )

    tail_target = None
    if character_bbox:
        char_left, char_top, char_width, char_height = character_bbox
        tail_target = (
            char_left + char_width // 2,
            char_top + int(char_height * 0.3),
        )

    draw_bubble_tail(
        draw,
        (x, y, width, height),
        tail_target,
        outline_color,
        style.get("shape", "oval"),
    )

    _draw_bubble_shape(
        draw,
        (x, y, width, height),
        style.get("shape", "oval"),
        None,
        outline_color,
        outline_width=outline_width,
    )

    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
    total_text_height = line_height * len(text_lines)
    text_y = y + (height - total_text_height) // 2
    
    # Đảm bảo text không vượt quá bubble width (trừ padding)
    available_text_width = max(40, width - 24)  # Padding 12px mỗi bên, minimum 40px

    for line in text_lines:
        bbox = font.getbbox(line)
        text_width = bbox[2] - bbox[0]
        
        # Nếu text quá dài, cắt ngắn lại
        if text_width > available_text_width:
            # Tìm vị trí cắt gần nhất
            words = line.split()
            truncated_line = ""
            for word in words:
                test_line = truncated_line + (" " if truncated_line else "") + word
                test_bbox = font.getbbox(test_line)
                test_width = test_bbox[2] - test_bbox[0]
                if test_width <= available_text_width:
                    truncated_line = test_line
                else:
                    break
            if not truncated_line:
                # Nếu không thể wrap, cắt ký tự
                truncated_line = line[:max(1, len(line) * available_text_width // text_width)]
            line = truncated_line
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]
        
        # Đảm bảo text không vượt quá bubble bounds
        text_x = max(x + 12, min(x + (width - text_width) // 2, x + width - text_width - 12))
        draw.text((text_x, text_y), line, fill=(10, 10, 10), font=font)
        text_y += line_height

def inject_bubbles_to_panel(
    panel_image: Image.Image,
    dialogues: List[dict],
) -> Image.Image:
    result = panel_image.copy()
    draw = ImageDraw.Draw(result)
    
    if not dialogues:
        return result
    
    character_bbox = find_character_bounding_box(panel_image)

    bubble_entries: List[Dict] = []
    for dialogue in dialogues:
        text = dialogue.get("text", "")
        if not text:
            continue
        for sentence in split_text_into_bubbles(text):
            bubble_entries.append(
                {"text": sentence, "emotion": dialogue.get("emotion")}
            )

    if not bubble_entries:
        return result

    image_width, image_height = result.size
    existing_bubbles: List[Tuple[int, int, int, int]] = []

    for entry in bubble_entries:
        text = entry["text"]
        emotion = entry.get("emotion")
        font_size = max(20, min(image_width, image_height) // 32)
        font_name = get_font_name_for_emotion(emotion)
        font = load_font(font_name, font_size)
        max_text_width = max(100, int(image_width * 0.6))
        text_lines = wrap_text_to_lines(text, font, max_text_width)
        line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
        text_height = line_height * len(text_lines)
        text_width = max(font.getbbox(line)[2] - font.getbbox(line)[0] for line in text_lines)

        bubble_padding = 70
        min_bubble_width = 160
        min_bubble_height = 90
        bubble_width = int(text_width + bubble_padding * 2)
        bubble_width = min(bubble_width, int(image_width * 0.85))
        bubble_width = max(bubble_width, min_bubble_width)

        effective_text_width = max(60, bubble_width - bubble_padding * 2)
        if effective_text_width < max_text_width:
            text_lines = wrap_text_to_lines(text, font, effective_text_width)
            text_height = line_height * len(text_lines)

        bubble_height = int(text_height + bubble_padding * 2)
        bubble_height = min(bubble_height, int(image_height * 0.65))
        bubble_height = max(bubble_height, min_bubble_height)

        loc = sample_bubble_position(
            panel_bounds=(0, 0, image_width, image_height),
            bubble_width=bubble_width,
            bubble_height=bubble_height,
            character_bbox=character_bbox,
            border_padding=20,
            all_character_bboxes=[character_bbox] if character_bbox else [],
            existing_bubbles=existing_bubbles,
            page_width=image_width,
            page_height=image_height,
        )
        x, y, _, _ = loc
        bubble_location = (x, y, bubble_width, bubble_height)
        existing_bubbles.append(bubble_location)

        style = choose_bubble_style(emotion)
        draw_speech_bubble(
            draw=draw,
            bbox=bubble_location,
            text_lines=text_lines,
            font=font,
            style=style,
            character_bbox=character_bbox,
        )

    return result

def get_all_character_bboxes_on_page(
    page: Image.Image,
    schema_path: str,
    panels_dir: str,
    panel_positions: List[Tuple[int, int, int, int]],
) -> List[Tuple[int, int, int, int]]:
    all_character_bboxes = []
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return all_character_bboxes
    
    panel_path = Path(panels_dir)
    panel_files = sorted(panel_path.glob("*.png"))
    panels_data = data.get("panels", [])
    
    for i, panel_data in enumerate(panels_data[:len(panel_files)]):
        if i >= len(panel_files) or i >= len(panel_positions):
            continue
        
        try:
            panel_image = Image.open(panel_files[i]).convert("RGB")
            panel_x, panel_y, panel_w, panel_h = panel_positions[i]
            
            scale_x = panel_w / panel_image.width
            scale_y = panel_h / panel_image.height
            
            character_bbox = find_character_bounding_box(panel_image)
            if character_bbox:  # type: ignore
                char_left, char_top, char_width, char_height = character_bbox
                scaled_char_bbox = (
                    int(panel_x + char_left * scale_x),
                    int(panel_y + char_top * scale_y),
                    int(char_width * scale_x),
                    int(char_height * scale_y),
                )
                all_character_bboxes.append(scaled_char_bbox)
        except Exception:
            continue
    
    return all_character_bboxes

def inject_bubbles_to_page(
    page: Image.Image,
    schema_path: str,
    panels_dir: str,
    panel_positions: List[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[WARN] Cannot load schema: {e}")
        return page
    
    panels_data = data.get("panels", [])
    if not panels_data:
        return page
    
    result = page.copy()
    draw = ImageDraw.Draw(result)
    
    panel_path = Path(panels_dir)
    panel_files = sorted(panel_path.glob("*.png"))
    
    page_width, page_height = result.size
    
    all_character_bboxes = []
    if panel_positions:
        all_character_bboxes = get_all_character_bboxes_on_page(
            result, schema_path, panels_dir, panel_positions
        )
        print(f"[BUBBLE] Found {len(all_character_bboxes)} character bboxes on page")
    
    bubble_entries: List[Dict] = []
    bubble_panels: List[Dict] = []
    
    for i, panel_data in enumerate(panels_data[:len(panel_files)]):
        dialogues = panel_data.get("dialogues", [])
        if not dialogues:
            continue
        
        if i >= len(panel_files):
            continue

        panel_image = Image.open(panel_files[i]).convert("RGB")

        if panel_positions and i < len(panel_positions):
            panel_x, panel_y, panel_w, panel_h = panel_positions[i]
            scale_x = panel_w / panel_image.width
            scale_y = panel_h / panel_image.height
        else:
            num_panels = len(panel_files)
            panel_height = page_height // num_panels if num_panels > 0 else page_height
            panel_width = page_width
            panel_x, panel_y = 0, i * panel_height
            scale_x = panel_width / panel_image.width
            scale_y = panel_height / panel_image.height
            panel_w = panel_width
            panel_h = panel_height

        character_bbox = find_character_bounding_box(panel_image)
        
        character_positions = panel_data.get("character_positions", {})
        
        char_bbox_map = {}
        if character_bbox:
            char_left, char_top, char_width, char_height = character_bbox
            for char_id, pos in character_positions.items():
                x_pos = pos.get("x", "center")
                if x_pos == "left":
                    char_bbox_map[char_id] = (
                        int(panel_x + char_left * scale_x),
                        int(panel_y + char_top * scale_y),
                        int(char_width * scale_x),
                        int(char_height * scale_y),
                    )
                elif x_pos == "right":
                    char_bbox_map[char_id] = (
                        int(panel_x + (char_left + char_width) * scale_x - char_width * scale_x * 0.5),
                        int(panel_y + char_top * scale_y),
                        int(char_width * scale_x),
                        int(char_height * scale_y),
                    )
                else:
                    char_bbox_map[char_id] = (
                        int(panel_x + char_left * scale_x),
                        int(panel_y + char_top * scale_y),
                        int(char_width * scale_x),
                        int(char_height * scale_y),
                    )
        
        default_char_bbox = None
        if character_bbox:
            char_left, char_top, char_width, char_height = character_bbox
            default_char_bbox = (
                int(panel_x + char_left * scale_x),
                int(panel_y + char_top * scale_y),
                int(char_width * scale_x),
                int(char_height * scale_y),
            )
        
        for dialogue in dialogues:
            text = dialogue.get("text", "")
            character_id = dialogue.get("character_id", "")
            if not text:
                continue
            
            char_bbox = char_bbox_map.get(character_id, default_char_bbox)
            
            active_char_ids = panel_data.get("active_char_ids", [])
            if character_id not in active_char_ids:
                print(f"[WARN] Dialogue character_id '{character_id}' not in active_char_ids {active_char_ids} for panel {i}")
            
            for sentence in split_text_into_bubbles(text):
                bubble_entries.append(
                    {
                        "text": sentence,
                        "emotion": dialogue.get("emotion"),
                        "character_id": character_id,
                    }
                )
                bubble_panels.append(
                    {
                        "panel_idx": i,
                        "char_bbox": char_bbox,
                        "character_id": character_id,
                        "panel_x": panel_x,
                        "panel_y": panel_y,
                        "panel_w": panel_w if panel_positions else page_width,
                        "panel_h": panel_h
                        if panel_positions
                        else (page_height // len(panel_files) if panel_files else page_height),
                    }
                )

    if not bubble_entries:
        return result

    # QUAN TRỌNG: existing_bubbles được share cho TẤT CẢ panels
    existing_bubbles: List[Tuple[int, int, int, int]] = []

    for entry, bubble_panel in zip(bubble_entries, bubble_panels):
        text = entry["text"]
        emotion = entry.get("emotion")
        char_bbox = bubble_panel["char_bbox"]
        panel_x = bubble_panel["panel_x"]
        panel_y = bubble_panel["panel_y"]
        panel_w = bubble_panel["panel_w"]
        panel_h = bubble_panel["panel_h"]

        font_size = max(22, min(page_width, page_height) // 36)
        font_name = get_font_name_for_emotion(emotion)
        font = load_font(font_name, font_size)

        bubble_padding = 45
        max_bubble_width = min(panel_w * 0.75, 400)
        min_bubble_width = 120
        min_bubble_height = 70
        
        max_text_width_initial = max(100, int(panel_w * 0.50))
        text_lines = wrap_text_to_lines(text, font, max_text_width_initial)
        line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1]
        
        text_width = 0
        for line in text_lines:
            bbox = font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            text_width = max(text_width, line_width)
        
        text_width = int(text_width * 1.1)
        
        bubble_width = max(int(text_width + bubble_padding * 2), min_bubble_width)
        bubble_width = min(bubble_width, int(max_bubble_width))
        
        effective_text_width = max(60, bubble_width - bubble_padding * 2 - 10)
        text_lines = wrap_text_to_lines(text, font, effective_text_width)
        
        text_height = line_height * len(text_lines)
        text_width_final = 0
        for line in text_lines:
            bbox = font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            text_width_final = max(text_width_final, line_width)
        
        if text_width_final + bubble_padding * 2 > bubble_width:
            bubble_width = min(int(text_width_final + bubble_padding * 2 + 10), int(max_bubble_width))

        bubble_height = max(int(text_height + bubble_padding * 2), min_bubble_height)
        bubble_height = min(bubble_height, int(panel_h * 0.60))

        # Gọi find_bubble_position với existing_bubbles GLOBAL (chứa bubbles từ tất cả panels)
        x, y = find_bubble_position(
            bubble_width,
            bubble_height,
            (panel_x, panel_y, panel_w, panel_h),
            char_bbox,
            existing_bubbles,  # QUAN TRỌNG: pass existing_bubbles global
            page_width,
            page_height,
            attempts=200,  # Tăng số attempts lên 200
        )
        bubble_location = (int(x), int(y), bubble_width, bubble_height)
        
        # QUAN TRỌNG: Add vào existing_bubbles NGAY sau khi tìm được vị trí
        existing_bubbles.append(bubble_location)
        
        print(f"[BUBBLE] Panel {bubble_panel['panel_idx']}: placed at ({x}, {y}, {bubble_width}, {bubble_height})")

        style = choose_bubble_style(emotion)
        draw_speech_bubble(
            draw=draw,
            bbox=bubble_location,
            text_lines=text_lines,
            font=font,
            style=style,
            character_bbox=char_bbox,
        )
    
    return result