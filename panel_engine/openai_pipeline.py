"""OpenAI image provider for comic panels.

The API key is read only on the server.  This module intentionally returns
ordinary local PNG files so the existing page/layout and speech-bubble stages
remain unchanged.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from PIL import Image

from page.builder import preserve_aspect_resize
from panel_engine.prompts import compose_unified_panel_prompt
from utils.parser import load_comic_from_json


def _image_size(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    if ratio > 1.25:
        return "1536x1024"
    if ratio < 0.8:
        return "1024x1536"
    return "1024x1024"


def generate_panels_openai(
    schema_path: str,
    output_panel_dir: str,
    model: str = "gpt-image-1",
    max_render_width: int = 1536,
    max_render_height: int = 1536,
    negative_prompt_extra: str | None = None,
) -> Dict[str, Dict[str, int]]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY chưa được cấu hình ở backend.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Thiếu package openai. Cài bằng: pip install openai") from exc

    with open(schema_path, "r", encoding="utf-8") as handle:
        comic = load_comic_from_json(json.load(handle))

    client = OpenAI(api_key=api_key)
    output_dir = Path(output_panel_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    panel_sizes: Dict[str, Dict[str, int]] = {}
    panel_sizes_path = Path(schema_path).parent / "panel_sizes.json"
    metadata = {}
    if panel_sizes_path.exists():
        with panel_sizes_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)

    for panel in comic.panels:
        target_width = int(metadata.get(panel.id, {}).get("width", 768))
        target_height = int(metadata.get(panel.id, {}).get("height", 1024))
        render_width = min(target_width, max_render_width)
        render_height = min(target_height, max_render_height)

        characters = []
        for char_id in panel.active_char_ids:
            char = comic.characters.get(char_id)
            if char:
                characters.append((char, char_id))

        prompt, negative = compose_unified_panel_prompt(
            panel_prompt=panel.panel_prompt_en,
            panel_negative=panel.panel_negative_en,
            characters_meta=characters,
            character_actions={
                cid: {
                    "action_en": panel.character_actions[cid].action_en,
                    "pose_en": panel.character_actions[cid].pose_en,
                    "objects": panel.character_actions[cid].objects,
                    "interaction": panel.character_actions[cid].interaction,
                }
                for cid in panel.character_actions
            },
            background_prompt=panel.background_prompt_en,
            dialogues=panel.dialogues,
            max_tokens=None,
        )
        if negative_prompt_extra:
            negative = f"{negative}, {negative_prompt_extra}"
        full_prompt = (
            "Create one clean 2D comic panel illustration. No text, lettering, captions, "
            "or speech bubbles; those are added later. Preserve exactly the described "
            f"characters and action. {prompt}. Avoid: {negative}"
        )

        try:
            response = client.images.generate(
                model=model,
                prompt=full_prompt,
                size=_image_size(render_width, render_height),
                quality="medium",
                n=1,
            )
        except Exception as exc:
            message = str(exc)
            if "404" in message or "Not found" in message:
                raise RuntimeError(
                    "Image API không khả dụng tại OPENAI_BASE_URL hiện tại. "
                    "Proxy này có thể chỉ hỗ trợ model chat; hãy dùng OpenAI "
                    "Platform base URL hoặc tiếp tục dùng SD 1.5."
                ) from exc
            raise RuntimeError(f"OpenAI Image API lỗi ở panel {panel.id}: {message}") from exc
        encoded = response.data[0].b64_json
        if not encoded:
            raise RuntimeError(f"OpenAI không trả về ảnh cho panel {panel.id}.")
        image_path = output_dir / f"{panel.id}.png"
        image_path.write_bytes(base64.b64decode(encoded))

        if render_width != target_width or render_height != target_height:
            image = Image.open(image_path).convert("RGB")
            image = preserve_aspect_resize(image, target_width, target_height, fill_mode="crop")
            image.save(image_path, format="PNG")
        panel_sizes[panel.id] = {"width": target_width, "height": target_height}

    return panel_sizes
