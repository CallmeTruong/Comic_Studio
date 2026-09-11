from pathlib import Path
from PIL import Image, ImageDraw

from page.builder import build_comic_page

schema = "outputs/story_1788957420.json"
panel_dir = "outputs/panels"
output = "outputs/sd15_test_comic.png"
build_comic_page(
    panels_dir=panel_dir,
    output_path=output,
    expected_panel_ids=["panel_1_1", "panel_1_2", "panel_1_3", "panel_1_4"],
    schema_path=schema,
    inject_bubbles=True,
    use_adaptive_layout=True,
    layout_name="Layout1",
)

paths = [Path(panel_dir) / f"panel_1_{i}.png" for i in range(1, 5)]
thumbs = []
for path in paths:
    image = Image.open(path).convert("RGB")
    image.thumbnail((720, 520))
    canvas = Image.new("RGB", (740, 560), "white")
    canvas.paste(image, ((740 - image.width) // 2, 30))
    ImageDraw.Draw(canvas).text((20, 10), path.stem, fill="black")
    thumbs.append(canvas)

sheet = Image.new("RGB", (1480, 1120), "#dddddd")
for index, thumb in enumerate(thumbs):
    sheet.paste(thumb, ((index % 2) * 740, (index // 2) * 560))
sheet.save("outputs/sd15_test_panels_contact.png")
print(output)
print("outputs/sd15_test_panels_contact.png")
