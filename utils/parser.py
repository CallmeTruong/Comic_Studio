from dataclasses import dataclass
from typing import Dict, List, Optional

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
    description_vi: str = ""
    active_char_ids: List[str] = None
    character_positions: Dict[str, CharacterPosition] = None
    character_actions: Dict[str, CharacterAction] = None
    dialogues: List[Dialogue] = None
    background_prompt_en: str = None
    
    def __post_init__(self):
        if self.active_char_ids is None:
            self.active_char_ids = []
        if self.character_positions is None:
            self.character_positions = {}
        if self.character_actions is None:
            self.character_actions = {}
        if self.dialogues is None:
            self.dialogues = []

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
    for panel_data in data.get("panels", []):
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
                text=dial_data.get("text", ""),
                emotion=dial_data.get("emotion", ""),
            ))
        
        panels.append(Panel(
            id=panel_data.get("id", ""),
            panel_prompt_en=panel_data.get("panel_prompt_en", ""),
            panel_negative_en=panel_data.get("panel_negative_en", ""),
            description_vi=panel_data.get("description_vi", ""),
            active_char_ids=panel_data.get("active_char_ids", []),
            character_positions=character_positions,
            character_actions=character_actions,
            dialogues=dialogues,
            background_prompt_en=panel_data.get("background_prompt_en"),
        ))

    return Comic(
        title=data.get("title", ""),
        metadata=data.get("metadata", {}),
        background=background,
        characters=characters,
        panels=panels,
    )

