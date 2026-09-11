from dataclasses import dataclass
from typing import Dict, List, Optional


def _normalize_string_list(value) -> List[str]:
    """Normalize authored collection fields without interpreting story prose."""
    if value is None:
        return []
    if isinstance(value, dict):
        value = [item for item in value.values() if isinstance(item, (str, int, float))]
    elif isinstance(value, (str, int, float)):
        value = [value]
    elif not isinstance(value, (list, tuple, set)):
        return []
    placeholders = {"none", "null", "n/a", "na", "unknown", "not applicable"}
    return list(dict.fromkeys(
        text for item in value
        if (text := str(item).strip()) and text.casefold() not in placeholders
    ))


def repair_mojibake(value: str) -> str:
    """Repair common UTF-8 text decoded as Windows-1252/Latin-1.

    Only apply the reversible conversion when typical corruption markers are
    present, so valid multilingual text is left untouched.
    """
    # Include common punctuation corruption as well as Vietnamese UTF-8
    # decoded as Latin-1/Windows-1252. Dialogue is user-facing, so repair it
    # before bubble rendering and Vision QA.
    mojibake_markers = (
        "\u00c3", "\u00c2", "\u00c4", "\u00c6", "\u00e1\u00ba", "\u00e1\u00bb",
        "\u00e2\u20ac\u2122", "\u00e2\u20ac\u0153", "\u00e2\u20ac\u009d",
        "\u00e2\u20ac\u0093", "\u00e2\u20ac\u0094",
    )
    if not isinstance(value, str) or not any(marker in value for marker in mojibake_markers):
        return value
    for source_encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
            if repaired != value:
                return repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return value

@dataclass
class CharacterPosition:
    x: str | float
    y: str | float
    anchor: str = "center"

@dataclass
class CharacterAction:
    action_en: str = ""
    pose_en: str = ""
    objects: List[str] = None
    interaction: str = ""
    
    def __post_init__(self):
        if self.objects is None:
            self.objects = []

@dataclass
class Dialogue:
    character_id: str
    text: str
    emotion: str = ""

@dataclass
class Character:
    name: str
    description: str
    base_prompt_en: str
    base_negative_en: str = ""
    camera_angle: str = "close-up"
    camera_distance: str = "close"
    seed: int = 0

@dataclass
class Background:
    prompt_en: str
    negative_en: str = ""
    seed: int = 2000

@dataclass
class Panel:
    id: str
    panel_prompt_en: str
    panel_negative_en: str = ""
    description_en: str = ""
    active_char_ids: List[str] = None
    character_positions: Dict[str, CharacterPosition] = None
    character_actions: Dict[str, CharacterAction] = None
    dialogues: List[Dialogue] = None
    background_prompt_en: str = None
    page_number: int = 1
    required_props: List[str] = None
    required_text: List[str] = None
    primary_subject: str = ""
    secondary_subject: str = ""
    visual_hierarchy: str = ""
    required_subjects: List[str] = None
    required_action: str = ""
    
    def __post_init__(self):
        if self.active_char_ids is None:
            self.active_char_ids = []
        if self.character_positions is None:
            self.character_positions = {}
        if self.character_actions is None:
            self.character_actions = {}
        if self.dialogues is None:
            self.dialogues = []
        # LLMs occasionally return a structured object for a collection field
        # (for example {"primary": ..., "secondary": ...}).  Normalize at
        # the schema boundary so every renderer receives the declared list
        # type; never let downstream code iterate object keys as if they were
        # visual subjects or props.
        self.required_props = _normalize_string_list(self.required_props)
        self.required_text = _normalize_string_list(self.required_text)
        if isinstance(self.required_subjects, dict):
            self.required_subjects = _normalize_string_list([
                self.required_subjects.get("primary"),
                self.required_subjects.get("secondary"),
            ])
        else:
            self.required_subjects = _normalize_string_list(self.required_subjects)

@dataclass
class Comic:
    title: str
    metadata: Dict
    background: Optional[Background]
    characters: Dict[str, Character]
    panels: List[Panel]

def load_comic_from_json(data: dict) -> Comic:
    background = None
    if data.get("background"):
        bg_data = data["background"]
        background = Background(
            prompt_en=bg_data.get("prompt_en", ""),
            negative_en=bg_data.get("negative_en", ""),
            seed=bg_data.get("seed", 2000),
        )
    
    characters = {}
    for cid, ch_data in data.get("characters", {}).items():
        characters[cid] = Character(
            name=ch_data.get("name", ""),
            description=ch_data.get("description", ""),
            base_prompt_en=ch_data.get("base_prompt_en", ""),
            base_negative_en=ch_data.get("base_negative_en", ""),
            camera_angle=ch_data.get("camera_angle", "close-up"),
            camera_distance=ch_data.get("camera_distance", "close"),
            seed=ch_data.get("seed", 0),
        )
    
    panels = []
    
    # Handle multi-page schema
    if "pages" in data:
        for page_data in data.get("pages", []):
            page_num = page_data.get("page_number", 1)
            for panel_data in page_data.get("panels", []):
                panels.append(_parse_panel(panel_data, page_num))
    else:
        # Fallback for flat panels array
        for panel_data in data.get("panels", []):
            panels.append(_parse_panel(panel_data, 1))
            
    return Comic(
        title=data.get("title", "Untitled"),
        metadata=data.get("metadata", {}),
        background=background,
        characters=characters,
        panels=panels,
    )

def _parse_panel(panel_data: dict, page_number: int) -> Panel:
    character_positions = {}
    for cid, pos_data in panel_data.get("character_positions", {}).items():
        character_positions[cid] = CharacterPosition(
                            x=pos_data.get("x", "center"),
                            y=pos_data.get("y", "middle"),
                            anchor=pos_data.get("anchor", "center"),
        )
    
    character_actions = {}
    for cid, action_data in panel_data.get("character_actions", {}).items():
        character_actions[cid] = CharacterAction(
                action_en=action_data.get("action_en", ""),
                pose_en=action_data.get("pose_en", ""),
                objects=action_data.get("objects", []),
            interaction=action_data.get("interaction", ""),
        )
    
    dialogues = []
    for dial_data in panel_data.get("dialogues", []):
        dialogues.append(Dialogue(
            character_id=dial_data.get("character_id", ""),
            text=repair_mojibake(dial_data.get("text", "")),
            emotion=dial_data.get("emotion", ""),
        ))
        
    return Panel(
        id=panel_data.get("id", ""),
        panel_prompt_en=panel_data.get("panel_prompt_en", ""),
        panel_negative_en=panel_data.get("panel_negative_en", ""),
        description_en=panel_data.get("description_en", ""),
        active_char_ids=panel_data.get("active_char_ids", []),
        character_positions=character_positions,
        character_actions=character_actions,
        dialogues=dialogues,
        background_prompt_en=panel_data.get("background_prompt_en", ""),
        page_number=page_number,
        required_props=_normalize_string_list(panel_data.get("required_props", [])),
        required_text=_normalize_string_list(panel_data.get("required_text", [])),
        primary_subject=panel_data.get("primary_subject", ""),
        secondary_subject=panel_data.get("secondary_subject", ""),
        visual_hierarchy=panel_data.get("visual_hierarchy", ""),
        required_subjects=panel_data.get("required_subjects", []),
        required_action=panel_data.get("required_action", ""),
    )
