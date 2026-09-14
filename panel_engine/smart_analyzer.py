from __future__ import annotations


def infer_emotion_from_dialogues_smart(dialogues) -> str:
    """Use the structured emotion field; never classify arbitrary dialogue text.

    The previous keyword table was a brittle, language-specific guesser and
    could inject an emotion that the writer never authored.
    """
    if not dialogues:
        return ""
    for dialogue in dialogues:
        value = getattr(dialogue, "emotion", None)
        if value is None and isinstance(dialogue, dict):
            value = dialogue.get("emotion")
        value = str(value or "").strip()
        if value:
            return value
    return ""

