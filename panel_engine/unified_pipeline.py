from __future__ import annotations
import json
import hashlib
import torch
from pathlib import Path
from typing import Dict, List, Tuple
from core.stable_diffusion import SD
from utils.parser import load_comic_from_json
from .prompts import compose_unified_panel_prompt
from .prompt_cleaner import clean_instruction_text
from page.layouts import LAYOUT_SETTINGS, compute_layout_placements
from page.builder import preserve_aspect_resize
from PIL import Image, ImageDraw
from style.presets import get_style_preset
from config import CONFIG
from core.model_registry import ensure_model, validate_model_id


def _position_ratio(value: str | None, fallback: float) -> float:
    mapping = {
        "left": 0.2,
        "center": 0.5,
        "right": 0.8,
    }
    return mapping.get((value or "").lower(), fallback)


def _vertical_anchor(value: str | None) -> float:
    mapping = {
        "top": 0.3,
        "middle": 0.5,
        "bottom": 0.7,
    }
    return mapping.get((value or "").lower(), 0.5)


def build_control_guides(
    width: int,
    height: int,
    characters_meta: List[Tuple],
    character_positions: Dict[str, dict],
    requested_modes: List[str],
) -> Dict[str, Image.Image]:
    if width <= 0 or height <= 0:
        width, height = CONFIG.panel.fallback_width, CONFIG.panel.fallback_height
    canny = Image.new("L", (width, height), color=0)
    pose = Image.new("RGB", (width, height), color="black")
    depth = Image.new("L", (width, height), color=80)
    canny_draw = ImageDraw.Draw(canny)
    pose_draw = ImageDraw.Draw(pose)
    depth_draw = ImageDraw.Draw(depth)

    num_chars = max(1, len(characters_meta))
    default_slots = [(i + 1) / (num_chars + 1) for i in range(num_chars)]

    for idx, (char_meta, char_id) in enumerate(characters_meta or [("", "anon")]):
        ratio = _position_ratio(character_positions.get(char_id, {}).get("x"), default_slots[min(idx, len(default_slots) - 1)])
        anchor_y = _vertical_anchor(character_positions.get(char_id, {}).get("y"))
        body_width = width * 0.18
        body_height = height * 0.55
        cx = int(ratio * width)
        top = int(max(height * 0.05, anchor_y * height - body_height / 2))
        bottom = int(min(height * 0.95, top + body_height))
        left = int(max(0, cx - body_width / 2))
        right = int(min(width, cx + body_width / 2))

        canny_draw.rectangle([left, top, right, bottom], outline=255, width=3)
        depth_draw.rectangle([left, top, right, bottom], fill=200)

        head_radius = int(body_width * 0.25)
        head_center = (cx, top - head_radius)
        pose_draw.ellipse(
            [
                head_center[0] - head_radius,
                head_center[1] - head_radius,
                head_center[0] + head_radius,
                head_center[1] + head_radius,
            ],
            outline=(0, 255, 255),
            width=4,
        )
        torso_bottom = (cx, bottom - int(body_height * 0.25))
        pose_draw.line([head_center, torso_bottom], fill=(0, 255, 0), width=6)
        arm_span = body_width * 0.6
        pose_draw.line(
            [
                (cx - arm_span, head_center[1] + head_radius),
                (cx + arm_span, head_center[1] + head_radius),
            ],
            fill=(255, 200, 0),
            width=5,
        )
        pose_draw.line(
            [
                torso_bottom,
                (cx - arm_span / 2, bottom),
            ],
            fill=(255, 0, 0),
            width=5,
        )
        pose_draw.line(
            [
                torso_bottom,
                (cx + arm_span / 2, bottom),
            ],
            fill=(255, 0, 0),
            width=5,
        )

    guides: Dict[str, Image.Image] = {}
    if "canny" in requested_modes:
        guides["canny"] = canny.convert("RGB")
    if "openpose" in requested_modes:
        guides["openpose"] = pose
    if "depth" in requested_modes:
        guides["depth"] = depth.convert("RGB")
    return guides


def _split_extra_tags(text: str | None) -> List[str]:
    if not text:
        return []
    normalized = text.replace("\n", ",")
    return [frag.strip() for frag in normalized.split(",") if frag.strip()]


def _extract_structured_fields(panel) -> dict[str, str]:
    """Return structured storyboard constraints without parsing panel prose."""
    fields: dict[str, str] = {}
    for name in ("primary_subject", "secondary_subject", "visual_hierarchy", "required_action"):
        value = str(getattr(panel, name, "") or "").strip()
        if value:
            fields[name] = value
    subjects = list(getattr(panel, "required_subjects", None) or [])
    if subjects:
        fields["required_subjects"] = ", ".join(str(value).strip() for value in subjects if str(value).strip())
    return fields


def _compute_render_size(
    target_width: int,
    target_height: int,
    max_render_width: int,
    max_render_height: int,
) -> Tuple[int, int]:
    if target_width <= 0 or target_height <= 0:
        return CONFIG.panel.fallback_width, CONFIG.panel.fallback_height

    if max_render_width <= 0 or max_render_height <= 0:
        return target_width, target_height

    scale = min(1.0, max_render_width / target_width, max_render_height / target_height)
    render_width = int(max(64, round(target_width * scale / 8) * 8))
    render_height = int(max(64, round(target_height * scale / 8) * 8))
    return render_width, render_height

def generate_panels_unified(
    schema_path: str,
    output_panel_dir: str,
    base_model_path: str,
    device: str = "cuda",
    base: str = "SDv1.5",
    lora_path: str | None = None,
    lora_scale: float = 0.85,
    panel_steps: int = 30,
    guidance_scale: float = 9.0,
    layout_name: str | None = None,
    negative_embedding_path: str | None = None,
    max_render_width: int = 1024,
    max_render_height: int = 1024,
    controlnet_config: dict | None = None,
    style_name: str | None = None,
    negative_prompt_extra: str | None = None,
    target_panel_ids: List[str] | None = None,
    series_id: str = "default",
    seed: int | None = None,
    model_id: str = "sd15",
) -> Dict[str, Dict[str, int]]:
    # A CPU fallback is useful for schema/pipeline smoke tests, but rendering
    # four large SD 1.5 panels concurrently with the normal GPU dimensions can
    # exhaust system memory and terminate the API process. Keep this fallback
    # bounded; CUDA runs retain the requested quality dimensions unchanged.
    if device == "cuda" and not torch.cuda.is_available():
        max_render_width = min(max_render_width, 512)
        max_render_height = min(max_render_height, 512)
        print(
            "[UNIFIED] CUDA unavailable; using bounded CPU fallback "
            f"({max_render_width}x{max_render_height})."
        )
    output_panel_path = Path(output_panel_dir)
    output_panel_path.mkdir(parents=True, exist_ok=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    comic = load_comic_from_json(raw_data)

    panel_layout_info = {}
    placement_targets: Dict[int, Tuple[int, int]] = {}
    if layout_name and layout_name in LAYOUT_SETTINGS:
        placement_list = compute_layout_placements(layout_name, len(comic.panels))
        placement_targets = {placement["idx"]: (placement["width"], placement["height"]) for placement in placement_list}
    else:
        layout_name = None
    panel_sizes_path = Path(schema_path).parent / "panel_sizes.json"
    panel_sizes_metadata: Dict[str, Dict[str, int]] = {}
    if panel_sizes_path.exists():
        with panel_sizes_path.open("r", encoding="utf-8") as f:
            panel_sizes_metadata = json.load(f)

    for idx, panel in enumerate(comic.panels):
        width, height = CONFIG.panel.width, CONFIG.panel.height
        if idx in placement_targets:
            width, height = placement_targets[idx]
        elif panel.id in panel_sizes_metadata:
            width = panel_sizes_metadata[panel.id].get("width", width)
            height = panel_sizes_metadata[panel.id].get("height", height)
        panel_layout_info[panel.id] = (width, height)

    controlnet_infos: List[dict] = []
    if controlnet_config and controlnet_config.get("enabled"):
        modes = controlnet_config.get("modes", [])
        paths = controlnet_config.get("paths", {})
        scales = controlnet_config.get("scales", {})
        for mode in modes:
            path = paths.get(mode)
            if not path:
                continue
            if not Path(path).exists():
                print(f"[CONTROLNET] Missing file for {mode}: {path}")
                continue
            controlnet_infos.append(
                {
                    "mode": mode,
                    "path": path,
                    "scale": scales.get(mode, 0.9),
                }
            )

    model_id = validate_model_id(model_id)
    model_profile, resolved_model_path = ensure_model(model_id, base_model_path)
    selected_base = model_profile["family"]
    print(f"[UNIFIED] Initializing {model_profile['label']}: {resolved_model_path}")
    sd_model = SD(
        resolved_model_path,
        device=device,
        base=selected_base,
        negative_embedding_path=negative_embedding_path,
        controlnet_infos=controlnet_infos,
    )
    if lora_path:
        lora_loaded = sd_model.load_lora(lora_path, lora_scale)
        print(
            f"[UNIFIED] LoRA status: {'applied' if lora_loaded else 'fallback to base model'} "
            f"({lora_path}, scale={lora_scale})"
        )

    background = comic.background
    default_bg_prompt = background.prompt_en if background else "simple background"
    bg_seed = background.seed if background else comic.metadata.get("background_seed", 2000)
    base_seed = seed if seed is not None else comic.metadata.get("base_seed", 1000)

    panel_sizes: Dict[str, Dict[str, int]] = {}
    controlnet_modes = [info["mode"] for info in controlnet_infos]
    style_preset = get_style_preset(style_name)

    # --- Per-character seeds (computed once, for ALL characters in the
    # schema, not just the ones active in the panel being rendered right
    # now). Panels reuse the same seed for the same character_id so the
    # starting noise is at least anchored the same way every time. ---
    character_seeds: Dict[str, int] = {}
    for char_id, char_meta in comic.characters.items():
        char_seed = getattr(char_meta, "seed", None)
        if char_seed is None or char_seed == 0:
            char_hash = sum(ord(c) for c in char_id) % 10000
            char_seed = base_seed + char_hash
        character_seeds[char_id] = char_seed

    for idx, panel in enumerate(comic.panels, start=1):
        if target_panel_ids and panel.id not in target_panel_ids:
            continue
        panel_width, panel_height = panel_layout_info.get(panel.id, (CONFIG.panel.width, CONFIG.panel.height))
        render_width, render_height = _compute_render_size(
            panel_width,
            panel_height,
            max_render_width,
            max_render_height,
        )
        
        bg_prompt = getattr(panel, "background_prompt_en", None) or default_bg_prompt

        characters_meta: List[Tuple] = []
        character_actions_dict: Dict[str, dict] = {}
        character_positions_dict: Dict[str, dict] = {}
        
        if panel.active_char_ids:
            for char_id in panel.active_char_ids:
                char_meta = comic.characters.get(char_id)
                if char_meta:
                    characters_meta.append((char_meta, char_id))

                    char_action_obj = panel.character_actions.get(char_id) if panel.character_actions else None
                    if char_action_obj:
                        if hasattr(char_action_obj, "action_en"):
                            character_actions_dict[char_id] = {
                                "action_en": char_action_obj.action_en,
                                "pose_en": char_action_obj.pose_en,
                                "objects": char_action_obj.objects,
                                "interaction": char_action_obj.interaction,
                            }
                        elif isinstance(char_action_obj, dict):
                            character_actions_dict[char_id] = char_action_obj
                    
                    char_pos_obj = panel.character_positions.get(char_id) if panel.character_positions else None
                    if char_pos_obj:
                        if hasattr(char_pos_obj, "x"):
                            character_positions_dict[char_id] = {
                                "x": char_pos_obj.x,
                                "y": char_pos_obj.y,
                                "anchor": char_pos_obj.anchor,
                            }
                        elif isinstance(char_pos_obj, dict):
                            character_positions_dict[char_id] = char_pos_obj
        
        if not characters_meta:
            print(f"[WARN] Panel {panel.id} has no characters!")
        
        main_char_meta = characters_meta[0][0] if characters_meta else None
        # Shot composition belongs to the panel, not the character portrait.
        camera_angle = None
        camera_distance = None

        cleaned_panel_prompt = clean_instruction_text(panel.panel_prompt_en)
        style_negative_tags = list(style_preset.negative_tags)
        style_negative_tags.extend(_split_extra_tags(negative_prompt_extra))
        panel_prompt, panel_negative = compose_unified_panel_prompt(
            panel_prompt=cleaned_panel_prompt,
            panel_negative=panel.panel_negative_en,
            characters_meta=characters_meta,
            character_actions=character_actions_dict,
            character_positions=character_positions_dict,
            background_prompt=bg_prompt,
            dialogues=panel.dialogues,
            camera_angle=camera_angle,
            camera_distance=camera_distance,
            description_en=panel.description_en,
            required_props=getattr(panel, "required_props", None),
            required_text=getattr(panel, "required_text", None),
            extra_structured_fields=_extract_structured_fields(panel),
            # Compel performs long-prompt chunking. Do not pre-truncate the
            # structured action/prop contract before it reaches Compel.
            max_tokens=None,
            style_positive=style_preset.prompt_tags,
            style_negative=style_negative_tags,
        )

        if characters_meta:
            # Derive the seed from the complete cast, not only the first
            # character, so recurring groups remain reproducible.
            cast_key = ":".join(sorted(char_id for _, char_id in characters_meta))
            cast_hash = int(hashlib.sha256(cast_key.encode("utf-8")).hexdigest()[:8], 16)
            # Reuse one latent anchor for the same recurring cast across the
            # page. Varying the seed per panel made SD1.5 invent a new face,
            # outfit, or extra person even when the prompt was identical about
            # identity. The action/shot prompt still changes each panel; the
            # shared anchor improves facial and clothing continuity.
            panel_seed = (base_seed + cast_hash) % (2**32)
        else:
            panel_seed = (base_seed + bg_seed + idx * 1009) % (2**32)

        render_note = ""
        if render_width != panel_width or render_height != panel_height:
            render_note = f" -> render at {render_width}x{render_height}"
        print(f"[UNIFIED] Generating {panel.id} ({panel_width}x{panel_height}{render_note}, seed={panel_seed})...")
        print(f"  Characters: {[c[1] for c in characters_meta] if characters_meta else 'none'}")
        if characters_meta:
            for char_meta, char_id in characters_meta:
                char_seed = character_seeds.get(char_id, "N/A")
                print(f"    {char_id}: seed={char_seed}")
        print(f"  Prompt: {panel_prompt[:150]}...")

        control_images = None
        if controlnet_modes:
            control_images = build_control_guides(
                render_width,
                render_height,
                characters_meta,
                character_positions_dict,
                requested_modes=controlnet_modes,
            )

        panel_image = sd_model.gen_image(
            context=panel_prompt,
            base_negative=panel_negative,
            sep=panel_steps,
            seed=panel_seed,
            width=render_width,
            height=render_height,
            guidance_scale=guidance_scale,
            control_images=control_images,
        )

        if render_width != panel_width or render_height != panel_height:
            from page.builder import preserve_aspect_resize
            panel_image = preserve_aspect_resize(
                panel_image,
                panel_width,
                panel_height,
                fill_mode="crop",
            )

        panel_path = output_panel_path / f"{panel.id}.png"
        panel_image.save(panel_path, quality=95)
        print(f"[UNIFIED] OK Saved: {panel_path}")

        panel_sizes[panel.id] = {"width": panel_width, "height": panel_height}

    # FREE VRAM
    print("[UNIFIED] Freeing Stable Diffusion VRAM...")
    del sd_model
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return panel_sizes
