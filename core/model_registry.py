"""Lazy local model registry used by the API and the rendering graph.

Model files are intentionally not downloaded while the application starts or
while the capabilities endpoint is queried.  A selected model is materialized
only when a render is actually requested.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "sd15": {
        "id": "sd15",
        "label": "ComicBabes v2 (SD 1.5)",
        "family": "SDv1.5",
        "path": "models/base/comicBabes_v2.safetensors",
        "repo_id": None,
        "download": "Place comicBabes_v2.safetensors in models/base.",
    },
    # DreamShaper XL is a widely used illustration checkpoint on HF and is a
    # safer general-purpose comic/illustration default than a random custom
    # checkpoint. It is opt-in and downloaded only when selected for rendering.
    "sdxl_dreamshaper": {
        "id": "sdxl_dreamshaper",
        "label": "DreamShaper XL 1.0 (SDXL)",
        "family": "SDXL",
        "path": "models/base/sdxl/dreamshaper-xl-1-0",
        "repo_id": "Lykon/dreamshaper-xl-1-0",
        "download": "Downloaded lazily from Hugging Face on first SDXL render.",
    },
}


def get_model_profile(model_id: str | None) -> dict[str, Any]:
    return MODEL_PROFILES.get(model_id or "sd15", MODEL_PROFILES["sd15"])


def model_catalog() -> list[dict[str, Any]]:
    """Return UI-safe metadata without touching Hugging Face or downloading."""
    result = []
    for profile in MODEL_PROFILES.values():
        path = Path(profile["path"])
        result.append({
            "id": profile["id"],
            "label": profile["label"],
            "family": profile["family"],
            "installed": path.exists(),
            "repo_id": profile["repo_id"],
        })
    return result


def ensure_model(model_id: str | None, override_path: str | None = None) -> tuple[dict[str, Any], str]:
    """Resolve a selected model, downloading only for an actual render."""
    profile = get_model_profile(model_id)
    # Keep the configured SD 1.5 checkpoint path authoritative. The registry
    # only supplies the default path and lazy-download behavior for optional
    # profiles; it must not break user-configured local checkpoints.
    path = Path(override_path) if profile["id"] == "sd15" and override_path else Path(profile["path"])
    if profile["repo_id"] is None:
        if not path.exists():
            raise FileNotFoundError(f"Missing base model: {path}. {profile['download']}")
        return profile, str(path)
    if not path.exists() or not any(path.iterdir()):
        from huggingface_hub import snapshot_download

        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[MODEL] Downloading {profile['repo_id']} to {path} (first use only)...")
        snapshot_download(repo_id=profile["repo_id"], local_dir=str(path))
    return profile, str(path)


def validate_model_id(model_id: str | None) -> str:
    """Return a known model id, falling back safely for older callers."""
    return model_id if model_id in MODEL_PROFILES else "sd15"
