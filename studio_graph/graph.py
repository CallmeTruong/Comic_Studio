import json
from pathlib import Path
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import StudioState
from .agents import run_director, run_writer, run_storyboarder, run_validator

# Import the actual renderer functions
from panel_engine.unified_pipeline import generate_panels_unified
from page.layouts import select_layout_name
from page.builder import build_comic_page
from config import CONFIG
from database.scene_state import save_scene_state, get_scene_state
from database.vector_db import add_story_event

def run_renderer(state: StudioState) -> StudioState:
    print("\n[RENDERER] Booting Stable Diffusion...")
    schema = state["current_schema"]
    schema_path = Path("data/base/schema/story.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    num_panels = len(schema.get("panels", []))
    resolved_layout = select_layout_name(num_panels, preferred=CONFIG.story.layout_name)
    print(f"[RENDERER] Render {num_panels} panels with {resolved_layout}...")
    
    # RENDER PANELS
    panel_sizes = generate_panels_unified(
        schema_path=str(schema_path),
        output_panel_dir=CONFIG.paths.panel_dir,
        base_model_path=CONFIG.models.base_model,
        device=CONFIG.models.device,
        base="SDv1.5",
        lora_path=CONFIG.models.lora_path,
        lora_scale=CONFIG.models.lora_scale,
        panel_steps=20, # Fast mode for demo
        guidance_scale=CONFIG.models.guidance_scale,
        layout_name=resolved_layout,
        max_render_width=CONFIG.quality.max_render_width,
        max_render_height=CONFIG.quality.max_render_height,
        negative_prompt_extra=CONFIG.models.negative_prompt_extra,
    )
    
    panel_sizes_path = schema_path.parent / "panel_sizes.json"
    with open(panel_sizes_path, "w", encoding="utf-8") as f:
        json.dump(panel_sizes, f, indent=2)
        
    # BUILD PAGE
    print("[RENDERER] Building Page and injecting bubbles...")
    page_idx = state["current_page_idx"]
    output_path = f"outputs/comic_page_{page_idx+1}.png"
    
    build_comic_page(
        panels_dir=CONFIG.paths.panel_dir,
        output_path=output_path,
        schema_path=str(schema_path),
        inject_bubbles=True,
        use_adaptive_layout=True,
        layout_name=resolved_layout,
    )
    print(f"[RENDERER] ✓ Completed page {page_idx+1}! Saved at {output_path}")
    
    # UPDATE SCENE STATE (Mocking for now based on schema)
    scene = get_scene_state()
    scene["last_page_rendered"] = page_idx + 1
    if schema.get("panels"):
        last_panel = schema["panels"][-1]
        scene["ongoing_action"] = last_panel.get("action_en", "Continuing...")
    save_scene_state(scene)
    
    # SAVE TO STORY MEMORY
    summary = f"Chapter {state.get('chapter_number', 1)} Page {page_idx+1}: {scene['ongoing_action']}"
    add_story_event(state.get('chapter_number', 1), page_idx+1, summary)
    
    # Next Page loop
    state["current_page_idx"] += 1
    state["next_step"] = "storyboarder"
    return state

def create_studio_graph():
    workflow = StateGraph(StudioState)
    
    # Nodes
    workflow.add_node("director", run_director)
    workflow.add_node("writer", run_writer)
    workflow.add_node("storyboarder", run_storyboarder)
    workflow.add_node("validator", run_validator)
    workflow.add_node("renderer", run_renderer)
    
    # Edges
    workflow.set_entry_point("director")
    workflow.add_edge("director", "writer")
    
    # Human in the loop goes here usually, but we go straight for demo
    workflow.add_edge("writer", "storyboarder")
    
    # Validator checks schema
    workflow.add_edge("storyboarder", "validator")
    
    def validator_router(state: StudioState):
        return state["next_step"] # "renderer" or "storyboarder"
        
    workflow.add_conditional_edges("validator", validator_router, {
        "renderer": "renderer",
        "storyboarder": "storyboarder"
    })
    
    # Renderer loops back to storyboarder for next page
    def renderer_router(state: StudioState):
        if state["current_page_idx"] >= len(state.get("page_scripts", [])):
            return "end"
        return "storyboarder"
        
    workflow.add_conditional_edges("renderer", renderer_router, {
        "end": END,
        "storyboarder": "storyboarder"
    })
    
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
