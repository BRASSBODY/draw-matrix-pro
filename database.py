# database.py – SQLite storage
import os
import sqlite3
from datetime import datetime

os.makedirs("data", exist_ok=True)
DB_PATH = "data/draw_matrix_pro.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            home_team TEXT,
            away_team TEXT,
            tournament TEXT,
            match_date TEXT,
            draw_odds REAL,
            h2h_draw_rate REAL,
            heatmap_score REAL,
            recommendation TEXT,
            confidence TEXT,
            created_at TEXT,
            result TEXT,
            actual_score TEXT,
            roi REAL
        )
    """)
    conn.commit()
    conn.close()

def save_recommendation(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO recommendations (
            event_id, home_team, away_team, tournament, match_date,
            draw_odds, h2h_draw_rate, heatmap_score, recommendation,
            confidence, created_at, result, actual_score, roi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("event_id"),
        data.get("home_team"),
        data.get("away_team"),
        data.get("tournament"),
        data.get("match_date"),
        data.get("draw_odds"),
        data.get("h2h_draw_rate"),
        data.get("heatmap_score"),
        data.get("recommendation"),
        data.get("confidence"),
        datetime.now().isoformat(),
        data.get("result", "PENDING"),
        data.get("actual_score"),
        data.get("roi"),
    ))
    conn.commit()
    conn.close()
