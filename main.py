from pathlib import Path
from config import CONFIG
from pipeline.comic_pipeline import generate_comic
from page.builder import build_comic_page



def cleanup_old_files(character_dir: str, panel_dir: str, background_dir: str | None = None) -> None:
    character_path = Path(character_dir)
    panel_path = Path(panel_dir)
    
    if character_path.exists():
        character_files = list(character_path.glob("*.png"))
        if character_files:
            print(f"[CLEANUP] Xóa {len(character_files)} character files...")
            for file in character_files:
                file.unlink()
            print(f"✓ Đã xóa {len(character_files)} character files")
    
    if panel_path.exists():
        panel_files = list(panel_path.glob("*.png"))
        if panel_files:
            print(f"[CLEANUP] Xóa {len(panel_files)} panel files...")
            for file in panel_files:
                file.unlink()
            print(f"✓ Đã xóa {len(panel_files)} panel files")
    
    if background_dir:
        bg_path = Path(background_dir)
        if bg_path.exists():
            bg_files = list(bg_path.glob("background_*.png"))
            bg_meta_files = list(bg_path.glob("background_*.json"))
            if bg_files or bg_meta_files:
                print(f"[CLEANUP] Xóa {len(bg_files)} background cache files...")
                for file in bg_files + bg_meta_files:
                    file.unlink()
                print(f"✓ Đã xóa {len(bg_files)} background cache files")
    
    for meta_file in [
        panel_path / "panel_sizes.json",
        character_path / "panel_sizes.json",
    ]:
        if meta_file.exists():
            meta_file.unlink()
            print(f"✓ Đã xóa {meta_file.name}")
    

def main():
    settings = CONFIG
    paths = settings.paths
    quality = settings.quality
    models = settings.models
    story = settings.story
    
    quality_mode_norm = quality.mode.lower()
    quality_multiplier = quality.step_multipliers.get(quality_mode_norm, 1.0)
    min_steps = quality.min_diffusion_steps
    max_steps = quality.max_diffusion_steps
    panel_steps_cfg = int(round(quality.panel_steps * quality_multiplier))
    panel_steps_cfg = max(min_steps, panel_steps_cfg)
    panel_steps_cfg = min(max_steps, panel_steps_cfg)
    bubble_steps_cfg = max(20, int(round(quality.bubble_steps * min(quality_multiplier, 1.1))))
    
    print("=" * 60)
    print("COMIC BOOK GENERATOR")
    print("=" * 60)
    print(f"Prompt: {story.prompt}")
    print(f"Quality mode: {quality.mode} (×{quality_multiplier:.2f})")
    print(f"Steps → panel:{panel_steps_cfg} bubble:{bubble_steps_cfg}")
    print(f"LoRA: {models.lora_path} (scale={models.lora_scale})")
    print(f"Guidance scale: {models.guidance_scale}\n")
    
    if story.cleanup_before_run:
        print("[0/2] Cleaning up old files...")
        cleanup_old_files(
            paths.character_dir, 
            paths.panel_dir, 
            paths.background_cache_dir
        )
        print("✓ Done\n")
    
    print("[1/2] Generating comic panels...")
    controlnet_config = None
    selected_layout = generate_comic(
        prompt=story.prompt,
        base_schema_path=paths.schema,
        output_panel_dir=paths.panel_dir,
        txt2img_model_path=models.base_model,
        device=models.device,
        lora_path=models.lora_path,
        lora_scale_base=models.lora_scale,
        panel_steps=panel_steps_cfg,
        layout_name=story.layout_name,
        negative_embedding_path=models.negative_embedding,
        max_render_width=quality.max_render_width,
        max_render_height=quality.max_render_height,
        controlnet_config=controlnet_config,
        style_name=settings.style.preset,
        guidance_scale=models.guidance_scale,
        negative_prompt_extra=models.negative_prompt_extra,
        force_regenerate_schema=story.force_regenerate_schema,
    )
    print("✓ Done\n")
    
    print("[2/2] Building page...")
    panel_files = sorted(Path(paths.panel_dir).glob("panel_*.png"))
    if not panel_files:
        panel_files = sorted(Path(paths.panel_dir).glob("*.png"))
    
    if not panel_files:
        raise ValueError(f"Không tìm thấy panels trong {paths.panel_dir}")
    
    layout_for_page = selected_layout or story.layout_name
    page = build_comic_page(
        panels_dir=paths.panel_dir, 
        output_path=paths.output_page,
        schema_path=paths.schema,
        inject_bubbles=True,
        use_adaptive_layout=True,
        layout_name=layout_for_page,
    )
    print("✓ Done\n")
    print(f"✓ Saved: {paths.output_page} ({page.size[0]}x{page.size[1]}px)")
    print("=" * 60)
    
    return page

if __name__ == "__main__":
    main()

