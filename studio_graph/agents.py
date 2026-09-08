import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state import StudioState
from .prompts import STORYBOARDER_SYSTEM_PROMPT, ART_DIRECTOR_SYSTEM_PROMPT
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
llm_json = ChatOpenAI(model="gpt-4o", temperature=0.7, model_kwargs={"response_format": {"type": "json_object"}})

def run_storyboarder(state: StudioState) -> StudioState:
    print("[STORYBOARDER] Converting user prompt to JSON Schema...")
    
    human_msg = "Create a short comic (3-6 panels) based on this idea:\n{prompt}\n\nMake sure to return valid JSON."
    
    if state.get("validation_errors"):
        errs = "\n".join(state["validation_errors"])
        human_msg += f"\n\nCRITICAL FIXES REQUIRED FROM ART DIRECTOR:\n{errs}\nYou MUST incorporate these fixes into the new JSON."

    prompt = ChatPromptTemplate.from_messages([
        ("system", STORYBOARDER_SYSTEM_PROMPT),
        ("human", human_msg)
    ])
    
    chain = prompt | llm_json
    res = chain.invoke({
        "prompt": state["user_prompt"]
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
    
    if "SUCCESS" in res.content.upper():
        state["validation_errors"] = []
        state["next_step"] = "renderer"
    else:
        state["validation_errors"] = [res.content]
        state["next_step"] = "storyboarder"
        
    return state
