from typing import TypedDict, List, Any

class StudioState(TypedDict):
    # Stable identifier for one user request. Vision-QA retries reuse the same
    # output directory/page instead of creating another History entry.
    generation_id: str
    user_prompt: str
    requested_language: str
    current_schema: dict
    validation_errors: List[str]
    next_step: str
    output_page: str
    output_pages: List[str]
    layoutStyle: str
    mangaLayout: str
    steps: int
    guidance: float
    lora: str
    negativePrompt: str
    seed: str
    pageCount: int
    retry_count: int
    max_retries: int
    generation_error: str
    story_plan: dict
    dialogue_plan: dict
    vision_qa: dict
    vision_retry_count: int
    max_vision_retries: int
