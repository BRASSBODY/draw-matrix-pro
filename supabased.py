# supabased.py
from supabase import create_client
import datetime

SUPABASE_URL = "https://lyrteygektllnfxhqkzp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx5cnRleWdla3RsbG5meGhxa3pwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg0NTA4NjAsImV4cCI6MjEwNDAyNjg2MH0.ukOUI9ECU5Zu-fLVWDYrXyxbEpvZve0YjJvEax1cA0k"

client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Connected to Supabase!")

# Test insert
try:
    data = client.table("recommendations").insert({
        "event_id": "test_001",
        "home_team": "Test Home",
        "away_team": "Test Away",
        "tournament": "Test League",
        "match_date": datetime.datetime.now().isoformat(),
        "draw_odds": 3.30,
        "h2h_draw_rate": 0.30,
        "heatmap_score": 0.35,
        "recommendation": "BET",
        "confidence": "MEDIUM",
        "result": "PENDING"
    }).execute()
    print("✅ Test insert successful!")
    print(f"   Data: {data}")
except Exception as e:
    print(f"❌ Insert failed: {e}")