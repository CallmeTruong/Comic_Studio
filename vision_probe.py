import base64, os
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
load_dotenv()
p=Path('outputs/comic_page_39c16d18696346f19daff22098a7b000_1.png')
b=base64.b64encode(p.read_bytes()).decode()
m=ChatOpenAI(model=os.getenv('OPENAI_VISION_MODEL','gpt-4o'),temperature=0,base_url=os.getenv('OPENAI_BASE_URL'))
r=m.invoke([{'role':'user','content':[{'type':'text','text':'Reply with JSON containing seen=true and a short summary. Can you inspect this comic page?'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+b}}]}])
print(r.content)
