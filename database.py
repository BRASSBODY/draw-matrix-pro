# database.py
import os

# Try Supabase first
USE_SUPABASE = True  # Set to False to use SQLite locally

if USE_SUPABASE:
    try:
        from supabase_client import save_to_supabase, get_recommendations, update_result
        print("✅ Using Supabase (cloud)")
        
        def init_db():
            pass  # Supabase handles this
        
        def save_recommendation(data):
            return save_to_supabase(data)
        
        def get_performance_summary():
            # Implement if needed
            return {"total_bets": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_roi": 0}
    except:
        USE_SUPABASE = False

if not USE_SUPABASE:
    # Fallback to SQLite
    import sqlite3
    from datetime import datetime
    
    DB_PATH = "data/draw_matrix_pro.db"
    os.makedirs("data", exist_ok=True)
    
    def init_db():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS recommendations (
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
        )""")
        conn.commit()
        conn.close()
    
    def save_recommendation(data):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""INSERT OR REPLACE INTO recommendations (
            event_id, home_team, away_team, tournament, match_date,
            draw_odds, h2h_draw_rate, heatmap_score, recommendation,
            confidence, created_at, result, actual_score, roi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
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
            data.get("roi", 0)
        ))
        conn.commit()
        conn.close()
    
    init_db()
    print("✅ Using SQLite (local)")