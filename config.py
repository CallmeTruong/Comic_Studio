from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class PathConfig:
    schema: str = "data/base/schema/story.json"
    character_dir: str = "outputs/characters"
    panel_dir: str = "outputs/panels"
    output_page: str = "comic_page.png"
    background_cache_dir: str | None = None

@dataclass
class ModelConfig:
    base_model: str = "models/base/comicBabes_v2.safetensors"
    inpaint_model: str = "models/base/epicrealism_v10-inpainting.safetensors"
    lora_path: str = "models/loras/ghibli_style_offset.safetensors"
    lora_scale: float = 1.0
    controlnet_canny: str = "models/controlnet/control_v11p_sd15_canny.pth"
    controlnet_openpose: str = "models/controlnet/control_v11p_sd15_openpose_2.pth"
    controlnet_depth: str = "models/controlnet/control_v11f1p_sd15_depth.pth"
    controlnet_modes: list[str] = field(default_factory=lambda: ["canny", "openpose"])
    controlnet_scales: dict | None = None
    use_controlnet: bool = False 
    guidance_scale: float = 8.5
    negative_prompt_extra: str = "bad anatomy, extra limbs, text artifact"
    negative_embedding: str = "models/embeddings/negative_hand-neg.pt"
    device: str = "cuda"

    def __post_init__(self):
        if not isinstance(self.controlnet_modes, list):
            self.controlnet_modes = list(self.controlnet_modes or [])
        if self.controlnet_scales is None:
            self.controlnet_scales = {
                "canny": 0.8,
                "openpose": 0.9,
                "depth": 0.6,
            }

@dataclass
class QualityConfig:
    mode: str = "balanced"
    base_steps: int = 80
    panel_steps: int = 60 
    bubble_steps: int = 40
    max_render_width: int = 1024
    max_render_height: int = 1024
    step_multipliers: dict = None
    min_diffusion_steps: int = 32
    max_diffusion_steps: int = 180
    
    def __post_init__(self):
        if self.step_multipliers is None:
            self.step_multipliers = {
                "fast": 0.6,
                "balanced": 1.0,
                "high": 1.3,
            }
        self.max_render_width = max(256, self.max_render_width)
        self.max_render_height = max(256, self.max_render_height)
        self.min_diffusion_steps = max(10, self.min_diffusion_steps)
        self.max_diffusion_steps = max(self.min_diffusion_steps, self.max_diffusion_steps)

@dataclass
class StyleConfig:
    preset: str = "neutral"

@dataclass
class StoryConfig:
    prompt: str = "A santa clause make a candy for kids, 4 panel"
    cleanup_before_run: bool = True
    force_regenerate_schema: bool = True
    layout_name: str = "auto"
    max_retries: int = 3
    retry_backoff: float = 2.0
    timeout: int = 120

@dataclass
class PanelConfig:
    width: int = 768
    height: int = 1024
    fallback_width: int = 512
    fallback_height: int = 768

@dataclass
class PageConfig:
    width: int = 2480
    height: int = 3508
    margin: int = 60
    gutter: int = 20


@dataclass
class Config:
    paths: PathConfig = None
    models: ModelConfig = None
    quality: QualityConfig = None
    story: StoryConfig = None
    style: StyleConfig = None
    page: PageConfig = None
    panel: PanelConfig = None
    
    def __post_init__(self):
        if self.paths is None:
            self.paths = PathConfig()
        if self.models is None:
            self.models = ModelConfig()
        if self.quality is None:
            self.quality = QualityConfig()
        if self.story is None:
            self.story = StoryConfig()
        if self.style is None:
            self.style = StyleConfig()
        if self.page is None:
            self.page = PageConfig()
        if self.panel is None:
            self.panel = PanelConfig()

CONFIG = Config()