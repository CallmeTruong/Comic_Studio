import json
from page.builder import build_comic_page
from config import CONFIG
from page.layouts import select_layout_name

schema_path = "data/base/schema/story.json"
with open(schema_path, "r", encoding="utf-8") as f:
    schema = json.load(f)

resolved_layout = select_layout_name(len(schema["panels"]), preferred=CONFIG.story.layout_name)
build_comic_page(
    panels_dir=CONFIG.paths.panel_dir,
    output_path="outputs/comic_page_1.png",
    schema_path=schema_path,
    inject_bubbles=True,
    use_adaptive_layout=True,
    layout_name=resolved_layout,
)
print("Done fixing layout!")
