from panel_engine.unified_pipeline import generate_panels_unified
from pathlib import Path
import json
schema='outputs/jobs/c83e921fd0f047ee805a555b2a0c1589/story.json'
out='outputs/targeted_cpu_panel'
Path(out).mkdir(exist_ok=True)
try:
 r=generate_panels_unified(schema,out,'models/base/comicBabes_v2.safetensors',device='cuda',base='SDv1.5',lora_path=None,panel_steps=10,guidance_scale=7.5,max_render_width=512,max_render_height=512,style_name='flat_comic',target_panel_ids=['panel_1_2'],seed=8124)
 print('RESULT',r)
except Exception as e:
 import traceback; traceback.print_exc()
