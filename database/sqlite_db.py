import sqlite3
import json
from pathlib import Path

def get_db_path(series_id: str) -> Path:
    if not series_id:
        series_id = "default"
    db_path = Path(f"data/series/{series_id}/lorebook.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

def init_db(series_id: str):
    db_path = get_db_path(series_id)
    conn = sqlite3.connect(db_path)
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

def get_character(series_id: str, char_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
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

def delete_character(series_id: str, char_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM characters WHERE id=?", (char_id,))
    conn.commit()
    conn.close()

def upsert_character(series_id: str, char_data: dict):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
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
        int(char_data.get("seed", 42)), json.dumps(char_data.get("inventory", []))
    ))
    conn.commit()
    conn.close()

def get_all_characters(series_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, personality, inventory, base_prompt_en, seed, age FROM characters")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "personality": r[2], "inventory": json.loads(r[3]), "base_prompt_en": r[4], "seed": r[5], "age": r[6]} for r in rows]

# --- SETTINGS ---
def get_settings(series_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, background_seed FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "description": r[2], "background_seed": r[3]} for r in rows]

def upsert_setting(series_id: str, setting_data: dict):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO settings (id, name, description, background_seed)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            description=excluded.description,
            background_seed=excluded.background_seed
    ''', (
        setting_data["id"], setting_data["name"], setting_data.get("description", ""), int(setting_data.get("background_seed", 42))
    ))
    conn.commit()
    conn.close()

def delete_setting(series_id: str, setting_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings WHERE id=?", (setting_id,))
    conn.commit()
    conn.close()

# --- HOOKS ---

def get_open_hooks(series_id: str):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, created_in_chapter FROM hooks WHERE status='open'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "description": r[1], "created_in_chapter": r[2]} for r in rows]

def add_hook(series_id: str, description: str, chapter: int):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("INSERT INTO hooks (description, created_in_chapter) VALUES (?, ?)", (description, chapter))
    conn.commit()
    conn.close()

def resolve_hook(series_id: str, hook_id: int):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("UPDATE hooks SET status='resolved' WHERE id=?", (hook_id,))
    conn.commit()
    conn.close()

def delete_hook(series_id: str, hook_id: int):
    init_db(series_id)
    conn = sqlite3.connect(get_db_path(series_id))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hooks WHERE id=?", (hook_id,))
    conn.commit()
    conn.close()

