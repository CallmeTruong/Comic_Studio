import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from .prompts import (
    DIRECTOR_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    STORYBOARDER_SYSTEM_PROMPT,
    ART_DIRECTOR_SYSTEM_PROMPT
)
from .state import StudioState
from database.scene_state import get_scene_state
from database.sqlite_db import get_all_characters, get_open_hooks
from langchain_core.runnables import RunnableConfig

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
llm_json = ChatOpenAI(model="gpt-4o", temperature=0.3, model_kwargs={"response_format": {"type": "json_object"}})

def run_director(state: StudioState, config: RunnableConfig) -> StudioState:
    print("[DIRECTOR] Planning new Chapter...")
    series_id = config.get("configurable", {}).get("series_id", "default")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", DIRECTOR_SYSTEM_PROMPT),
        ("human", "User Idea: {user_prompt}\n\nExisting Lore: {lore}\n\nUnresolved Hooks: {hooks}\n\nProvide a detailed Chapter Outline (Page by Page).")
    ])
    
    chars = get_all_characters(series_id)
    lore_text = json.dumps(chars, ensure_ascii=False)
    hooks_text = json.dumps(get_open_hooks(series_id), ensure_ascii=False)
    
    chain = prompt | llm
    res = chain.invoke({
        "user_prompt": state["user_prompt"],
        "lore": lore_text,
        "hooks": hooks_text
    })
    
    state["chapter_outline"] = res.content
    state["retrieved_lore"] = lore_text
    state["unresolved_hooks"] = hooks_text
    return state

def run_writer(state: StudioState) -> StudioState:
    print("[WRITER] Writing detailed script...")
    prompt = ChatPromptTemplate.from_messages([
        ("system", WRITER_SYSTEM_PROMPT),
        ("human", "User Request/Idea (Contains requested language):\n{user_prompt}\n\nChapter Outline:\n{outline}\n\nMicro Scene State (End of last page):\n{scene_state}\n\nHuman Feedback (if any):\n{feedback}\n\nWrite the detailed script for this Chapter.")
    ])
    
    scene = json.dumps(get_scene_state(), ensure_ascii=False)
    
    chain = prompt | llm
    res = chain.invoke({
        "user_prompt": state.get("user_prompt", ""),
        "outline": state["chapter_outline"],
        "scene_state": scene,
        "feedback": state.get("human_feedback", "None")
    })
    
    import re
    script_content = res.content
    
    # Split the script by "--- PAGE X ---" (ignoring case and whitespace)
    page_splits = re.split(r'(?i)---\s*PAGE\s*\d+\s*---', script_content)
    
    # Remove the first split if it's empty (before the first --- PAGE ---)
    if page_splits and not page_splits[0].strip():
        page_splits.pop(0)
    
    # Fallback to single page if no split marker found
    if not page_splits:
        page_splits = [script_content]
        
    scripts = []
    for i, content in enumerate(page_splits):
        if content.strip():
            scripts.append({"page_number": i + 1, "content": content.strip()})
    
    state["page_scripts"] = scripts
    state["current_page_idx"] = 0
    return state

def run_storyboarder(state: StudioState) -> StudioState:
    page_idx = state["current_page_idx"]
    if page_idx >= len(state["page_scripts"]):
        state["next_step"] = "end"
        return state
        
    print(f"[STORYBOARDER] Converting script for page {page_idx+1} to JSON Schema...")
    script = state["page_scripts"][page_idx]["content"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", STORYBOARDER_SYSTEM_PROMPT),
        ("human", "Previous Page Context:\n{prev_context}\n\nWrite the JSON schema for this script:\n{script}\n\nLore (Use strictly these seeds/prompts if characters exist):\n{lore}\n\nMake sure to return valid JSON.")
    ])
    
    previous_context = "None (This is the first page, establish the scene based on the script)."
    prev_schema = state.get("previous_schema")
    if prev_schema and "panels" in prev_schema and prev_schema["panels"]:
        last_panel = prev_schema["panels"][-1]
        previous_context = f"Last Panel Background/Setting: {last_panel.get('panel_prompt_en', 'Unknown')}"
    
    chain = prompt | llm_json
    res = chain.invoke({
        "prev_context": previous_context,
        "script": script,
        "lore": state["retrieved_lore"]
    })
    
    try:
        schema = json.loads(res.content)
        state["current_schema"] = schema
        state["validation_errors"] = []
    except Exception as e:
        state["validation_errors"] = [f"JSON Parse Error: {e}"]
        
    return state

def run_validator(state: StudioState) -> StudioState:
    print("[ART DIRECTOR] Validating JSON Schema...")
    if state.get("validation_errors"):
        state["next_step"] = "storyboarder" # Force retry
        return state
        
    schema_str = json.dumps(state["current_schema"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", ART_DIRECTOR_SYSTEM_PROMPT),
        ("human", "Review this JSON Schema:\n{schema}\n\nReply 'SUCCESS' if valid, or list errors.")
    ])
    
    chain = prompt | llm
    res = chain.invoke({"schema": schema_str})
    
    # If the Art Director says SUCCESS anywhere, we consider it passed.
    # Alternatively, we just check if "SUCCESS" is the main conclusion.
    if "SUCCESS" in res.content.upper():
        state["validation_errors"] = []
        state["next_step"] = "renderer"
    else:
        state["validation_errors"] = [res.content]
        state["next_step"] = "storyboarder"
        print(f"[ART DIRECTOR] Error found: {res.content}")
        
    return state
