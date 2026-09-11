import asyncio
import json
import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
from panel_engine.unified_pipeline import generate_panels_unified
from page.builder import build_comic_page
from page.layouts import select_layout_name
from utils.parser import load_comic_from_json

from studio_graph.graph import create_studio_graph
from config import CONFIG, resolve_lora_selection
from core.model_registry import model_catalog
import uvicorn

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output dirs
output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)
panels_dir = output_dir / "panels"
panels_dir.mkdir(parents=True, exist_ok=True)

CONFIG.paths.panel_dir = str(panels_dir)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    layoutStyle: str = "auto"
    mangaLayout: str = "style1"
    steps: int = Field(default=80, ge=10, le=180)
    guidance: float = 7.5
    lora: str = "ghibli"
    negativePrompt: str = ""
    seed: str = ""
    pageCount: int = Field(default=1, ge=1, le=8)
    model: str = Field(default="sd15", pattern="^(sd15|sdxl_dreamshaper)$")

class RegeneratePanelRequest(BaseModel):
    pageUrl: str = Field(min_length=1)
    panelId: str = Field(min_length=1, max_length=100)
    panelPrompt: str = Field(min_length=1, max_length=2000)
    dialogues: list[dict] = Field(default_factory=list)
    steps: int = Field(default=20, ge=1, le=180)
    guidance: float = Field(default=7.5, ge=1, le=30)
    lora: str = "ghibli"
    negativePrompt: str = ""
    seed: str = ""
    mode: str = Field(default="panel", pattern="^(panel|dialogue)$")
    model: str = Field(default="sd15", pattern="^(sd15|sdxl_dreamshaper)$")


class SavePageRequest(BaseModel):
    pageUrl: str = Field(min_length=1)
    filename: str = Field(default="comic-page.png", min_length=1, max_length=120)

graph = create_studio_graph()

LORA_DIR = Path("models/loras")

def available_loras() -> list[dict[str, str]]:
    allowed = {".safetensors", ".pt", ".ckpt"}
    if not LORA_DIR.exists():
        return []
    return [{"id": p.name, "label": p.stem.replace("_", " ").replace("-", " ")} for p in sorted(LORA_DIR.iterdir(), key=lambda p: p.name.lower()) if p.is_file() and p.suffix.lower() in allowed]


def resolve_lora_path(selection: str) -> str | None:
    """Resolve both built-in aliases and filenames discovered from models/loras."""
    return resolve_lora_selection(selection, str(LORA_DIR))


@app.get("/api/capabilities")
async def get_capabilities():
    """Expose safe provider status; never return API keys."""
    return {
        "sd15": True,
        "loras": available_loras(),
        "models": model_catalog(),
    }

@app.get("/api/history")
async def get_history():
    files = []
    for f in output_dir.glob("comic_page_*.png"):
        files.append((f.stat().st_mtime, f.name))
    files.sort(reverse=True)
    return {"history": [f"/outputs/{name}" for _, name in files]}


@app.post("/api/save-page")
async def save_page(req: SavePageRequest):
    """Persist a generated page in outputs/saved for later use/download."""
    relative = req.pageUrl.removeprefix("/outputs/").replace("/", os.sep)
    source = (output_dir / relative).resolve()
    if output_dir.resolve() not in source.parents or not source.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    safe_name = Path(req.filename).name
    if Path(safe_name).suffix.lower() != ".png":
        safe_name += ".png"
    saved_dir = (output_dir / "saved").resolve()
    saved_dir.mkdir(parents=True, exist_ok=True)
    destination = saved_dir / safe_name
    source.replace(destination) if source == destination else destination.write_bytes(source.read_bytes())
    return {"url": "/outputs/saved/" + destination.name}


@app.get("/api/page-meta")
async def get_page_meta(url: str = Query(..., min_length=1)):
    """Return panel geometry and editable content for any generated page.

    History entries predate the current SSE metadata event, so the UI can use
    this endpoint to show the same regenerate controls when an old page is
    selected from the sidebar.
    """
    relative = url.removeprefix("/outputs/").replace("/", os.sep)
    page_path = (output_dir / relative).resolve()
    if output_dir.resolve() not in page_path.parents or not page_path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    parts = page_path.stem.split("_")
    if len(parts) < 4 or parts[:2] != ["comic", "page"]:
        raise HTTPException(status_code=400, detail="Unsupported page URL")
    job_id = "_".join(parts[2:-1])
    page_number = int(parts[-1])
    job_dir = output_dir / "jobs" / job_id
    schema_file = job_dir / "story.json"
    layout_file = job_dir / "page_layout.json"
    if not schema_file.exists() or not layout_file.exists():
        raise HTTPException(status_code=404, detail="Page metadata not found")
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    layout = json.loads(layout_file.read_text(encoding="utf-8"))
    panels = next(
        (page.get("panels", []) for page in schema.get("pages", [])
         if int(page.get("page_number", 1)) == page_number),
        [],
    )
    return {
        "url": "/outputs/" + page_path.relative_to(output_dir.resolve()).as_posix(),
        "pageWidth": layout.get("page_width", CONFIG.page.width),
        "pageHeight": layout.get("page_height", CONFIG.page.height),
        "panels": [
            {
                "x": pos[0], "y": pos[1], "width": pos[2], "height": pos[3],
                "id": panel.get("id"),
                "prompt": panel.get("panel_prompt_en", ""),
                "dialogues": panel.get("dialogues", []),
            }
            for pos, panel in zip(layout.get("panels", []), panels)
            if len(pos) == 4
        ],
    }

@app.post("/api/regenerate-panel")
async def regenerate_panel(req: RegeneratePanelRequest):
    """Regenerate one panel and rebuild its containing page."""
    relative = req.pageUrl.removeprefix("/outputs/").replace("/", os.sep)
    page_path = (output_dir / relative).resolve()
    if output_dir.resolve() not in page_path.parents or not page_path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    # Page names are comic_page_<job uuid>_<page number>.png.
    parts = page_path.stem.split("_")
    if len(parts) < 4 or parts[0:2] != ["comic", "page"]:
        raise HTTPException(status_code=400, detail="Unsupported page URL")
    job_id = "_".join(parts[2:-1])
    page_number = int(parts[-1])
    job_dir = output_dir / "jobs" / job_id
    schema_path = job_dir / "story.json"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="Generation job not found")

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    comic = load_comic_from_json(schema)
    panel = next((item for item in comic.panels if item.id == req.panelId), None)
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel not found")
    panel.panel_prompt_en = req.panelPrompt
    panel.dialogues = req.dialogues
    for page in schema.get("pages", []):
        for item in page.get("panels", []):
            if item.get("id") == req.panelId:
                item["panel_prompt_en"] = req.panelPrompt
                item["dialogues"] = req.dialogues
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    page_panels = [item for item in comic.panels if item.page_number == page_number]
    panel_dir = job_dir / "panels"
    seed = int(req.seed) if req.seed.isdigit() else None
    # Dialogue-only edits should preserve the rendered panel and only rebuild
    # the page compositor. This avoids an unnecessary diffusion run and keeps
    # bubble changes independent from image prompt changes.
    if req.mode == "panel":
        generate_panels_unified(
            schema_path=str(schema_path), output_panel_dir=str(panel_dir),
            base_model_path=CONFIG.models.base_model, device=CONFIG.models.device,
            base="SDv1.5", lora_path=resolve_lora_path(req.lora),
            lora_scale=CONFIG.models.lora_scale, panel_steps=req.steps,
            guidance_scale=req.guidance, max_render_width=CONFIG.quality.max_render_width,
            max_render_height=CONFIG.quality.max_render_height,
            negative_prompt_extra=req.negativePrompt, target_panel_ids=[req.panelId],
            series_id=f"regenerate_{job_id}", seed=seed, style_name=CONFIG.style.preset,
            model_id=req.model,
        )
    expected_ids = [item.id for item in page_panels]
    layout = select_layout_name(len(expected_ids))
    build_comic_page(str(panel_dir), str(page_path), expected_ids, str(schema_path),
                     inject_bubbles=True, use_adaptive_layout=True, layout_name=layout)
    # page_path is resolved above while output_dir is configured as a relative
    # path.  Resolve both before relative_to; otherwise regeneration succeeds
    # but the endpoint raises a 500 while constructing the response URL.
    return {"url": "/outputs/" + page_path.relative_to(output_dir.resolve()).as_posix(),
            "panelId": req.panelId, "mode": req.mode}

@app.post("/api/generate")
async def generate_short_comic(req: GenerateRequest):
    
    async def event_generator():
        yield "data: [START] Starting comic generation...\n\n"
        await asyncio.sleep(0.1)
        
        config = {"configurable": {"thread_id": f"short_comic_{uuid.uuid4().hex}"}}
        
        try:
            # We can stream the events from LangGraph
            initial_state = {
                "user_prompt": req.prompt, 
                "current_schema": {}, 
                "story_plan": {},
                "dialogue_plan": {},
                "vision_qa": {},
                "vision_retry_count": 0,
                # Keep the production default strict, but allow short Colab
                # smoke tests to opt into a much smaller retry budget.
                "max_vision_retries": max(0, int(os.getenv("MAX_VISION_RETRIES", "10"))),
                "validation_errors": [], 
                "next_step": "",
                "layoutStyle": req.layoutStyle,
                "mangaLayout": req.mangaLayout,
                "steps": req.steps,
                "guidance": req.guidance,
                "lora": req.lora,
                "negativePrompt": req.negativePrompt,
                "seed": req.seed,
                "pageCount": req.pageCount,
                "model": req.model,
                "retry_count": 0,
                "max_retries": CONFIG.story.max_retries,
                "generation_error": "",
                "image_provider": "sd15",
            }
            for event in graph.stream(initial_state, config):
                for key, value in event.items():
                    if key == "story_planner":
                        yield "data: [AGENT] Planning the story beats and punchline...\n\n"
                    elif key == "dialogue_writer":
                        yield "data: [AGENT] Writing and checking natural dialogue...\n\n"
                    elif key == "storyboarder":
                        yield "data: [AGENT] Building the detailed storyboard...\n\n"
                    elif key == "validator":
                        errs = value.get("validation_errors", [])
                        generation_error = value.get("generation_error", "")
                        if generation_error:
                            yield f"data: [ERROR] {generation_error}\n\n"
                        elif errs:
                            yield f"data: [AGENT] Art Director requested changes: {errs[0][:100]}...\n\n"
                        else:
                            yield "data: [AGENT] Storyboard approved! Starting rendering...\n\n"
                    elif key == "renderer":
                        yield "data: [RENDERER] Rendering and assembling the comic...\n\n"
                        # When renderer is done, it adds 'output_pages' to state
                        output_pages = value.get("output_pages", [])
                        if output_pages:
                            for page_path in output_pages:
                                # Convert local path to URL
                                url_path = Path(page_path).relative_to("outputs").as_posix()
                                yield f"data: [RESULT] /outputs/{url_path}\n\n"
                                page_file = Path(page_path)
                                job_dir = output_dir / "jobs" / page_file.stem.split("_")[2]
                                schema_file = job_dir / "story.json"
                                if schema_file.exists():
                                    schema = json.loads(schema_file.read_text(encoding="utf-8"))
                                    page_no = int(page_file.stem.split("_")[-1])
                                    panels = next((p.get("panels", []) for p in schema.get("pages", []) if p.get("page_number") == page_no), [])
                                    layout_file = job_dir / "page_layout.json"
                                    layout = json.loads(layout_file.read_text(encoding="utf-8")) if layout_file.exists() else {"page_width": CONFIG.page.width, "page_height": CONFIG.page.height, "panels": []}
                                    meta = {"url": f"/outputs/{url_path}", "pageWidth": layout["page_width"], "pageHeight": layout["page_height"], "panels": []}
                                    for pos, panel in zip(layout.get("panels", []), panels):
                                        if len(pos) != 4:
                                            continue
                                        x, y, width, height = pos
                                        meta["panels"].append({"x": x, "y": y, "width": width, "height": height, "id": panel.get("id"), "prompt": panel.get("panel_prompt_en", ""), "dialogues": panel.get("dialogues", [])})
                                    yield "data: [META] " + json.dumps(meta, ensure_ascii=False) + "\n\n"
                    elif key == "vision_qa":
                        qa = value.get("vision_qa", {})
                        status = "Passed" if qa.get("passed") else "Rejected"
                        attempt = int(value.get("vision_retry_count", 0)) + 1
                        corrections = "; ".join(
                            str(item.get("correction") or item.get("reason", ""))
                            for item in qa.get("issues", [])[:3]
                        )
                        detail = qa.get("summary", "")
                        if corrections:
                            detail += f" Corrections: {corrections}"
                        yield f"data: [VISION QA] Attempt {attempt}/10 — {status} ({qa.get('score', 0)}/10): {detail}\n\n"
        except Exception as e:
            yield f"data: [ERROR] System error: {e}\n\n"
            
        yield "data: [DONE]\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
