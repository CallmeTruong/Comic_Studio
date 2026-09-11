from __future__ import annotations

import os
from pathlib import Path
from typing import Dict
from functools import lru_cache

import numpy as np
from PIL import ImageFont
from sentence_transformers import SentenceTransformer

FONT_ROOT = Path("assets/fonts")

FONT_REGISTRY: Dict[str, Path] = {
    "actionman": FONT_ROOT / "DigitalStripBB" / "PatrickHand-Regular.woff2",
    "digitalstrip": FONT_ROOT / "DigitalStripBB" / "PatrickHand-Regular.woff2",
    "komika": FONT_ROOT / "Komika-Hand" / "PatrickHandSC-Regular.woff2",
    "karantula": FONT_ROOT / "DigitalStripBB" / "PatrickHand-Regular.woff2",
    "manoskope": FONT_ROOT / "DigitalStripBB" / "PatrickHand-Regular.woff2",
}

# Semantic description for each font
FONT_DESCRIPTIONS: Dict[str, str] = {
    "actionman": "neutral calm normal default casual friendly conversation",
    "digitalstrip": "surprised shocked amazed astonished wow unexpected stunning",
    "komika": "angry furious shouting rage mad frustrated yelling intense",
    "karantula": "scary horror creepy spooky frightening terrifying dark evil",
    "manoskope": "sad melancholy sorry apologetic depressed gloomy regretful",
}


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _get_font_embeddings() -> tuple[list[str], np.ndarray]:
    model = _get_model()
    fonts = list(FONT_DESCRIPTIONS.keys())
    embeddings = model.encode(list(FONT_DESCRIPTIONS.values()))
    return fonts, embeddings


def get_font_name_for_emotion(emotion: str | None) -> str:
    if not emotion:
        return "actionman"

    # Font choice must be deterministic and lightweight. Loading a sentence
    # transformer for every page made bubble rendering slow and could exhaust
    # the temporary disk while converting WOFF2 files.
    emotion_lower = emotion.lower()
    if any(word in emotion_lower for word in ("shout", "scream", "yell")):
        return "komika"
    if any(word in emotion_lower for word in ("surpris", "shock", "panic")):
        return "digitalstrip"
    if any(word in emotion_lower for word in ("sad", "sorry", "apolog")):
        return "manoskope"
    return "actionman"


def _load_woff2(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        from fontTools.ttLib.woff2 import decompress
    except Exception as exc:
        raise RuntimeError(f"fontTools missing for {path}: {exc}") from exc

    # Keep transient font files beside the project so a full system temp
    # drive cannot break comic rendering.
    cache_dir = FONT_ROOT / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{path.stem}_{size}"
    in_path = str(cache_dir / f"{stem}.woff2")
    out_path = str(cache_dir / f"{stem}.ttf")
    Path(in_path).write_bytes(path.read_bytes())

    try:
        decompress(in_path, out_path)
        font = ImageFont.truetype(out_path, size=size)
    finally:
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except OSError:
                pass
    return font


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_REGISTRY.get(name)
    if not path or not path.exists():
        return ImageFont.truetype("arial.ttf", size=size)
    try:
        if path.suffix.lower() in (".ttf", ".otf"):
            return ImageFont.truetype(str(path), size=size)
        if path.suffix.lower() == ".woff2":
            return _load_woff2(path, size)
        return ImageFont.truetype(str(path), size=size)
    except Exception as exc:
        print(f"[WARN] Cannot load font {name} from {path}: {exc}")
        return ImageFont.truetype("arial.ttf", size=size)


__all__ = ["load_font", "get_font_name_for_emotion"]
