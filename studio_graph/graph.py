import json
import time
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import StudioState
from .agents import run_storyboarder, run_validator

from panel_engine.unified_pipeline import generate_panels_unified
from page.layouts import select_layout_name
from page.builder import build_comic_page
from config import CONFIG
from langchain_core.runnables import RunnableConfig

def run_renderer(state: StudioState, config: RunnableConfig) -> StudioState:
    print("\n[RENDERER] Booting Stable Diffusion...")
    schema = state["current_schema"]
    
    # Use timestamp to avoid overwriting
    timestamp = int(time.time())
    
    out_dir = Path(CONFIG.paths.panel_dir).parent
    schema_path = out_dir / f"story_{timestamp}.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    num_panels = len(schema.get("panels", []))
    
    # Determine layout based on user selection
    layoutStyle = state.get("layoutStyle", "auto")
    mangaLayout = state.get("mangaLayout", "style1")
    
    if layoutStyle == "manga":
        # Map style1 -> Layout1, style2 -> Layout2, style3 -> Layout3
        preferred = mangaLayout.replace("style", "Layout")
    else:
        preferred = None
        
    resolved_layout = select_layout_name(num_panels, preferred=preferred)
    print(f"[RENDERER] Render {num_panels} panels with {resolved_layout}...")
    
    lora_name = state.get("lora", "ghibli")
    # Lora selection mapping
    lora_map = {
        "ghibli": "models/loras/ghibli_style_offset.safetensors",
        "mjmanga": "models/loras/MjManga.safetensors",
        "ukiyo": "models/loras/Ukiyo-e.safetensors",
        "vintage": "models/loras/1950sVintageArt.safetensors",
        "cartoony": "models/loras/cartoony.safetensors"
    }
    lora_path = lora_map.get(lora_name, lora_map["ghibli"])

    # Base negative prompt + user input
    base_negative = CONFIG.models.negative_prompt_extra
    user_negative = state.get("negativePrompt", "").strip()
    if user_negative:
        base_negative += ", " + user_negative
        
    seed = state.get("seed", "").strip()
    if not seed or not seed.isdigit():
        import random
        seed_val = random.randint(1000, 999999)
    else:
        seed_val = int(seed)

    # RENDER PANELS
    panel_sizes = generate_panels_unified(
        schema_path=str(schema_path),
        output_panel_dir=CONFIG.paths.panel_dir,
        base_model_path=CONFIG.models.base_model,
        device=CONFIG.models.device,
        base="SDv1.5",
        lora_path=lora_path,
        lora_scale=CONFIG.models.lora_scale,
        panel_steps=state.get("steps", 20),
        guidance_scale=state.get("guidance", 7.5),
        layout_name=resolved_layout,
        max_render_width=CONFIG.quality.max_render_width,
        max_render_height=CONFIG.quality.max_render_height,
        negative_prompt_extra=base_negative,
        series_id="short_comic",
        seed=seed_val
    )
    
    panel_sizes_path = schema_path.parent / "panel_sizes.json"
    with open(panel_sizes_path, "w", encoding="utf-8") as f:
        json.dump(panel_sizes, f, indent=2)
        
    # BUILD PAGE
    print("[RENDERER] Building Page and injecting bubbles...")
    output_path = str(out_dir / f"comic_page_{timestamp}.png")
    
    build_comic_page(
        panels_dir=CONFIG.paths.panel_dir,
        output_path=output_path,
        schema_path=str(schema_path),
        inject_bubbles=True,
        use_adaptive_layout=True,
        layout_name=resolved_layout,
    )
    print(f"[RENDERER] ✓ Completed page! Saved at {output_path}")
    
    # Save output path in state so we can return it to frontend
    state["next_step"] = "end"
    state["output_page"] = output_path
    
    return state

def create_studio_graph() -> StateGraph:
    workflow = StateGraph(StudioState)
    
    workflow.add_node("storyboarder", run_storyboarder)
    workflow.add_node("validator", run_validator)
    workflow.add_node("renderer", run_renderer)
    
    workflow.set_entry_point("storyboarder")
    
    workflow.add_edge("storyboarder", "validator")
    
    def validator_router(state: StudioState):
        return state.get("next_step", "storyboarder")
        
    workflow.add_conditional_edges(
        "validator",
        validator_router,
        {
            "storyboarder": "storyboarder",
            "renderer": "renderer"
        }
    )
    
    workflow.add_edge("renderer", END)
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app
