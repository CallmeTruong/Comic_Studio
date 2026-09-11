from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from .smart_analyzer import infer_emotion_from_dialogues_smart
from transformers import CLIPTokenizer

try:
        

    _CLIP_TOKENIZER: Optional[CLIPTokenizer] = CLIPTokenizer.from_pretrained(
        "openai/clip-vit-large-patch14"
    )
except Exception:
    _CLIP_TOKENIZER = None


def truncate_prompt_smart(prompt: str, max_tokens: int = 150) -> str:
    if _CLIP_TOKENIZER is not None:
        try:
            tokens = _CLIP_TOKENIZER.encode(prompt, truncation=False, return_tensors="pt")[0]
            if len(tokens) <= max_tokens:
                return prompt

            truncated_tokens = tokens[: max_tokens - 3]
            truncated_prompt = _CLIP_TOKENIZER.decode(truncated_tokens, skip_special_tokens=True)
            print(
                f"[TRUNCATE] Prompt truncated from {len(tokens)} tokens to {len(truncated_tokens)} tokens"
            )
            return truncated_prompt
        except Exception:
            pass

    max_words = int(max_tokens * 0.75)
    words = prompt.split()
    if len(words) <= max_words:
        return prompt
    truncated = " ".join(words[:max_words])
    print(f"[TRUNCATE] Prompt truncated (fallback) from {len(words)} words to {max_words} words")
    return truncated


def truncate_prompt(prompt: str, max_tokens: int = 150) -> str:
    return truncate_prompt_smart(prompt, max_tokens)

def format_character_template(char_meta, char_id: str, char_action: dict | None = None) -> str:
    """Return the authored character card without guessing its semantics."""
    if not char_meta or not getattr(char_meta, "base_prompt_en", ""):
        return ""
    name = getattr(char_meta, "name", "") or char_id
    identity = " ".join(str(char_meta.base_prompt_en).split())
    parts = [f"{name}, fixed recurring design: {identity}"]
    if char_action:
        for key in ("action_en", "pose_en"):
            value = str(char_action.get(key, "")).strip()
            if value:
                parts.append(value)
        objects = char_action.get("objects") or []
        if objects:
            parts.append("objects: " + ", ".join(str(item) for item in objects))
    return ", ".join(parts)

def compose_unified_panel_prompt(
    panel_prompt: str,
    panel_negative: str | None,
    characters_meta: List | None = None,
    character_actions: Dict[str, dict] | None = None,
    character_positions: Dict[str, dict] | None = None,
    background_prompt: str | None = None,
    dialogues: Iterable = None,
    camera_angle: str | None = None,
    camera_distance: str | None = None,
    description_en: str | None = None,
    required_props: Iterable[str] | None = None,
    required_text: Iterable[str] | None = None,
    extra_structured_fields: Dict[str, str] | None = None,
    max_tokens: int | None = None,
    style_positive: List[str] | None = None,
    style_negative: List[str] | None = None,
) -> tuple[str, str]:
    dialogues = dialogues or []
    # Put immutable identity cards first so CLIP truncation cannot remove them.
    prompt_parts = []

    # 1. Put compact identity capsules first, then the critical visual brief.
    # Keeping the cast separate prevents scene text from swallowing one of the
    # protagonists during CLIP truncation.
    # Props are explicit structured input; never infer them from prose.
    critical_objects = list(dict.fromkeys(
        str(item).strip() for item in (required_props or []) if str(item).strip()
    ))
    required_text = list(dict.fromkeys(
        str(item).strip() for item in (required_text or []) if str(item).strip()
    ))
    # Put one compact fingerprint for every recurring character before the
    # scene description. Both protagonists must survive CLIP truncation.
    if characters_meta:
        for char_meta, char_id in characters_meta:
            identity = format_character_template(char_meta, char_id, None)
            if identity:
                # Compel weight syntax: emphasise identity so it survives
                # cross-attention competition with scene/action tokens.
                prompt_parts.append(f"({identity})1.2")
        # This is derived from the registered schema cast, not from story
        # keywords.  SD 1.5 otherwise tends to replace a single subject with
        # a generic group when the scene contains a prop or doorway.
        cast_names = ", ".join(
            str(getattr(meta, "name", "") or char_id).strip()
            for meta, char_id in characters_meta
        )
        prompt_parts.append(
            f"(ONLY the registered cast: {cast_names}; exactly {len(characters_meta)} visible subject(s), no replacements)1.25"
        )
        if len(characters_meta) > 1:
            prompt_parts.append(
                "all active registered subjects visible together in one readable composition, "
                "preserve their spatial relationship and do not crop or replace any subject"
            )
    # Structured constraints are authored data and therefore take precedence
    # over free-form scene prose when the CLIP safety cap is reached.
    if extra_structured_fields:
        for field_name in ("primary_subject", "secondary_subject", "required_subjects", "required_action", "visual_hierarchy"):
            value = str(extra_structured_fields.get(field_name, "") or "").strip()
            if value:
                prompt_parts.append(f"{field_name.replace('_', ' ')}: {value}")
        # SD 1.5 often collapses a multi-entity beat into an isolated portrait
        # unless the composition is explicitly framed as an interaction. This
        # is a renderer-level invariant derived from structured action data,
        # not a topic-specific keyword rule.
        if extra_structured_fields.get("required_action"):
            prompt_parts.append(
                "full scene, readable spatial relationship, visible interaction, "
                "show the complete action rather than an isolated close-up"
            )
    # Put authored props/text immediately beside the structured subject/action
    # contract.  They must not depend on the free-form panel prose surviving a
    # tokenizer/chunk boundary.
    if critical_objects:
        prompt_parts.append("(CRITICAL VISIBLE PROPS: " + ", ".join(critical_objects) + ")1.3")
    if required_text:
        prompt_parts.append("(VISIBLE TEXT: " + " | ".join(required_text) + ")1.2")
    if panel_prompt:
        prompt_parts.append(panel_prompt)

    # 3. Actions are after the visual brief.  The brief
    # contains the shot's required objects and must survive prompt truncation.
    if character_actions:
        for char_id, char_action in character_actions.items():
            if not char_action:
                continue
            action_text = char_action.get("action_en", "")
            pose_text = char_action.get("pose_en", "")
            if action_text:
                prompt_parts.append(f"{char_id} action: {action_text}")
            elif pose_text:
                prompt_parts.append(f"{char_id} pose: {pose_text}")

    # 3. Background, lighting, and extra details from LLM.
    if background_prompt:
        # Keep the authored setting intact.  Arbitrarily taking the first few
        # words used to discard the location's distinguishing details.  The
        # tokenizer/Compel safety cap below is the single place responsible
        # for length management.
        prompt_parts.append("setting: " + " ".join(str(background_prompt).split()))
    if style_positive:
        prompt_parts.extend(str(tag).strip() for tag in style_positive if str(tag).strip())
        
    # 4. Camera
    if camera_angle:
        prompt_parts.append(camera_angle)
    if camera_distance:
        prompt_parts.append(f"{camera_distance} distance")
        
    emotion = infer_emotion_from_dialogues_smart(dialogues)
    if emotion:
        prompt_parts.append(emotion)
        
    # --- Compel-aware prompt assembly ------------------------------------
    # Compel is responsible for chunking long prompts.  Do not apply a second
    # tokenizer-based cut here: it can discard the action/props at the end of
    # an authored brief before Compel ever sees them.  A caller may still pass
    # an explicit limit when using a backend without Compel.
    prompt_parts.append("high quality")
    unified_prompt = ", ".join(filter(None, prompt_parts))

    if max_tokens is not None:
        unified_prompt = truncate_prompt_smart(unified_prompt, max_tokens=max_tokens)

    negative_parts = [
        "blurry, distorted, bad anatomy, extra limbs, extra fingers",
        "text, watermark, speech bubble, duplicate, cloned character, replacement character, extra characters, "
        "isolated close-up, cropped subject, unrelated collage",
    ]
    if characters_meta:
        negative_parts.append(
            f"unregistered subjects, additional people or creatures, group portrait, duplicate of registered subject"
        )
    if panel_negative:
        negative_parts.insert(0, " ".join(str(panel_negative).split()))
    if style_negative:
        negative_parts.extend(style_negative)
    
    # Required props are explicit structured input; never infer story objects
    # from arbitrary prose.
    if required_props:
        negative_parts.append("missing required props, empty hands, unrelated objects, blank background")
    
    unified_negative = ", ".join(filter(None, negative_parts))
    if max_tokens is not None:
        unified_negative = truncate_prompt_smart(unified_negative, max_tokens=max_tokens)
    
    return unified_prompt, unified_negative
