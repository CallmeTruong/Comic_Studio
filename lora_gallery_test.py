from pathlib import Path
import json
from panel_engine.unified_pipeline import generate_panels_unified
from page.builder import build_comic_page
from page.layouts import select_layout_name
from utils.parser import load_comic_from_json
from config import CONFIG

root=Path(__file__).parent
source=root/'outputs/jobs/843983ae10a44e41aa102114d0091027'
schema=source/'story.json'
comic=load_comic_from_json(json.loads(schema.read_text(encoding='utf-8')))
loras={
 'ghibli':'models/loras/ghibli_style_offset.safetensors',
 'cartoony':'models/loras/cartoony.safetensors',
 'manga':'models/loras/MjManga.safetensors',
 'vintage':'models/loras/1950sVintageArt.safetensors',
}
for i,(name,lora) in enumerate(loras.items()):
    job=root/'outputs'/'lora_gallery'/name
    panels=job/'panels'; page=job/'comic_page.png'; job.mkdir(parents=True,exist_ok=True)
    generate_panels_unified(str(schema),str(panels),CONFIG.models.base_model,device='cuda',base='SDv1.5',lora_path=lora,lora_scale=1.0,panel_steps=80,guidance_scale=7.5,max_render_width=896,max_render_height=896,negative_prompt_extra='text, watermark, extra limbs, duplicate characters, deformed hands',series_id='gallery_'+name,seed=5200+i,style_name=CONFIG.style.preset)
    ids=[p.id for p in comic.panels if p.page_number==1]
    build_comic_page(str(panels),str(page),ids,str(schema),inject_bubbles=True,use_adaptive_layout=True,layout_name=select_layout_name(len(ids)))
    print(name,page)
