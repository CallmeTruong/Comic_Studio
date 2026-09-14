from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


def resolve_lora_selection(selection: str | None, directory: str = "models/loras") -> str | None:
    """Resolve a user-selected LoRA filename to a full path safely."""
    if not selection:
        return None
    requested = Path(str(selection)).name.casefold()
    root = Path(directory)
    if not requested or not root.exists():
        return None
    supported = {".safetensors", ".pt", ".ckpt"}
    return next(
        (str(path) for path in root.iterdir()
         if path.is_file() and path.suffix.casefold() in supported
         and path.name.casefold() == requested),
        None,
    )

load_dotenv()

@dataclass
class PathConfig:
    panel_dir: str = "outputs/panels"
    output_page: str = "comic_page.png"

@dataclass
class ModelConfig:
    base_model: str = "models/base/comicBabes_v2.safetensors"
    lora_scale: float = 1.0
    negative_prompt_extra: str = "bad anatomy, extra limbs, text artifact"
    negative_embedding: str | None = None
    device: str = "cuda"

@dataclass
class QualityConfig:
    panel_steps: int = 80
    max_render_width: int = 896
    max_render_height: int = 896

    def __post_init__(self):
        self.max_render_width = max(256, self.max_render_width)
        self.max_render_height = max(256, self.max_render_height)

@dataclass
class StyleConfig:
    preset: str = "flat_comic"

@dataclass
class StoryConfig:
    max_retries: int = 3

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

    def to_dict(self):
        import dataclasses
        return dataclasses.asdict(self)

    def from_dict(self, data: dict):
        if 'paths' in data:
            for k, v in data['paths'].items():
                if hasattr(self.paths, k): setattr(self.paths, k, v)
        if 'models' in data:
            for k, v in data['models'].items():
                if hasattr(self.models, k): setattr(self.models, k, v)
        if 'quality' in data:
            for k, v in data['quality'].items():
                if hasattr(self.quality, k): setattr(self.quality, k, v)
        if 'story' in data:
            for k, v in data['story'].items():
                if hasattr(self.story, k): setattr(self.story, k, v)
        if 'style' in data:
            for k, v in data['style'].items():
                if hasattr(self.style, k): setattr(self.style, k, v)
        if 'page' in data:
            for k, v in data['page'].items():
                if hasattr(self.page, k): setattr(self.page, k, v)
        if 'panel' in data:
            for k, v in data['panel'].items():
                if hasattr(self.panel, k): setattr(self.panel, k, v)

CONFIG = Config()

