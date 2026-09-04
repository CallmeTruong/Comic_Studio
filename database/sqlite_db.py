import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/lorebook.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Characters Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age TEXT,
            personality TEXT,
            base_prompt_en TEXT,
            seed INTEGER,
            inventory TEXT DEFAULT '[]'
        )
    ''')
    
    # Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            background_seed INTEGER
        )
    ''')
    
    # Unresolved Plot Hooks Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_in_chapter INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def get_character(char_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM characters WHERE id=?", (char_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "age": row[2],
            "personality": row[3],
            "base_prompt_en": row[4],
            "seed": row[5],
            "inventory": json.loads(row[6])
        }
    return None

def upsert_character(char_data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO characters (id, name, age, personality, base_prompt_en, seed, inventory)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            age=excluded.age,
            personality=excluded.personality,
            base_prompt_en=excluded.base_prompt_en,
            seed=excluded.seed,
            inventory=excluded.inventory
    ''', (
        char_data["id"], char_data["name"], char_data.get("age", ""), 
        char_data.get("personality", ""), char_data["base_prompt_en"], 
        char_data["seed"], json.dumps(char_data.get("inventory", []))
    ))
    conn.commit()
    conn.close()

def get_all_characters():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, personality, inventory FROM characters")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "personality": r[2], "inventory": json.loads(r[3])} for r in rows]

def get_open_hooks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, created_in_chapter FROM hooks WHERE status='open'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "description": r[1], "created_in_chapter": r[2]} for r in rows]

def add_hook(description: str, chapter: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO hooks (description, created_in_chapter) VALUES (?, ?)", (description, chapter))
    conn.commit()
    conn.close()

def resolve_hook(hook_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE hooks SET status='resolved' WHERE id=?", (hook_id,))
    conn.commit()
    conn.close()

init_db()
