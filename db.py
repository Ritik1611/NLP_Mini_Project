# db.py
import sqlite3
import pandas as pd
from typing import Optional

DB_NAME = "reviews.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Schema remains the same, the issue is with old DB files
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT,
            product TEXT,
            source TEXT,
            title TEXT,
            snippet TEXT,
            link TEXT,
            emotion TEXT,
            fetched_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_reviews(records: list):
    """
    records: list of dicts matching columns: brand, product, source, title, snippet, link, fetched_at
    """
    if not records:
        return
    df = pd.DataFrame(records)
    conn = sqlite3.connect(DB_NAME)
    df.to_sql("reviews", conn, if_exists="append", index=False)
    conn.close()

def fetch_reviews(brand: str, product: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM reviews WHERE brand=? AND product=?"
    df = pd.read_sql_query(query, conn, params=(brand, product))
    conn.close()
    return df

def update_emotions_for_rows(updates: pd.DataFrame):
    """
    updates: DataFrame containing id and emotion columns.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    for _, r in updates.iterrows():
        cur.execute("UPDATE reviews SET emotion=? WHERE id=?", (r['emotion'], int(r['id'])))
    conn.commit()
    conn.close()

def clear_cache():
    """
    Drops the table entirely to ensure the schema is recreated on next init.
    This is more robust than just deleting rows.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS reviews") # <-- CORRECTED LOGIC
    conn.commit()
    conn.close()
    init_db() # Re-create the table immediately after dropping