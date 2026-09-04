from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class PageScript(BaseModel):
    page_number: int
    content: str

class StudioState(TypedDict):
    user_prompt: str
    chapter_number: int
    
    # Lore & Memory
    retrieved_lore: str
    unresolved_hooks: str
    
    # Scripts & Outlines
    chapter_outline: str
    page_scripts: List[PageScript]
    
    # Generation State
    current_page_idx: int
    current_schema: Optional[Dict[str, Any]]
    
    # Validation & Feedback
    validation_errors: List[str]
    vision_feedback: str
    human_feedback: str
    
    # Next node routing
    next_step: str
