"""Generate a small deterministic QA set through the running local API."""
from __future__ import annotations

import json
from pathlib import Path
import requests

PROMPTS = [
    (
        "bear_enclosure",
        "Write all speech bubbles in natural English only. Two friends look at a calm bear behind a zoo barrier. One says the bear cannot be happy in captivity; the other lists food, shelter, healthcare, and no responsibilities until the argument becomes persuasive. Four panels: setup, escalating logic, silent reconsideration, final visual punchline where the practical friend climbs into the enclosure. Use only the two friends and the bear, one zoo setting, short conversational dialogue, and keep the friends' clothing consistent.",
    ),
    (
        "drawing_lesson_meta",
        "Write all speech bubbles in natural English only. A boastful bear introduces himself in a hand-drawn comic while a blue cat insists it is their turn to draw. Their argument escalates into a tiny shove, then the bear justifies taking the comic by saying every famous character deserves their own lesson. Six panels: immediate introduction, protest, escalation, brief silent beat, meta reveal, visual punchline. Only the bear and blue cat may speak; keep their designs and the drawing-table setting consistent.",
    ),
    (
        "sand_bath_cat",
        "Write all speech bubbles in natural English only. Two cheerful sparrows excitedly roll in sand and announce how wonderful sand bathing feels. A reserved gray cat starts to object, hesitates, then quietly says 'Never mind.' Three panels: joyful setup, interrupted reaction, deadpan anticlimax. Use only the two sparrows and the gray cat, one beach setting, minimal dialogue, and make the cat's expression carry the final joke.",
    ),
    (
        "robot_housework_vi",
        "Write all speech bubbles in natural Vietnamese only. Một người thuê robot dọn nhà để có thêm thời gian nghỉ ngơi. Robot hỏi phải dọn những gì, người đó liệt kê mọi thứ rồi phát hiện robot đã học cách giao việc ngược lại cho chủ. Bốn panel: thiết lập, danh sách việc, im lặng nhận ra, cú chốt trực quan khi người chủ cầm chổi còn robot nằm nghỉ. Chỉ dùng một người và một robot, một căn hộ, thoại tiếng Việt tự nhiên, ngắn gọn.",
    ),
    (
        "meeting_livestream",
        "Write all speech bubbles in natural English only. A student secretly watches a cooking livestream during a boring meeting. The manager asks for the presentation, the student shares the screen, and the final panel reveals everyone quietly taking notes from the recipe. Four panels, one meeting room, two recurring speaking characters plus silent background silhouettes only if necessary, short natural dialogue, and a clear visual punchline.",
    ),
]


def main() -> None:
    root = Path(__file__).parent
    out = root / "qa_results"
    out.mkdir(exist_ok=True)
    for index, (name, prompt) in enumerate(PROMPTS):
        response = requests.post(
            "http://127.0.0.1:8000/api/generate",
            json={"prompt": prompt, "steps": 80, "guidance": 7.5, "lora": "flat_comic", "seed": str(4100 + index), "pageCount": 1},
            stream=True,
            timeout=1800,
        )
        response.raise_for_status()
        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                events.append(line[6:])
        (out / f"{name}.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        results = [e[9:].strip() for e in events if e.startswith("[RESULT]")]
        print(name, results)
        if not results:
            raise RuntimeError(f"No generated page for {name}")


if __name__ == "__main__":
    main()
