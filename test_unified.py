import json
from panel_engine.unified_pipeline import generate_panels_unified
from config import CONFIG

try:
    generate_panels_unified(
        schema_path="outputs/story_1788957420.json",
        output_panel_dir="outputs/panels",
        base_model_path="models/base/comicBabes_v2.safetensors",
        device="cuda",
        base="SDv1.5",
        lora_path="models/loras/ghibli_style_offset.safetensors",
        lora_scale=1.0,
        panel_steps=20,
        guidance_scale=7.5,
        layout_name=None,
        max_render_width=896,
        max_render_height=896,
        negative_prompt_extra="bad anatomy",
        series_id="short_comic",
        seed=12345,
        style_name="flat_comic",
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
