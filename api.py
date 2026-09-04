import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import os
import glob
from pathlib import Path
from pydantic import BaseModel

from studio_graph.graph import create_studio_graph
from config import CONFIG

CANCEL_REQUESTED = False

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/data", StaticFiles(directory="data"), name="data")

def setup_paths(series_id: str, chapter_id: str):
    if not series_id: series_id = "default"
    if not chapter_id: chapter_id = "chapter_1"
    
    base_dir = f"data/series/{series_id}/{chapter_id}"
    out_dir = f"outputs/series/{series_id}/{chapter_id}"
    
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(f"{out_dir}/panels", exist_ok=True)
    os.makedirs(f"{out_dir}/characters", exist_ok=True)
    
    CONFIG.paths.schema = f"{base_dir}/story.json"
    CONFIG.paths.panel_dir = f"{out_dir}/panels"
    CONFIG.paths.character_dir = f"{out_dir}/characters"
    CONFIG.paths.output_page = f"comic_page.png"
    return base_dir, out_dir

# -----------------
# SERIES MANAGEMENT
# -----------------
@app.get("/api/series")
async def get_series_list():
    series_dir = Path("data/series")
    if not series_dir.exists():
        return {"series": []}
    
    series_list = []
    for s_path in series_dir.iterdir():
        if s_path.is_dir():
            chapters = []
            for c_path in s_path.iterdir():
                if c_path.is_dir():
                    chapters.append(c_path.name)
            series_list.append({"id": s_path.name, "name": s_path.name, "chapters": sorted(chapters)})
            
    return {"series": series_list}

class CreateSeriesRequest(BaseModel):
    series_id: str

@app.post("/api/series/create")
async def create_series(req: CreateSeriesRequest):
    os.makedirs(f"data/series/{req.series_id}/chapter_1", exist_ok=True)
    os.makedirs(f"outputs/series/{req.series_id}/chapter_1/panels", exist_ok=True)
    return {"status": "success", "series_id": req.series_id}

class CreateChapterRequest(BaseModel):
    series_id: str
    chapter_id: str

@app.post("/api/chapter/create")
async def create_chapter(req: CreateChapterRequest):
    os.makedirs(f"data/series/{req.series_id}/{req.chapter_id}", exist_ok=True)
    os.makedirs(f"outputs/series/{req.series_id}/{req.chapter_id}/panels", exist_ok=True)
    return {"status": "success", "chapter_id": req.chapter_id}

# -----------------
# EXPLORER API
# -----------------
@app.get("/api/explorer")
async def get_explorer(series_id: str, chapter_id: str):
    out_dir = Path(f"outputs/series/{series_id}/{chapter_id}")
    if not out_dir.exists():
        return {"pages": [], "panels": []}
    
    pages = []
    panels = []
    
    for file in out_dir.glob("*.png"):
        pages.append(file.name)
        
    panels_dir = out_dir / "panels"
    if panels_dir.exists():
        for file in panels_dir.glob("*.png"):
            panels.append(file.name)
            
    # Sort files naturally
    import re
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]
    
    pages.sort(key=natural_sort_key)
    panels.sort(key=natural_sort_key)
    
    return {"pages": pages, "panels": panels}

class DeleteFileRequest(BaseModel):
    series_id: str
    chapter_id: str
    filename: str
    is_panel: bool = False

@app.post("/api/explorer/delete")
async def delete_file(req: DeleteFileRequest):
    base = Path(f"outputs/series/{req.series_id}/{req.chapter_id}")
    if req.is_panel:
        base = base / "panels"
    file_path = base / req.filename
    if file_path.exists() and file_path.suffix == '.png':
        os.remove(file_path)
        return {"status": "success"}
    return {"status": "error", "message": "File not found"}

# -----------------
# STUDIO API
# -----------------
class GenerateRequest(BaseModel):
    prompt: str
    series_id: str
    chapter_id: str

@app.post("/api/generate")
async def generate_comic(req: GenerateRequest):
    global CANCEL_REQUESTED
    CANCEL_REQUESTED = False
    base_dir, out_dir = setup_paths(req.series_id, req.chapter_id)
    
    async def event_generator():
        yield "data: [STUDIO] Khởi tạo hệ thống...\n\n"
        await asyncio.sleep(0.1)
        
        try:
            graph = create_studio_graph()
            config = {"configurable": {"thread_id": f"chapter_{req.series_id}_{req.chapter_id}", "series_id": req.series_id}}
            
            initial_state = {
                "user_prompt": req.prompt,
                "chapter_number": 1,
                "current_page_idx": 0,
                "page_scripts": [],
                "retrieved_lore": "",
                "unresolved_hooks": "",
                "chapter_outline": "",
                "current_schema": None,
                "previous_schema": None,
                "validation_errors": [],
                "vision_feedback": "",
                "human_feedback": "",
                "next_step": ""
            }
            
            for event in graph.stream(initial_state, config):
                if CANCEL_REQUESTED:
                    yield "data: [CANCELLED] Quá trình tạo đã bị dừng.\n\n"
                    break
                for k, v in event.items():
                    yield f"data: ✅ Hoàn thành Node: {k}\n\n"
                    await asyncio.sleep(0.1)
                    
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: ❌ Lỗi: {str(e)}\n\n"
            yield "data: [DONE]\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/schema")
async def get_schema(series_id: str = "default", chapter_id: str = "chapter_1", page_name: str = "comic_page_1.png"):
    _, out_dir = setup_paths(series_id, chapter_id)
    idx = page_name.replace("comic_page_", "").replace(".png", "")
    schema_path = f"{out_dir}/story_{idx}.json"
    layout_path = f"{out_dir}/page_layout_{idx}.json"
    
    if not os.path.exists(schema_path):
        return {"panels": [], "layout": []}
        
    with open(schema_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if os.path.exists(layout_path):
        with open(layout_path, "r", encoding="utf-8") as f:
            data["layout"] = json.load(f)
    else:
        data["layout"] = []
        
    return data

class UpdateBubblesRequest(BaseModel):
    panels: list
    series_id: str
    chapter_id: str
    page_name: str = "comic_page_1.png"

@app.post("/api/update_bubbles")
async def update_bubbles(req: UpdateBubblesRequest):
    _, out_dir = setup_paths(req.series_id, req.chapter_id)
    idx = req.page_name.replace("comic_page_", "").replace(".png", "")
    schema_path = f"{out_dir}/story_{idx}.json"
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        
    schema["panels"] = req.panels
    
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    from page.builder import build_comic_page
    from page.layouts import select_layout_name
    
    resolved_layout = select_layout_name(len(schema["panels"]), preferred=CONFIG.story.layout_name)
    build_comic_page(
        panels_dir=CONFIG.paths.panel_dir,
        output_path=f"{out_dir}/{req.page_name}",
        schema_path=schema_path,
        inject_bubbles=True,
        use_adaptive_layout=True,
        layout_name=resolved_layout,
    )
    
    return {"status": "success"}

class RegeneratePanelRequest(BaseModel):
    panel_id: str
    new_prompt: str
    series_id: str
    chapter_id: str
    page_name: str = "comic_page_1.png"
    
@app.post("/api/regenerate_panel")
async def regenerate_panel(req: RegeneratePanelRequest):
    _, out_dir = setup_paths(req.series_id, req.chapter_id)
    idx = req.page_name.replace("comic_page_", "").replace(".png", "")
    schema_path = f"{out_dir}/story_{idx}.json"
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
        
    for p in schema["panels"]:
        if p["id"] == req.panel_id:
            p["panel_prompt_en"] = req.new_prompt
            break
            
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    from panel_engine.unified_pipeline import generate_panels_unified
    from page.layouts import select_layout_name
    from page.builder import build_comic_page
    
    resolved_layout = select_layout_name(len(schema["panels"]), preferred=CONFIG.story.layout_name)
    
    generate_panels_unified(
        schema_path=schema_path,
        output_panel_dir=CONFIG.paths.panel_dir,
        base_model_path=CONFIG.models.base_model,
        device=CONFIG.models.device,
        base="SDv1.5",
        lora_path=CONFIG.models.lora_path,
        lora_scale=CONFIG.models.lora_scale,
        panel_steps=20,
        guidance_scale=CONFIG.models.guidance_scale,
        layout_name=resolved_layout,
        max_render_width=CONFIG.quality.max_render_width,
        max_render_height=CONFIG.quality.max_render_height,
        negative_prompt_extra=CONFIG.models.negative_prompt_extra,
        target_panel_ids=[req.panel_id]
    )
    
    build_comic_page(
        panels_dir=CONFIG.paths.panel_dir,
        output_path=f"{out_dir}/{req.page_name}",
        schema_path=schema_path,
        inject_bubbles=True,
        use_adaptive_layout=True,
        layout_name=resolved_layout,
    )
    
    return {"status": "success"}

# -----------------
# CONFIG & DATABASE
# -----------------
def scan_loras():
    loras = []
    # Quét trong models/loras
    search_path = os.path.join("models", "loras", "*.safetensors")
    for file in glob.glob(search_path):
        loras.append(file.replace("\\", "/"))
    return loras



@app.get("/api/database/characters")
async def get_characters(series_id: str):
    from database.sqlite_db import get_all_characters
    chars = get_all_characters(series_id)
    return {"characters": chars}

class CreateCharacterRequest(BaseModel):
    series_id: str
    id: str
    name: str
    age: str
    personality: str
    base_prompt_en: str
    seed: int
    inventory: list

@app.post("/api/database/characters/create")
async def create_character(req: CreateCharacterRequest):
    from database.sqlite_db import upsert_character
    upsert_character(req.series_id, req.dict())
    return {"status": "success"}

@app.delete("/api/database/characters/{char_id}")
async def delete_character(char_id: str, series_id: str):
    from database.sqlite_db import delete_character as db_delete_character
    db_delete_character(series_id, char_id)
    return {"status": "success"}


@app.post("/api/cancel")
async def cancel_generation():
    global CANCEL_REQUESTED
    CANCEL_REQUESTED = True
    return {"status": "success", "message": "Đã gửi yêu cầu dừng."}

@app.get("/api/config")
async def get_config():
    return CONFIG.to_dict()

@app.post("/api/config")
async def update_config(request: Request):
    data = await request.json()
    CONFIG.from_dict(data)
    return {"status": "success", "config": CONFIG.to_dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

