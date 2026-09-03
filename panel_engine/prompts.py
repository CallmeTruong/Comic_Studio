from __future__ import annotations

import re
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
                f"[TRUNCATE] Prompt truncated từ {len(tokens)} tokens xuống {len(truncated_tokens)} tokens"
            )
            return truncated_prompt
        except Exception:
            pass

    max_words = int(max_tokens * 0.75)
    words = prompt.split()
    if len(words) <= max_words:
        return prompt
    truncated = " ".join(words[:max_words])
    print(f"[TRUNCATE] Prompt truncated (fallback) từ {len(words)} từ xuống {max_words} từ")
    return truncated


def truncate_prompt(prompt: str, max_tokens: int = 150) -> str:
    return truncate_prompt_smart(prompt, max_tokens)

# Stop words để loại bỏ
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "as", "is", "was", "are", "were", "been", "be", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "should", "could", "may", "might", "must", "can",
    "this", "that", "these", "those", "who", "which", "what", "where", "when", "why", "how"
}

def remove_stop_words(text: str) -> str:
    """Loại bỏ stop words để tiết kiệm tokens"""
    words = text.split()
    filtered = [w for w in words if w.lower() not in _STOP_WORDS]
    return " ".join(filtered)

def compress_phrases(text: str) -> str:
    """Nén các cụm từ thường dùng thành ngắn gọn hơn"""
    # Dictionary các cụm từ và cách nén
    replacements = {
        # Character descriptions
        "young female student": "female student",
        "young male student": "male student",
        "young student": "student",
        "wearing a": "wearing",
        "wearing an": "wearing",
        "with brown hair": "brown hair",
        "with black hair": "black hair",
        "with short hair": "short hair",
        "with long hair": "long hair",
        "wearing glasses": "glasses",
        "wearing light blue hoodie": "light blue hoodie",
        "wearing forest green": "forest green",
        
        # Actions
        "accidentally tips over": "tips",
        "accidentally spills": "spills",
        "leaning forward": "leans forward",
        "looking at": "looks at",
        "reaching out": "reaches",
        "holding out": "holds",
        
        # Objects
        "coffee cup tipped over": "coffee cup tipped",
        "coffee-stained notebook": "stained notebook",
        "open notebook": "notebook",
        "white tissue paper": "tissue",
        
        # Tags
        "clearly visible": "",
        "prominent": "",
        "consistent": "",
        "same character": "",
        "on desk": "",
        "in hand": "",
        
        # Redundant phrases
        ", ,": ",",
        "  ": " ",
    }
    
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    # Loại bỏ dấu phẩy thừa và khoảng trắng
    result = re.sub(r",\s*,", ",", result)  # ", ," -> ","
    result = re.sub(r"\s+", " ", result)  # Multiple spaces -> single space
    result = result.strip(", ")  # Remove leading/trailing commas and spaces
    
    return result

def compress_prompt(prompt: str) -> str:
    """Nén prompt bằng cách loại bỏ stop words và nén cụm từ"""
    # Bước 1: Loại bỏ stop words
    compressed = remove_stop_words(prompt)
    
    # Bước 2: Nén cụm từ
    compressed = compress_phrases(compressed)
    
    return compressed

def format_character_template(char_meta, char_id: str, char_action: dict | None = None) -> str:
    """Format character description theo template ngắn gọn"""
    if not char_meta:
        return ""
    
    char_desc = char_meta.base_prompt_en
    if not char_desc:
        return ""
    
    gender, age = extract_gender_and_age(char_desc)
    char_details = extract_character_details(char_desc)
    char_name = getattr(char_meta, "name", char_id.replace("char_", "").replace("student_", "").capitalize())
    
    # Template ngắn gọn: "name gender, hair, eyes, clothing, glasses"
    parts = []
    
    # Name + gender
    if gender == "female":
        parts.append(f"{char_name} female")
    elif gender == "male":
        parts.append(f"{char_name} male")
    else:
        parts.append(char_name)
    
    # Features (chỉ giữ 2-3 quan trọng nhất)
    if char_details["hair"]:
        parts.append(char_details["hair"].strip())
    if char_details["eyes"]:
        parts.append(char_details["eyes"].strip())
    if char_details["clothing"]:
        # Rút gọn clothing: chỉ lấy màu và loại
        clothing = char_details["clothing"].strip()
        # "wearing light blue hoodie" -> "blue hoodie"
        clothing = re.sub(r"wearing\s+", "", clothing, flags=re.IGNORECASE)
        clothing = re.sub(r"light\s+", "", clothing, flags=re.IGNORECASE)
        clothing = re.sub(r"dark\s+", "", clothing, flags=re.IGNORECASE)
        parts.append(clothing)
    
    if "glasses" in char_desc.lower():
        parts.append("glasses")
    
    # Action (rút gọn)
    if char_action:
        action_en = char_action.get("action_en", "")
        if action_en:
            # Chỉ lấy 6-8 từ đầu
            action_words = action_en.split()
            if len(action_words) > 8:
                action_short = " ".join(action_words[:8])
                parts.append(action_short)
    else:
                parts.append(action_en)
    
    return ", ".join(parts)

def extract_gender_and_age(char_desc: str) -> tuple[str, str]:
    gender = None
    age = None
    
    char_lower = char_desc.lower()
    
    if "female" in char_lower or "woman" in char_lower or "girl" in char_lower:
        gender = "female"
    elif "male" in char_lower or "man" in char_lower or "boy" in char_lower:
        gender = "male"
    
    if "young" in char_lower or "teen" in char_lower or "student" in char_lower:
        age = "young"
    elif "adult" in char_lower or "mature" in char_lower:
        age = "adult"
    elif "old" in char_lower or "elderly" in char_lower:
        age = "old"
    
    return gender or "unknown", age or "unknown"

def extract_character_details(char_desc: str) -> Dict[str, str]:
    details = {
        "hair": "",
        "eyes": "",
        "clothing": "",
        "features": "",
    }
    
    char_lower = char_desc.lower()
    
    hair_patterns = [
        (r"\b(brown|black|blonde|blond|red|auburn)\s+hair\b", "hair"),
        (r"\b(short|long|medium)\s+hair\b", "hair"),
        (r"\b(ponytail|braid|bun)\b", "hair"),
    ]
    
    for pattern, key in hair_patterns:
        match = re.search(pattern, char_lower)
        if match:
            details["hair"] += match.group(0) + " "
    
    eye_patterns = [
        (r"\b(brown|blue|green|hazel|black)\s+eyes?\b", "eyes"),
    ]
    
    for pattern, key in eye_patterns:
        match = re.search(pattern, char_lower)
        if match:
            details["eyes"] += match.group(0) + " "
    
    clothing_patterns = [
        (r"\b(hoodie|jacket|shirt|dress|jeans|pants|skirt)\b", "clothing"),
        (r"\b(blue|red|green|white|black|brown|purple|pink)\s+(hoodie|jacket|shirt|dress|jeans)\b", "clothing"),
    ]
    
    for pattern, key in clothing_patterns:
        match = re.search(pattern, char_lower)
        if match:
            details["clothing"] += match.group(0) + " "
    
    feature_patterns = [
        (r"\b(thick|thin)\s+eyebrows?\b", "features"),
        (r"\b(round|oval|square)\s+face\b", "features"),
    ]
    
    for pattern, key in feature_patterns:
        match = re.search(pattern, char_lower)
        if match:
            details["features"] += match.group(0) + " "
    
    return {k: v.strip() for k, v in details.items()}

def format_character_description(
    char_meta,
    char_id: str,
    character_action: dict | None = None,
    position: str | None = None,
) -> str:
    if not char_meta:
        return ""
    
    parts = []
    
    char_desc = char_meta.base_prompt_en
    if not char_desc:
        return ""
    
    gender, age = extract_gender_and_age(char_desc)
    char_details = extract_character_details(char_desc)
    
    char_name = getattr(char_meta, "name", char_id.replace("char_", "").replace("student_", "").capitalize())
    
    # Nhấn mạnh giới tính ngay từ đầu để đảm bảo consistency
    if gender == "female":
        char_tag = f"young female student {char_name}"
    elif gender == "male":
        char_tag = f"young male student {char_name}"
    else:
        char_tag = f"character {char_name}"
    
    parts.append(char_tag)
    
    # Rút gọn: chỉ giữ thông tin quan trọng nhất để tiết kiệm tokens
    # Kết hợp các đặc điểm thành 1 câu ngắn gọn
    char_features = []
    if char_details["hair"]:
        char_features.append(char_details["hair"].strip())
    if char_details["eyes"]:
        char_features.append(char_details["eyes"].strip())
    if char_details["clothing"]:
        char_features.append(f"wearing {char_details['clothing'].strip()}")
    if "glasses" in char_desc.lower() or "spectacles" in char_desc.lower():
        char_features.append("wearing glasses")
    
    if char_features:
        # Kết hợp tất cả features thành 1 câu ngắn
        parts.append(", ".join(char_features[:3]))  # Chỉ giữ 3 features đầu
    
    if position:
        parts.append(f"on {position}")
    
    # Không thêm char_desc đầy đủ nữa (đã có trong panel_prompt), chỉ giữ base description ngắn
    # Rút gọn char_desc: chỉ lấy 10-15 từ đầu (tên + đặc điểm chính)
    char_desc_words = char_desc.split()
    if len(char_desc_words) > 15:
        char_desc_short = " ".join(char_desc_words[:15])
        parts.append(char_desc_short)
    else:
        parts.append(char_desc)
    
    if character_action:
        action_en = character_action.get("action_en", "")
        pose_en = character_action.get("pose_en", "")
        objects = character_action.get("objects", [])
        
        # Rút gọn action: chỉ lấy 10-12 từ đầu (hành động chính)
        if action_en:
            action_words = action_en.split()
            if len(action_words) > 12:
                action_short = " ".join(action_words[:12])
                parts.append(f"{action_short}, prominent action")
            else:
                parts.append(f"{action_en}, prominent action")
        elif pose_en:
            pose_words = pose_en.split()
            if len(pose_words) > 8:
                pose_short = " ".join(pose_words[:8])
                parts.append(f"{pose_short}, prominent pose")
            else:
                parts.append(f"{pose_en}, prominent pose")
        
        # Rút gọn objects: chỉ giữ tên object và trạng thái chính
        if objects:
            for obj in objects[:2]:  # Chỉ giữ 2 objects đầu
                obj_lower = obj.lower()
                if "coffee" in obj_lower:
                    if "spill" in obj_lower or "tipped" in obj_lower:
                        parts.append("coffee cup tipped over, spilling")
                    else:
                        parts.append("coffee cup")
                elif "notebook" in obj_lower or "book" in obj_lower:
                    if "stain" in obj_lower or "stained" in obj_lower:
                        parts.append("coffee-stained notebook")
                    else:
                        parts.append("notebook")
                elif "tissue" in obj_lower:
                    parts.append("tissue")
                elif "pen" in obj_lower:
                    parts.append("pen")
                else:
                    # Rút gọn object name
                    obj_short = obj.split()[0] if obj.split() else obj
                    parts.append(obj_short)
    
    return ", ".join(parts)

def extract_important_objects(panel_prompt: str, character_actions: Dict[str, dict]) -> List[str]:
    objects = []
    
    panel_lower = panel_prompt.lower()
    
    # Rút gọn object descriptions: chỉ giữ tên và trạng thái chính
    if "coffee" in panel_lower:
        if "spill" in panel_lower or "spilling" in panel_lower or "spilled" in panel_lower:
            objects.append("coffee cup tipped over")
        else:
            objects.append("coffee cup")
    
    if "notebook" in panel_lower or "book" in panel_lower:
        if "stain" in panel_lower or "stained" in panel_lower or "spill" in panel_lower:
            objects.append("coffee-stained notebook")
        else:
            objects.append("notebook")
    
    if "tissue" in panel_lower or "paper" in panel_lower:
        objects.append("tissue")
    
    # Chỉ lấy objects từ character_actions nếu chưa có trong panel_prompt
    for char_id, action in character_actions.items():
        if action and action.get("objects"):
            for obj in action.get("objects", []):
                obj_lower = obj.lower()
                if "coffee" in obj_lower and "coffee cup" not in " ".join(objects).lower():
                    if "spill" in obj_lower or "tipped" in obj_lower:
                        objects.append("coffee cup tipped over")
                    else:
                        objects.append("coffee cup")
                elif "notebook" in obj_lower and "notebook" not in " ".join(objects).lower():
                    if "stain" in obj_lower:
                        objects.append("coffee-stained notebook")
                    else:
                        objects.append("notebook")
                elif "tissue" in obj_lower and "tissue" not in " ".join(objects).lower():
                    objects.append("tissue")
                elif "pen" in obj_lower:
                    objects.append("pen")
    
    return list(set(objects))

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
    max_tokens: int = 150,
    style_positive: List[str] | None = None,
    style_negative: List[str] | None = None,
) -> tuple[str, str]:
    dialogues = dialogues or []
    
    priority_parts = []
    secondary_parts = []
    
    # Bỏ background_prompt vì đã có trong panel_prompt, tiết kiệm tokens
    # if background_prompt:
    #     secondary_parts.append(background_prompt)
    
    if characters_meta and len(characters_meta) > 0:
        char_descriptions = []
        interaction_parts = []
        
        for i, (char_meta, char_id) in enumerate(characters_meta):
            char_action = character_actions.get(char_id) if character_actions else None
            char_pos = character_positions.get(char_id) if character_positions else None
            
            position_str = None
            if char_pos:
                x_pos = char_pos.get("x", "center")
                y_pos = char_pos.get("y", "middle")
                if x_pos == "left" and y_pos == "middle":
                    position_str = "left"
                elif x_pos == "right" and y_pos == "middle":
                    position_str = "right"
                elif x_pos == "center" and y_pos == "top":
                    position_str = "top center"
                elif x_pos == "center" and y_pos == "bottom":
                    position_str = "bottom center"
            
            # Sử dụng template ngắn gọn thay vì description đầy đủ
            char_desc = format_character_template(char_meta, char_id, char_action)
            if char_desc:
                char_descriptions.append(char_desc)
            
            if char_action and char_action.get("interaction"):
                interaction_parts.append(char_action.get("interaction"))
        
        if char_descriptions:
            if len(char_descriptions) == 1:
                priority_parts.append(char_descriptions[0])
                priority_parts.append("ONLY ONE CHARACTER, no extra people")
            elif len(char_descriptions) == 2:
                # Rút gọn: chỉ giữ thông tin quan trọng nhất
                priority_parts.append(f"{char_descriptions[0]} AND {char_descriptions[1]}")
                priority_parts.append("EXACTLY TWO CHARACTERS, no extra people, no third person")
            else:
                priority_parts.append(", ".join(char_descriptions[:-1]) + f", AND {char_descriptions[-1]}")
                priority_parts.append(f"EXACTLY {len(char_descriptions)} CHARACTERS, no extra people")
        
        if interaction_parts:
            priority_parts.append(", ".join(interaction_parts))
    
    # Put panel_prompt in priority for better content accuracy
    if panel_prompt:
        priority_parts.insert(0, panel_prompt)
    
    important_objects = extract_important_objects(panel_prompt or "", character_actions or {})
    if important_objects:
        priority_parts.append(", ".join(important_objects))
    
    if camera_angle or camera_distance:
        camera_parts = []
        if camera_angle:
            camera_parts.append(camera_angle)
        if camera_distance:
            camera_parts.append(f"{camera_distance} distance")
        if camera_parts:
            secondary_parts.append(", ".join(camera_parts))
    
    emotion = infer_emotion_from_dialogues_smart(dialogues)
    if emotion:
        secondary_parts.append(emotion)
    
    # Remove "beautiful" to save tokens
    prompt_parts = []
    
    if priority_parts:
        prompt_parts.append(", ".join(priority_parts))
    
    # Only add secondary_parts if there is space (after truncate)
    # if secondary_parts:
    #     prompt_parts.append(", ".join(secondary_parts))
    
    # Remove style_positive and "award winning" to save tokens
    # Only keep "high quality" if there is space
    # if style_positive:
    #     prompt_parts.extend(style_positive)
    # prompt_parts.extend(["high quality"])
    
    unified_prompt = ", ".join(filter(None, prompt_parts))
    
    # Step 1: Compress prompt (remove stop words, compress phrases)
    unified_prompt = compress_prompt(unified_prompt)
    
    # Step 2: Truncate if still too long
    # CLIP tokenizer supports max 77 tokens, so we must be selective
    unified_prompt = truncate_prompt_smart(unified_prompt, max_tokens=max_tokens)
    
    # If still too long after truncate, optimize by keeping most important parts
    if _CLIP_TOKENIZER is not None:
        try:
            tokens = _CLIP_TOKENIZER.encode(unified_prompt, truncation=False, return_tensors="pt")[0]
            if len(tokens) > max_tokens:
                # Priority: panel_prompt > character descriptions > objects
                essential_parts = []
                
                # Always keep panel_prompt (most important - main content)
                if priority_parts and len(priority_parts) > 0:
                    essential_parts.append(priority_parts[0])  # panel_prompt
                
                # Keep character descriptions short (only name and main traits)
                if len(priority_parts) > 1:
                    # Get first character description (shorter)
                    char_desc = priority_parts[1] if len(priority_parts) > 1 else ""
                    if char_desc:
                        # Shorten character description: only keep name, gender, main clothing
                        char_words = char_desc.split()
                        # Keep ~15-20 first words (name + main traits)
                        char_desc_short = " ".join(char_words[:20])
                        essential_parts.append(char_desc_short)
                
                # Keep important objects (if any)
                if len(priority_parts) > 2:
                    # Find objects part (usually at end of priority_parts)
                    for part in priority_parts[2:]:
                        if any(obj in part.lower() for obj in ["coffee", "notebook", "tissue", "pen"]):
                            obj_words = part.split()
                            essential_parts.append(" ".join(obj_words[:10]))  # Keep ~10 words
                            break
                
                # Add short style tags
                essential_parts.append("high quality")
                
                unified_prompt = ", ".join(filter(None, essential_parts))
                unified_prompt = truncate_prompt_smart(unified_prompt, max_tokens=max_tokens)
        except Exception:
            pass

    negative_parts = [
        panel_negative or "",
        "speech bubble, caption, subtitle",
        "blurry, low quality, distorted, artifacts, noise",
        "extra characters, duplicate, wrong costume, off-model",
    ]
    if style_negative:
        negative_parts.extend(style_negative)
    
    if characters_meta and len(characters_meta) > 0:
        negative_parts.append("teacher, adult, old person, elderly")
        
        # Shorten negative prompts but emphasize count and gender
        if len(characters_meta) == 1:
            negative_parts.append("multiple people, extra characters, third person")
        elif len(characters_meta) == 2:
            # Emphasize: exactly 2 people with correct gender
            genders = [extract_gender_and_age(c.base_prompt_en)[0] for c, _ in characters_meta]
            if "female" in genders and "male" in genders:
                # One female and one male
                negative_parts.append("no third person, no extra people, no same gender pair")
                negative_parts.append("must have one female and one male")
            else:
                negative_parts.append("no third person, no extra people")
            negative_parts.append("three people, four people, multiple people")
        else:
            negative_parts.append(f"no extra people, exactly {len(characters_meta)} characters")
        
        # Emphasize gender for each character
        for char_meta, char_id in characters_meta:
            gender, age = extract_gender_and_age(char_meta.base_prompt_en)
            if gender == "female":
                negative_parts.append("male character")
            elif gender == "male":
                negative_parts.append("female character")
    
    if panel_prompt:
        panel_lower = panel_prompt.lower()
        if "coffee" in panel_lower:
            if "spill" in panel_lower or "spilling" in panel_lower:
                negative_parts.append("no coffee cup, missing coffee, no spill, no liquid, clean desk, dry notebook")
            else:
                negative_parts.append("no coffee cup, missing coffee, clean desk, no liquid")
        if "notebook" in panel_lower or "book" in panel_lower:
            negative_parts.append("no notebook, missing notebook, empty desk, no book, closed book")
        if "tissue" in panel_lower or "paper" in panel_lower:
            negative_parts.append("no tissue, missing tissue, no paper")
    
    # Add stronger negative prompts to remove extra characters
    if characters_meta and len(characters_meta) == 2:
        negative_parts.append("3 people, 4 people, 5 people, 6 people, many people, multiple people, extra characters, background characters, crowd, group, bystanders, onlookers, other students, other people, additional people, more than 2 people, more than two characters")
    
    unified_negative = ", ".join(filter(None, negative_parts))
    unified_negative = truncate_prompt_smart(unified_negative, max_tokens=max_tokens)
    
    return unified_prompt, unified_negative
