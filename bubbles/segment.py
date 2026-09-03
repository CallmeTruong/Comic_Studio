from __future__ import annotations

import numpy as np
from PIL import Image

try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except Exception:
    _MP_AVAILABLE = False


def detect_character_bbox_mediapipe(image: Image.Image) -> tuple[int, int, int, int] | None:
    if not _MP_AVAILABLE:
        return None

    try:
        mp_selfie = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)
        img_np = np.array(image.convert("RGB"))
        results = mp_selfie.process(img_np)
        mp_selfie.close()
        mask = results.segmentation_mask
        if mask is None:
            return None
        mask_binary = (mask > 0.2).astype(np.uint8)
        
        # Tìm tất cả shapes (giống ai-comic-factory)
        shapes = []
        visited = np.zeros_like(mask_binary)
        height, width = mask_binary.shape
        
        for y in range(height):
            for x in range(width):
                if mask_binary[y, x] > 0 and visited[y, x] == 0:
                    # Flood fill để tìm shape
                    shape_bbox = _flood_fill_bbox(mask_binary, visited, x, y, width, height)
                    if shape_bbox:
                        shapes.append(shape_bbox)
        
        if not shapes:
            return None
        
        # Lọc shapes nhỏ (< 1% diện tích) và sắp xếp theo diện tích
        min_area = width * height * 0.01
        shapes = [s for s in shapes if s[2] * s[3] > min_area]
        if not shapes:
            return None
        
        # Sắp xếp theo diện tích (descending)
        shapes.sort(key=lambda s: s[2] * s[3], reverse=True)
        
        # Tìm shape có tỷ lệ vertical cao nhất (giống ai-comic-factory)
        most_vertical = max(shapes, key=lambda s: s[3] / max(s[2], 1))
        
        return most_vertical
    except Exception:
        return None

def _flood_fill_bbox(mask: np.ndarray, visited: np.ndarray, start_x: int, start_y: int, width: int, height: int) -> tuple[int, int, int, int] | None:
    """Flood fill để tìm bounding box của một shape"""
    queue = [(start_x, start_y)]
    min_x, max_x = start_x, start_x
    min_y, max_y = start_y, start_y
    
    while queue:
        x, y = queue.pop(0)
        if x < 0 or x >= width or y < 0 or y >= height:
            continue
        if visited[y, x] > 0 or mask[y, x] == 0:
            continue
        
        visited[y, x] = 1
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        
        queue.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
    
    if min_x >= max_x or min_y >= max_y:
        return None
    
    return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

