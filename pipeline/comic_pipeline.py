from pathlib import Path
import json
from story_engine.llm_generator import generate_schema
from panel_engine.unified_pipeline import generate_panels_unified
from page.layouts import select_layout_name

def generate_comic(
    prompt: str,
    base_schema_path: str = "data/base/schema/story.json",
    output_panel_dir: str = "outputs/panels",
    txt2img_model_path: str = "models/base/comicBabes_v2.safetensors",
    device: str = "cuda",
    lora_path = None,
    lora_scale_base: float = 0.85,
    panel_steps: int = 50,
    layout_name: str | None = "Layout1",
    negative_embedding_path: str | None = None,
    max_render_width: int = 1024,
    max_render_height: int = 1024,
    controlnet_config: dict | None = None,
    style_name: str | None = None,
    guidance_scale: float = 9.0,
    negative_prompt_extra: str | None = None,
    force_regenerate_schema: bool = True,
):
    print("[STEP 1/2] Generate story schema...")
    print(f"[SCHEMA] User prompt: {prompt}")
    # Nếu force_regenerate_schema=True, xóa schema cũ trước
    if force_regenerate_schema and Path(base_schema_path).exists():
        print(f"[SCHEMA] Force regenerate: deleted old schema at {base_schema_path}")
        Path(base_schema_path).unlink()
    
    try:
        generate_schema(prompt, output_path=base_schema_path)
    except RuntimeError as err:
        if Path(base_schema_path).exists() and "quota" in str(err).lower():
            print("[SCHEMA] Quota hit, reuse existing schema on disk.")
            print(f"[SCHEMA] ⚠️  WARNING: Using old schema, may not match new prompt!")
            print(f"[SCHEMA] Current prompt: {prompt}")
        else:
            raise

    print("[STEP 2/2] Generate panels with unified workflow...")

    with open(base_schema_path, "r", encoding="utf-8") as schema_file:
        schema_data = json.load(schema_file)
    num_panels = len(schema_data.get("panels", []))
    resolved_layout = select_layout_name(
        num_panels,
        preferred=layout_name,
        seed_text=prompt,
    )
    print(f"[LAYOUT] Selected layout: {resolved_layout}")

    panel_sizes = generate_panels_unified(
        schema_path=base_schema_path,
        output_panel_dir=output_panel_dir,
        base_model_path=txt2img_model_path,
        device=device,
        base="SDv1.5",
        lora_path=lora_path,
        lora_scale=lora_scale_base,
        panel_steps=panel_steps,
        guidance_scale=guidance_scale,
        layout_name=resolved_layout,
        negative_embedding_path=negative_embedding_path,
        max_render_width=max_render_width,
        max_render_height=max_render_height,
        controlnet_config=controlnet_config,
        style_name=style_name,
        negative_prompt_extra=negative_prompt_extra,
    )

    panel_sizes_path = str(Path(base_schema_path).parent / "panel_sizes.json")
    with open(panel_sizes_path, "w", encoding="utf-8") as f:
        json.dump(panel_sizes, f, indent=2)
    print(f"[STEP 2/2] ✓ Panel sizes saved: {panel_sizes_path}")

    return resolved_layout
