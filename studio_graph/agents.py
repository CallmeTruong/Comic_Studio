import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state import StudioState
from .prompts import (
    ART_DIRECTOR_HUMAN_PROMPT,
    ART_DIRECTOR_SYSTEM_PROMPT,
    STORYBOARDER_SYSTEM_PROMPT,
    build_storyboarder_human_prompt,
    STORY_PLANNER_SYSTEM_PROMPT,
    DIALOGUE_WRITER_SYSTEM_PROMPT,
    STORY_PLANNER_HUMAN_PROMPT,
    DIALOGUE_WRITER_HUMAN_PROMPT,
    VISION_QA_SYSTEM_PROMPT,
)
import os
import base64
import re
from io import BytesIO
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv("OPENAI_BASE_URL")
if not base_url:
    base_url = None

llm = ChatOpenAI(model="gpt-4o", temperature=0.7, base_url=base_url)
llm_json = ChatOpenAI(model="gpt-4o", temperature=0.7, base_url=base_url, model_kwargs={"response_format": {"type": "json_object"}})

def parse_json_content(content) -> dict:
    raw = content if isinstance(content, str) else json.dumps(content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some compatible vision gateways wrap JSON in prose or markdown even
        # when response_format is requested. Recover the outermost object so a
        # transient formatting issue does not discard an otherwise useful QA
        # result.
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _panel_number(value) -> int:
    """Accept either a numeric beat or a schema panel id from the dialogue LLM."""
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"(?:panel[_ -]*)?(?:\d+[_ -]+)?(\d+)$", text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _apply_story_constraints(schema: dict, story_plan: dict) -> None:
    """Copy authored beat constraints into each renderable panel.

    The planner already produces structured subjects/actions/props.  Keeping
    those fields attached to the panel prevents the storyboard LLM from
    accidentally reducing a concrete beat to a vague prose prompt.  No
    object, character, or keyword is inferred here.
    """
    beats = story_plan.get("beats", []) if isinstance(story_plan, dict) else []
    by_panel = {
        _panel_number(beat.get("panel")): beat
        for beat in beats
        if isinstance(beat, dict) and _panel_number(beat.get("panel")) > 0
    }
    for page in schema.get("pages", []):
        page_number = int(page.get("page_number", 1) or 1)
        for index, panel in enumerate(page.get("panels", []), start=1):
            number = (page_number - 1) * 6 + index
            beat = by_panel.get(number)
            if not beat:
                continue
            for field in ("primary_subject", "secondary_subject", "visual_hierarchy", "required_action"):
                value = beat.get(field)
                if value:
                    panel[field] = value
            for field in ("required_subjects", "required_props", "required_text"):
                value = beat.get(field)
                if isinstance(value, dict):
                    # Accept the structured hierarchy form without copying its
                    # field names into the visual contract.
                    value = [value.get("primary"), value.get("secondary")] if field == "required_subjects" else list(value.values())
                elif isinstance(value, (str, int, float)):
                    value = [value]
                if isinstance(value, (list, tuple, set)):
                    placeholders = {"none", "null", "n/a", "na", "unknown", "not applicable"}
                    panel[field] = list(dict.fromkeys(
                        text for item in value
                        if (text := str(item).strip()) and text.casefold() not in placeholders
                    ))


def _normalize_panel_schema(schema: dict) -> None:
    """Ensure every render panel carries the fields needed by the renderer/QA."""
    for page in schema.get("pages", []):
        for panel in page.get("panels", []):
            subjects = panel.get("required_subjects", [])
            # Some model responses use the structured subject hierarchy object
            # in this field even though the render schema expects a list.  Do
            # not let ``list(dict)`` reduce it to the literal keys
            # ("primary", "secondary", ...), which silently discards the
            # actual visual subjects from every downstream prompt.
            if isinstance(subjects, dict):
                ordered = [
                    subjects.get("primary"),
                    subjects.get("secondary"),
                ]
                subjects = [item for item in ordered if item]
            if not isinstance(subjects, list):
                subjects = [subjects] if subjects else []
            panel["required_subjects"] = list(dict.fromkeys(
                str(item).strip() for item in subjects if str(item).strip()
            ))
            panel.setdefault("required_props", [])
            panel.setdefault("required_text", [])
            panel.setdefault("primary_subject", "")
            panel.setdefault("secondary_subject", "")
            panel.setdefault("visual_hierarchy", "")
            panel.setdefault("required_action", "")


def _enforce_vision_gate(review: dict, expected_panel_ids: set[str] | None = None) -> dict:
    """Apply conservative, deterministic gates after the vision model responds.

    Vision models sometimes return an optimistic score while mentioning a missing
    subject in their notes.  The audit is therefore treated as evidence, not as
    optional commentary.  This still allows one minor imperfection through.
    """
    if not isinstance(review, dict):
        return {"passed": False, "score": 0.0, "issues": [], "summary": "Invalid Vision QA response."}
    audit = review.get("panel_audit")
    issues = review.get("issues")
    if not isinstance(audit, list) or not audit:
        review["passed"] = False
        review["score"] = min(float(review.get("score", 0) or 0), 6.0)
        review.setdefault("issues", []).append({
            "panel_id": "page", "type": "story", "severity": "major",
            "reason": "Vision QA did not provide a complete panel-by-panel audit.",
            "correction": "Inspect every panel and explicitly verify its required subjects, action/object, and dialogue."
        })
        return review
    if not isinstance(issues, list):
        review["issues"] = []
        issues = review["issues"]
    # False values are stronger evidence than a generous prose summary.
    def is_false(value) -> bool:
        return value is False or (isinstance(value, str) and value.strip().lower() in {"false", "no", "missing"})

    audited_ids = {str(row.get("panel_id")) for row in audit if isinstance(row, dict) and row.get("panel_id")}
    uncovered = sorted((expected_panel_ids or set()) - audited_ids)
    missing = [row for row in audit if isinstance(row, dict) and (
        is_false(row.get("present_subjects")) or is_false(row.get("required_action_or_object"))
        or is_false(row.get("dialogue_matches"))
    )]
    major = [item for item in issues if isinstance(item, dict) and item.get("severity", "major") in {"critical", "major"}]
    if uncovered:
        for panel_id in uncovered:
            issues.append({
                "panel_id": panel_id, "type": "story", "severity": "major",
                "reason": "Vision QA did not audit this rendered panel.",
                "correction": "Review this panel explicitly and verify every required subject, action, prop, and dialogue."
            })
    if missing:
        for row in missing:
            panel_id = row.get("panel_id", "page")
            if not any(item.get("panel_id") == panel_id and item.get("type") in {"story", "image", "continuity"}
                       for item in issues if isinstance(item, dict)):
                issues.append({
                    "panel_id": panel_id, "type": "story", "severity": "major",
                    "reason": "A required subject, action, or object is not visibly present.",
                    "correction": "Restore the missing required subject/object/action in this panel prompt."
                })
        major = [item for item in issues if isinstance(item, dict) and item.get("severity", "major") in {"critical", "major"}]
    if uncovered or missing or any(item.get("severity") == "critical" for item in issues if isinstance(item, dict)) or len(major) >= 2:
        review["passed"] = False
        review["score"] = min(float(review.get("score", 0) or 0), 6.9)
    else:
        review["passed"] = bool(review.get("passed")) and float(review.get("score", 0) or 0) >= 7.0
    return review

def run_story_planner(state: StudioState) -> StudioState:
    prompt = ChatPromptTemplate.from_messages([("system", STORY_PLANNER_SYSTEM_PROMPT), ("human", STORY_PLANNER_HUMAN_PROMPT)])
    result = (prompt | llm_json).invoke({"idea": state["user_prompt"], "pages": state.get("pageCount", 1)})
    try:
        state["story_plan"] = parse_json_content(result.content)
        state["validation_errors"] = []
        state["next_step"] = "dialogue_writer"
    except Exception as exc:
        state["validation_errors"] = [f"Story plan JSON error: {exc}"]
        state["next_step"] = "story_planner"
    return state


def run_vision_qa(state: StudioState) -> StudioState:
    """Review the rendered page with a multimodal model when supported."""
    pages = state.get("output_pages", [])
    page_path = Path(pages[0]) if pages else None
    if not page_path or not page_path.exists():
        state["vision_qa"] = {"passed": False, "score": 0, "summary": "No rendered page found."}
        state["next_step"] = "failed"
        return state
    vision = ChatOpenAI(
        model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
        temperature=0,
        base_url=base_url,
        max_retries=2,
        timeout=120,
    )
    # Gateways are much more reliable with a modest JPEG than with a multi-MB
    # page PNG.  Preserve enough resolution for panel-level inspection while
    # avoiding silent image drops/HTML responses from compatible vision APIs.
    try:
        with Image.open(page_path) as page_image:
            page_image = page_image.convert("RGB")
            # Keep the request comfortably below the gateway's payload limit.
            page_image.thumbnail((1024, 1400), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            # PNG is accepted more consistently by the configured OpenAI-
            # compatible gateway than JPEG data URLs.  Resize first so the
            # request remains small without changing the media type.
            page_image.save(buffer, format="PNG", optimize=True)
            image_bytes = buffer.getvalue()
        image_mime = "image/png"
    except Exception:
        image_bytes = page_path.read_bytes()
        image_mime = "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    context = json.dumps({"story_plan": state.get("story_plan", {}), "dialogue_plan": state.get("dialogue_plan", {}), "schema": state.get("current_schema", {})}, ensure_ascii=False)
    content = [{"type": "text", "text": f"Review this comic page against this context:\n{context}"}, {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{encoded}"}}]
    try:
        result = vision.invoke([{"role": "system", "content": VISION_QA_SYSTEM_PROMPT}, {"role": "user", "content": content}])
        raw = result.content if isinstance(result.content, str) else json.dumps(result.content)
        try:
            state["vision_qa"] = parse_json_content(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Some gateways ignore response_format and wrap the result in a
            # short explanation. Ask once more using an explicit JSON-only
            # instruction before treating the QA pass as unavailable.
            retry_content = content[:]
            retry_content[0] = {
                "type": "text",
                "text": f"{content[0]['text']}\nReturn ONLY one valid JSON object. No markdown, no explanation."
            }
            retry = vision.invoke([
                {"role": "system", "content": VISION_QA_SYSTEM_PROMPT},
                {"role": "user", "content": retry_content},
            ])
            retry_raw = retry.content if isinstance(retry.content, str) else json.dumps(retry.content)
            state["vision_qa"] = parse_json_content(retry_raw)
        try:
            state["vision_qa"]["score"] = float(state["vision_qa"].get("score", 0))
        except (TypeError, ValueError):
            state["vision_qa"]["score"] = 0.0
        expected_panel_ids = {
            panel.get("id")
            for page in state.get("current_schema", {}).get("pages", [])
            for panel in page.get("panels", [])
            if panel.get("id")
        }
        state["vision_qa"] = _enforce_vision_gate(state["vision_qa"], expected_panel_ids)
        # Persist the review next to the job so the UI/API and later audits can
        # distinguish a validated page from a merely rendered page.
        job_id = page_path.stem.removeprefix("comic_page_").rsplit("_", 1)[0]
        report_path = page_path.parent / "jobs" / job_id / "vision_qa.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    **state["vision_qa"],
                    "attempt": int(state.get("vision_retry_count", 0)) + 1,
                    "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o"),
                    "page": str(page_path),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if state["vision_qa"].get("passed"):
            state["next_step"] = "end"
        elif int(state.get("vision_retry_count", 0)) >= int(state.get("max_vision_retries", 10)):
            state["next_step"] = "failed"
        else:
            state["vision_retry_count"] = int(state.get("vision_retry_count", 0)) + 1
            issues = state["vision_qa"].get("issues", [])
            state["validation_errors"] = [
                f"Vision QA panel {item.get('panel_id', 'page')}: {item.get('correction') or item.get('reason', '')}"
                for item in issues
            ] or [state["vision_qa"].get("summary", "Improve the rendered page.")]
            # Keep a compact, explicit correction block available to the next
            # storyboard pass instead of merely saying that QA failed.
            state["story_plan"]["vision_corrections"] = [
                {
                    "panel_id": item.get("panel_id"),
                    "type": item.get("type"),
                    "correction": item.get("correction") or item.get("reason", ""),
                }
                for item in issues
            ]
            # Preserve the approved cast as an explicit correction so the next
            # storyboard pass cannot solve a missing subject by inventing a
            # group or replacing the protagonists.
            cast_ids = list(state.get("current_schema", {}).get("characters", {}).keys())
            if cast_ids:
                state["story_plan"]["vision_corrections"].append({
                    "panel_id": "page",
                    "type": "continuity",
                    "correction": f"Represent only the registered subjects {cast_ids} required by the story plan; do not replace them or obscure the structured primary/secondary subject hierarchy.",
                })
            issue_types = {item.get("type") for item in issues}
            # A story/image/continuity defect is a visual storyboard defect,
            # not a reason to rewrite otherwise approved dialogue.  Sending
            # mixed issues to the dialogue writer used to make retries drift
            # the plot while leaving the missing prop/action unchanged.
            state["next_step"] = (
                "dialogue_writer"
                if issue_types and issue_types.issubset({"dialogue"})
                else "storyboarder"
            )
    except Exception as exc:
        # Do not silently mark a rendered page as permanently failed because a
        # compatible gateway emitted malformed JSON.  Preserve the raw error,
        # consume one QA retry, and let the graph attempt the review again.
        state["vision_qa"] = {
            "passed": False,
            "score": 0,
            "issues": [{
                "panel_id": "page", "type": "image", "severity": "major",
                "reason": f"Vision QA response was not valid JSON: {exc}",
                "correction": "Repeat the visual audit and return the required JSON schema only.",
            }],
            "summary": f"Vision QA response was unavailable: {exc}",
        }
        retries = int(state.get("vision_retry_count", 0))
        if retries < int(state.get("max_vision_retries", 10)):
            state["vision_retry_count"] = retries + 1
            state["next_step"] = "renderer"
        else:
            state["next_step"] = "failed"
    return state


def run_dialogue_writer(state: StudioState) -> StudioState:
    prompt = ChatPromptTemplate.from_messages([("system", DIALOGUE_WRITER_SYSTEM_PROMPT), ("human", DIALOGUE_WRITER_HUMAN_PROMPT)])
    result = (prompt | llm_json).invoke({
        "plan": json.dumps(state.get("story_plan", {}), ensure_ascii=False),
        "corrections": json.dumps(state.get("story_plan", {}).get("vision_corrections", []), ensure_ascii=False),
    })
    try:
        state["dialogue_plan"] = parse_json_content(result.content)
        state["validation_errors"] = []
        state["next_step"] = "storyboarder"
    except Exception as exc:
        state["validation_errors"] = [f"Dialogue plan JSON error: {exc}"]
        state["next_step"] = "dialogue_writer"
    return state


def run_storyboarder(state: StudioState) -> StudioState:
    print("[STORYBOARDER] Converting user prompt to JSON Schema...")
    
    page_count = max(1, min(int(state.get("pageCount", 1)), 8))
    human_msg = build_storyboarder_human_prompt(
        page_count=page_count,
        has_previous_draft=bool(state.get("validation_errors")),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", STORYBOARDER_SYSTEM_PROMPT),
        ("human", human_msg)
    ])
    
    chain = prompt | llm_json
    res = chain.invoke({
        "prompt": state["user_prompt"],
        "draft": json.dumps(state.get("current_schema", {}), ensure_ascii=False),
        "fixes": "\n".join(state.get("validation_errors", [])),
        "story_plan": json.dumps(state.get("story_plan", {}), ensure_ascii=False),
        "dialogue_plan": json.dumps(state.get("dialogue_plan", {}), ensure_ascii=False),
        "vision_corrections": json.dumps(state.get("story_plan", {}).get("vision_corrections", []), ensure_ascii=False),
    })
    
    try:
        schema = parse_json_content(res.content)
        _apply_story_constraints(schema, state.get("story_plan", {}))
        _normalize_panel_schema(schema)
        # Character cards are immutable across validator/Vision retries.  A
        # fresh storyboard draft must not silently replace the registered cast.
        previous_characters = state.get("current_schema", {}).get("characters", {})
        if previous_characters:
            schema["characters"] = previous_characters
        registered_ids = set(schema.get("characters", {}).keys())
        allowed_ids = set(previous_characters.keys()) if previous_characters else registered_ids
        # Keep only registered cast IDs in every panel. Structured subject fields
        # remain available for stories that legitimately need groups/backgrounds.
        structural_errors: list[str] = []
        for page in schema.get("pages", []):
            for panel in page.get("panels", []):
                active = panel.get("active_char_ids", []) or []
                unknown = [cid for cid in active if cid not in allowed_ids]
                if unknown:
                    structural_errors.append(
                        f"Panel {panel.get('id', 'unknown')} contains unregistered character IDs: {unknown}."
                    )
                panel["active_char_ids"] = [cid for cid in active if cid in allowed_ids]
                actions = panel.get("character_actions", {}) or {}
                panel["character_actions"] = {cid: value for cid, value in actions.items() if cid in allowed_ids}
                # Do not inspect prose for story-specific keywords here. The
                # structured cast/subject fields and Art Director are the
                # source of truth; arbitrary prompt wording must remain free.
        # Deterministically synchronize the visual brief with the approved
        # dialogue. This avoids needless Art Director retries when the model
        # wrote a valid line but forgot a speech/expression cue.
        for page in schema.get("pages", []):
            for panel in page.get("panels", []):
                dialogues = panel.get("dialogues", []) or []
                if not dialogues:
                    continue
                visual = str(panel.get("panel_prompt_en", "")).strip().rstrip(".,")
                lower_visual = visual.lower()
                if "speaking" not in lower_visual and "talking" not in lower_visual:
                    visual += ", speaking, open mouth"
                emotions = [str(item.get("emotion", "")).strip().lower() for item in dialogues]
                for emotion in emotions:
                    if emotion and emotion not in lower_visual:
                        visual += f", {emotion} expression"
                panel["panel_prompt_en"] = visual
        if structural_errors:
            state["validation_errors"] = structural_errors
            return state
        # Dialogue is approved upstream. Do not let the storyboard model
        # silently rewrite it while converting the plan into render JSON.
        approved = state.get("dialogue_plan", {}).get("dialogues", [])
        by_panel: dict[int, list[dict]] = {}
        for item in approved:
            panel_number = _panel_number(item.get("panel", 0))
            character_id = item.get("character_id") or item.get("character")
            if panel_number > 0 and character_id and item.get("text"):
                by_panel.setdefault(panel_number, []).append({
                    "character_id": character_id,
                    "text": item["text"],
                    "emotion": item.get("emotion", "neutral"),
                })
        for page in schema.get("pages", []):
            for index, panel in enumerate(page.get("panels", []), start=1):
                panel_number = (int(page.get("page_number", 1)) - 1) * 6 + index
                if panel_number in by_panel:
                    panel["dialogues"] = by_panel[panel_number]
        # The renderer operates on each panel independently. Repeat the fixed
        # cast and the one setting in every visual brief so an SD image cannot
        # drift into an unrelated portrait or room on later panels.
        cast = schema.get("characters", {})
        for page in schema.get("pages", []):
            for panel in page.get("panels", []):
                panel["panel_prompt_en"] = (
                    "preserve the registered recurring cast and approved setting; "
                    f"{panel.get('panel_prompt_en', '')}"
                )
        state["current_schema"] = schema
        state["validation_errors"] = []
    except Exception as e:
        state["validation_errors"] = [f"JSON Parse Error: {e}"]
        
    return state

def run_validator(state: StudioState) -> StudioState:
    print("[ART DIRECTOR] Validating JSON Schema...")
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 3))
    if state.get("validation_errors"):
        if retry_count >= max_retries:
            state["generation_error"] = "The storyboard did not pass quality checks after the maximum number of retries."
            state["next_step"] = "failed"
            return state
        state["retry_count"] = retry_count + 1
        state["next_step"] = "storyboarder" # Force retry
        return state
        
    schema_str = json.dumps(state["current_schema"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", ART_DIRECTOR_SYSTEM_PROMPT),
        ("human", ART_DIRECTOR_HUMAN_PROMPT)
    ])
    
    chain = prompt | llm
    res = chain.invoke({"schema": schema_str, "idea": state["user_prompt"], "pages": state.get("pageCount", 1)})
    
    # IMPORTANT: use an exact match, not a substring check.
    # "SUCCESS" in "NOT SUCCESSFUL".upper() is True, which used to let
    # rejected/low-quality scripts (no punchline, flat dialogue, etc.)
    # through to the renderer without ever being fixed.
    verdict = res.content.strip().strip("*").strip().rstrip(".!").upper()
    if verdict == "SUCCESS":
        state["validation_errors"] = []
        # Art Director retries and Vision QA retries are separate budgets.  A
        # storyboard that passed here must get a fresh validation budget when
        # Vision QA sends it back for a targeted correction; otherwise the
        # first rejected render can exhaust the storyboard retry counter and
        # terminate the graph before the correction is rendered.
        state["retry_count"] = 0
        state["next_step"] = "renderer"
    else:
        state["validation_errors"] = [res.content]
        if retry_count >= max_retries:
            state["generation_error"] = "The storyboard did not pass quality checks after the maximum number of retries."
            state["next_step"] = "failed"
        else:
            state["retry_count"] = retry_count + 1
            state["next_step"] = "storyboarder"
        
    return state
