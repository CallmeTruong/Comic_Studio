from typing import TypedDict, List, Any

class StudioState(TypedDict):
    user_prompt: str
    current_schema: dict
    validation_errors: List[str]
    next_step: str
    output_page: str
    layoutStyle: str
    mangaLayout: str
    steps: int
    guidance: float
    lora: str
    negativePrompt: str
    seed: str
