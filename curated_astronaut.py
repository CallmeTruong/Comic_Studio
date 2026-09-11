import json
from pathlib import Path
from panel_engine.unified_pipeline import generate_panels_unified
from page.builder import build_comic_page
from config import CONFIG
root=Path(__file__).parent
source=root/'outputs/jobs/3bf74ab4cc234f95874e46fbaa4fc721/story.json'
job=root/'outputs/curated_jobs/astronaut_vintage'; job.mkdir(parents=True,exist_ok=True)
data=json.loads(source.read_text(encoding='utf8'))
# Ensure the curated sample has concise Vietnamese dialogue.
for page in data.get('pages',[]):
  for p in page.get('panels',[]):
    for d in p.get('dialogues',[]):
      d['text']=d.get('text','')
(schema:=job/'story.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
panels=job/'panels'
generate_panels_unified(str(schema),str(panels),CONFIG.models.base_model,device='cuda',base='SDv1.5',lora_path='models/loras/1950sVintageArt.safetensors',lora_scale=1.0,panel_steps=80,guidance_scale=7.5,max_render_width=896,max_render_height=896,negative_prompt_extra='bad anatomy, extra limbs, duplicate characters, malformed hands, text, watermark',seed=7202,style_name=CONFIG.style.preset)
out=job/'comic_page.png'; build_comic_page(str(panels),str(out),[f'panel_1_{i}' for i in range(1,5)],str(schema),inject_bubbles=True,use_adaptive_layout=True,layout_name='Layout4Panels_Dynamic'); print(out)
