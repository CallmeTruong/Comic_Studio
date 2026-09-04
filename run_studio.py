import os
from dotenv import load_dotenv

# Load env variables including OPENAI_API_KEY
load_dotenv()

from studio_graph.graph import create_studio_graph
from database.sqlite_db import upsert_character

def init_mock_lore():
    # Insert a test character into SQLite so the agents have something to work with
    upsert_character({
        "id": "char_anna",
        "name": "Anna",
        "age": "22",
        "personality": "Brave, slightly reckless, always looking for adventure.",
        "base_prompt_en": "young woman, 22, short brown hair, green eyes, wearing a leather jacket and goggles",
        "seed": 42069,
        "inventory": ["sword", "compass"]
    })

def main():
    print("="*50)
    print("LANGGRAPH COMIC STUDIO INITIALIZING...")
    print("="*50)
    
    init_mock_lore()
    
    graph = create_studio_graph()
    
    user_idea = input("\n[STUDIO] Enter idea for new Chapter (Example: Anna explores an ice cave and speaks Vietnamese): ")
    if not user_idea.strip():
        user_idea = "Anna khám phá một hang động băng tuyết bí ẩn và tìm thấy một chiếc rương cổ."
        print(f"[STUDIO] Using default idea: {user_idea}")
        
    print(f"\n[STUDIO] Processing idea: {user_idea}")
        
    config = {"configurable": {"thread_id": "chapter_1"}}
    
    # Initialize State
    initial_state = {
        "user_prompt": user_idea,
        "chapter_number": 1,
        "current_page_idx": 0,
        "page_scripts": [],
        "retrieved_lore": "",
        "unresolved_hooks": "",
        "chapter_outline": "",
        "current_schema": None,
        "validation_errors": [],
        "vision_feedback": "",
        "human_feedback": "",
        "next_step": ""
    }
    
    # Run entire Workflow
    for event in graph.stream(initial_state, config):
        for k, v in event.items():
            print(f"\n--- Node Completed: {k} ---")
            
    print("\n[STUDIO] 🎉 CHAPTER COMPLETED! Check the outputs/ folder for the comic pages.")

if __name__ == "__main__":
    main()
