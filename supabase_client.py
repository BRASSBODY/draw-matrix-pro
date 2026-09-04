# supabase_client.py
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lyrteygektllnfxhqkzp.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx5cnRleWdla3RsbG5meGhxa3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg0NTA4NjAsImV4cCI6MjEwNDAyNjg2MH0.ukOUI9ECU5Zu-fLVWDYrXyxbEpvZve0YjJvEax1cA0k")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_to_supabase(data):
    """Save recommendation to Supabase"""
    try:
        result = client.table("recommendations").insert({
            "event_id": data.get("event_id"),
            "home_team": data.get("home_team"),
            "away_team": data.get("away_team"),
            "tournament": data.get("tournament"),
            "match_date": data.get("match_date"),
            "draw_odds": data.get("draw_odds"),
            "h2h_draw_rate": data.get("h2h_draw_rate"),
            "heatmap_score": data.get("heatmap_score"),
            "recommendation": data.get("recommendation"),
            "confidence": data.get("confidence"),
            "result": data.get("result", "PENDING"),
            "actual_score": data.get("actual_score"),
            "roi": data.get("roi", 0)
        }).execute()
        return result.data
    except Exception as e:
        print(f"❌ Supabase save failed: {e}")
        return None

def get_recommendations(limit=50):
    """Get recent recommendations"""
    try:
        result = client.table("recommendations")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return result.data
    except Exception as e:
        print(f"❌ Supabase fetch failed: {e}")
        return []

def update_result(event_id, result, actual_score, roi):
    """Update match result"""
    try:
        data = client.table("recommendations")\
            .update({
                "result": result,
                "actual_score": actual_score,
                "roi": roi
            })\
            .eq("event_id", event_id)\
            .execute()
        return data.data
    except Exception as e:
        print(f"❌ Supabase update failed: {e}")
        return None

print("✅ Supabase client ready!")