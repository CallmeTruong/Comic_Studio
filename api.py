import asyncio
import json
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from studio_graph.graph import create_studio_graph
from config import CONFIG
import uvicorn

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
    prompt: str
    layoutStyle: str = "auto"
    mangaLayout: str = "style1"
    steps: int = 20
    guidance: float = 7.5
    lora: str = "ghibli"
    negativePrompt: str = ""
    seed: str = ""

graph = create_studio_graph()

@app.get("/api/history")
async def get_history():
    files = []
    for f in output_dir.glob("comic_page_*.png"):
        files.append((f.stat().st_mtime, f.name))
    files.sort(reverse=True)
    return {"history": [f"/outputs/{name}" for _, name in files]}

@app.post("/api/generate")
async def generate_short_comic(req: GenerateRequest):
    
    async def event_generator():
        yield "data: [START] Kích hoạt quá trình tạo truyện...\n\n"
        await asyncio.sleep(0.1)
        
        config = {"configurable": {"thread_id": "short_comic_gen"}}
        
        try:
            # We can stream the events from LangGraph
            initial_state = {
                "user_prompt": req.prompt, 
                "current_schema": {}, 
                "validation_errors": [], 
                "next_step": "",
                "layoutStyle": req.layoutStyle,
                "mangaLayout": req.mangaLayout,
                "steps": req.steps,
                "guidance": req.guidance,
                "lora": req.lora,
                "negativePrompt": req.negativePrompt,
                "seed": req.seed
            }
            for event in graph.stream(initial_state, config):
                for key, value in event.items():
                    if key == "storyboarder":
                        yield "data: [AGENT] Đang xây dựng kịch bản chi tiết...\n\n"
                    elif key == "validator":
                        errs = value.get("validation_errors", [])
                        if errs:
                            yield f"data: [AGENT] Art Director yêu cầu sửa đổi: {errs[0][:100]}...\n\n"
                        else:
                            yield "data: [AGENT] Kịch bản hoàn hảo! Bắt đầu vẽ...\n\n"
                    elif key == "renderer":
                        yield "data: [RENDERER] Bắt đầu quá trình vẽ và ghép ảnh...\n\n"
                        # When renderer is done, it adds 'output_page' to state
                        output_page = value.get("output_page")
                        if output_page:
                            # Convert local path to URL
                            url_path = Path(output_page).relative_to("outputs").as_posix()
                            yield f"data: [RESULT] /outputs/{url_path}\n\n"
        except Exception as e:
            yield f"data: [ERROR] Lỗi hệ thống: {e}\n\n"
            
        yield "data: [DONE]\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
