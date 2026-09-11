import json
import time
from uuid import uuid4
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import StudioState
from .agents import run_story_planner, run_dialogue_writer, run_storyboarder, run_validator, run_vision_qa

from panel_engine.unified_pipeline import generate_panels_unified
from page.layouts import select_layout_name
from page.builder import build_comic_page
from config import CONFIG, resolve_lora_selection
from langchain_core.runnables import RunnableConfig

def run_renderer(state: StudioState, config: RunnableConfig) -> StudioState:
    print("\n[RENDERER] Booting Stable Diffusion...")
    schema = state["current_schema"]
    
    # Use timestamp to avoid overwriting
    timestamp = uuid4().hex
    
    out_dir = Path(CONFIG.paths.panel_dir).parent
    job_dir = out_dir / "jobs" / timestamp
    panel_dir = job_dir / "panels"
    schema_path = job_dir / "story.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    num_panels = sum(
        len(page.get("panels", [])) for page in schema.get("pages", [])
    ) or len(schema.get("panels", []))
    
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
    
    lora_path = resolve_lora_selection(state.get("lora"))

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

    from utils.parser import load_comic_from_json
    from page.layouts import compute_layout_placements

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)
    comic = load_comic_from_json(schema_data)
    
    # Group panels by page_number
    pages_dict = {}
    for p in comic.panels:
        pages_dict.setdefault(p.page_number, []).append(p)
        
    if not pages_dict:
        # Fallback if no panels
        print("[WARN] No pages found in comic schema.")
        pages_dict[1] = []

    # PRE-CALCULATE PANEL SIZES
    panel_sizes_metadata = {}
    for page_num in sorted(pages_dict.keys()):
        panels_in_page = pages_dict[page_num]
        expected_panel_ids = [p.id for p in panels_in_page]
        page_layout = select_layout_name(len(expected_panel_ids), preferred=preferred, seed_text=f"{timestamp}_{page_num}")
        placements = compute_layout_placements(page_layout, len(expected_panel_ids))
        for placement, pid in zip(placements, expected_panel_ids):
            panel_sizes_metadata[pid] = {
                "width": placement["width"],
                "height": placement["height"]
            }

    panel_sizes_path = schema_path.parent / "panel_sizes.json"
    with open(panel_sizes_path, "w", encoding="utf-8") as f:
        json.dump(panel_sizes_metadata, f, indent=2)

    # Render every panel with the local Stable Diffusion pipeline.
    generate_panels_unified(
        schema_path=str(schema_path),
        output_panel_dir=str(panel_dir),
        base_model_path=CONFIG.models.base_model,
        device=CONFIG.models.device,
        base="SDv1.5",
        lora_path=lora_path,
        lora_scale=CONFIG.models.lora_scale,
        panel_steps=state.get("steps", 20),
        guidance_scale=state.get("guidance", 7.5),
        layout_name=None,
        max_render_width=CONFIG.quality.max_render_width,
        max_render_height=CONFIG.quality.max_render_height,
        negative_prompt_extra=base_negative,
        series_id=f"short_comic_{timestamp}",
        seed=seed_val,
        style_name=CONFIG.style.preset,
    )
        
    # BUILD PAGES
    print("[RENDERER] Building Pages and injecting bubbles...")
    
    output_paths = []
    
    for page_num in sorted(pages_dict.keys()):
        panels_in_page = pages_dict[page_num]
        expected_panel_ids = [p.id for p in panels_in_page]
        
        page_output_path = str(out_dir / f"comic_page_{timestamp}_{page_num}.png")
        
        # Select layout based on the number of panels in this specific page, randomized by page_num
        page_layout = select_layout_name(len(expected_panel_ids), preferred=preferred, seed_text=f"{timestamp}_{page_num}")
        
        build_comic_page(
            panels_dir=str(panel_dir),
            output_path=page_output_path,
            expected_panel_ids=expected_panel_ids,
            schema_path=str(schema_path),
            inject_bubbles=True,
            use_adaptive_layout=True,
            layout_name=page_layout,
        )
        print(f"[RENDERER] OK Completed page {page_num}! Saved at {page_output_path}")
        output_paths.append(page_output_path)
    
    # Save output paths in state so we can return them to frontend
    state["next_step"] = "end"
    state["output_pages"] = output_paths
    
    return state

def create_studio_graph() -> StateGraph:
    workflow = StateGraph(StudioState)
    
    workflow.add_node("story_planner", run_story_planner)
    workflow.add_node("dialogue_writer", run_dialogue_writer)
    workflow.add_node("storyboarder", run_storyboarder)
    workflow.add_node("validator", run_validator)
    workflow.add_node("renderer", run_renderer)
    workflow.add_node("vision_qa", run_vision_qa)
    
    workflow.set_entry_point("story_planner")
    
    workflow.add_edge("story_planner", "dialogue_writer")
    workflow.add_edge("dialogue_writer", "storyboarder")
    workflow.add_edge("storyboarder", "validator")
    
    def validator_router(state: StudioState):
        return state.get("next_step", "storyboarder")
        
    workflow.add_conditional_edges(
        "validator",
        validator_router,
        {
            "story_planner": "story_planner",
            "dialogue_writer": "dialogue_writer",
            "storyboarder": "storyboarder",
            "renderer": "renderer",
            "failed": END,
        }
    )
    
    workflow.add_edge("renderer", "vision_qa")
    workflow.add_conditional_edges(
        "vision_qa",
        lambda state: state.get("next_step", "failed"),
        {"end": END, "failed": END, "renderer": "renderer", "storyboarder": "storyboarder", "dialogue_writer": "dialogue_writer"},
    )
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app
