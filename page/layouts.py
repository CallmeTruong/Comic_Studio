from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Sequence


LAYOUT_SETTINGS: Dict[str, List[Dict]] = {
    # Layouts cho 2 panels
    "Layout2Panels": [
        {"width": 1024, "height": 768, "col_span": 1, "row_span": 1},
        {"width": 1024, "height": 768, "col_span": 1, "row_span": 1},
    ],
    "Layout2PanelsWide": [
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
    ],
    # Layouts cho 3 panels
    "Layout3Panels": [
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
    ],
    "Layout3PanelsMixed": [
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
    ],
    # Layouts cho 4 panels
    "Layout1": [
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 2},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 2},
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
    ],
    "Layout2": [
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 2},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 2},
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
    ],
    "Layout3": [
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},  # top
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},   # middle left
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},   # middle right
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},   # bottom
    ],
    # Layouts cho 5 panels
    "Layout5Panels": [
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},
    ],
    # Layouts cho 6 panels
    "Layout6Panels": [
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},
    ],
    "Layout6Panels_1": [
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},   # top left
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},   # top right
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 2},   # middle left
        {"width": 1024, "height": 1024, "col_span": 2, "row_span": 2},  # middle right large
        {"width": 768, "height": 1024, "col_span": 1, "row_span": 1},   # bottom left
        {"width": 1024, "height": 768, "col_span": 2, "row_span": 1},   # bottom right
    ],
}

GRID_CONFIGS: Dict[str, Dict] = {
    "Layout2Panels": {"cols": 2, "rows": 1},
    "Layout2PanelsWide": {"cols": 2, "rows": 2},
    "Layout3Panels": {"cols": 1, "rows": 3},
    "Layout3PanelsMixed": {"cols": 2, "rows": 2},
    "Layout0": {"cols": 2, "rows": 2},
    "Layout1": {"cols": 2, "rows": 4},
    "Layout2": {"cols": 3, "rows": 4},
    "Layout3": {"cols": 2, "rows": 3},
    "Layout4": {"cols": 3, "rows": 3},
    "Layout5Panels": {"cols": 3, "rows": 2},
    "Layout5Panels_1": {"cols": 3, "rows": 3},
    "Layout6Panels": {"cols": 3, "rows": 2},
    "Layout6Panels_1": {"cols": 3, "rows": 4},
}


def _list_candidates(num_panels: int) -> List[str]:
    candidates = [name for name, panels in LAYOUT_SETTINGS.items() if len(panels) >= num_panels]
    if not candidates:
        candidates = list(LAYOUT_SETTINGS.keys())
    return candidates


def _layout_orientation_score(layout_entries: Sequence[Dict]) -> int:
    score = 0
    for entry in layout_entries:
        width = entry.get("width", 1)
        height = entry.get("height", 1)
        score += 1 if width >= height else -1
    return score


def select_layout_name(
    num_panels: int,
    preferred: Optional[str] = None,
    seed_text: str = "",
) -> str:
    # Nếu có preferred layout và phù hợp, dùng nó
    if preferred and preferred in LAYOUT_SETTINGS and len(LAYOUT_SETTINGS[preferred]) >= num_panels:
        return preferred

    # Tìm các layout phù hợp với số lượng panel
    candidates = _list_candidates(num_panels)
    
    # Ưu tiên layout có số panel gần nhất với num_panels
    candidates.sort(key=lambda name: abs(len(LAYOUT_SETTINGS[name]) - num_panels))
    
    # Lọc các layout có số panel chính xác hoặc gần nhất
    exact_match = [c for c in candidates if len(LAYOUT_SETTINGS[c]) == num_panels]
    if exact_match:
        candidates = exact_match

    if len(candidates) == 1:
        return candidates[0]

    # Sử dụng seed để chọn layout ngẫu nhiên nhưng nhất quán
    digest = hashlib.md5(seed_text.encode("utf-8")).hexdigest() if seed_text else None
    if digest:
        bias = 1 if int(digest[-1], 16) % 2 == 0 else -1
        candidates.sort(
            key=lambda name: (
                abs(_layout_orientation_score(LAYOUT_SETTINGS[name]) - bias),
                name,
            )
        )
        idx = int(digest[:8], 16) % len(candidates)
        return candidates[idx]

    return candidates[0]


def compute_layout_placements(
    layout_name: str,
    panels_count: int,
    page_width: int = 2480,
    page_height: int = 3508,
    margin: int = 60,
    gutter: int = 20,
) -> List[Dict]:
    if layout_name not in LAYOUT_SETTINGS:
        layout_name = "Layout1"

    layout_settings = LAYOUT_SETTINGS[layout_name]
    grid_config = GRID_CONFIGS.get(layout_name, GRID_CONFIGS["Layout1"])

    num_cols = grid_config["cols"]
    num_rows = grid_config["rows"]

    content_width = page_width - margin * 2
    content_height = page_height - margin * 2

    total_gutter_width = gutter * (num_cols - 1)
    total_gutter_height = gutter * (num_rows - 1)

    cell_width = int((content_width - total_gutter_width) / num_cols)
    cell_height = int((content_height - total_gutter_height) / num_rows)

    actual_content_width = cell_width * num_cols + total_gutter_width
    actual_content_height = cell_height * num_rows + total_gutter_height

    width_adjustment = (content_width - actual_content_width) // 2
    height_adjustment = (content_height - actual_content_height) // 2

    placements: List[Dict] = []
    grid_occupied = [[False for _ in range(num_cols)] for _ in range(num_rows)]

    # Chỉ sử dụng số panel thực tế, không tạo panel trống
    max_panels = min(panels_count, len(layout_settings))

    for idx in range(max_panels):
        entry = layout_settings[idx]
        col_span = entry.get("col_span", 1)
        row_span = entry.get("row_span", 1)

        row = 0
        col = 0
        found = False

        for r in range(num_rows):
            for c in range(num_cols):
                can_place = True
                for dr in range(row_span):
                    for dc in range(col_span):
                        if r + dr >= num_rows or c + dc >= num_cols:
                            can_place = False
                            break
                        if grid_occupied[r + dr][c + dc]:
                            can_place = False
                            break
                    if not can_place:
                        break
                if can_place:
                    row, col = r, c
                    found = True
                    break
            if found:
                break

        if not found:
            col = idx % num_cols
            row = idx // num_cols

        for dr in range(row_span):
            for dc in range(col_span):
                if row + dr < num_rows and col + dc < num_cols:
                    grid_occupied[row + dr][col + dc] = True

        panel_width = int(cell_width * col_span + gutter * (col_span - 1))
        panel_height = int(cell_height * row_span + gutter * (row_span - 1))

        x = int(margin + width_adjustment + col * (cell_width + gutter))
        y = int(margin + height_adjustment + row * (cell_height + gutter))

        placements.append(
            {
                "idx": idx,
                "width": panel_width,
                "height": panel_height,
                "col": col,
                "row": row,
                "col_span": col_span,
                "row_span": row_span,
                "x": x,
                "y": y,
            }
        )

    return placements


__all__ = [
    "LAYOUT_SETTINGS",
    "GRID_CONFIGS",
    "select_layout_name",
    "compute_layout_placements",
]

