import re

PREFIXES = [
    "draw a",
    "draw the",
    "draw",
    "show a",
    "show the",
    "show",
    "depict",
    "illustrate",
    "frame shows",
    "panel shows",
]


def clean_instruction_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    lowered = cleaned.lower()
    for prefix in PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].lstrip(" ,.-")
            break
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned

