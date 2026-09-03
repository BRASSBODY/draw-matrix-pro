#!/usr/bin/env python3
"""
Fetch fixtures from FlashScore JSON and convert to cache
"""

import json
import glob
from datetime import datetime

def load_cached_fixtures():
    try:
        with open("fixtures_cache.json", "r") as f:
            data = json.load(f)
            return data.get("fixtures", [])
    except:
        return []

def save_cached_fixtures(fixtures):
    with open("fixtures_cache.json", "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "fixtures": fixtures}, f, indent=2)

def fetch():
    files = glob.glob("flashscore_fixtures_*.json")
    if files:
        latest = max(files)
        with open(latest, "r") as f:
            fixtures = json.load(f)
            events = []
            for f in fixtures:
                # Preserve league name from FlashScore
                league = f.get("league", "Unknown")
                # Clean up league name (remove extra text)
                if league and "Standings" in league:
                    league = league.replace("Standings", "").strip()
                if league and ":" in league:
                    league = league.split(":")[0].strip()
                
                events.append({
                    "home_team": f.get("home", ""),
                    "away_team": f.get("away", ""),
                    "event_date": f.get("kickoff", ""),
                    "status": "notstarted",
                    "league_name": league,  # Preserve the league name!
                    "source": "flashscore"
                })
            save_cached_fixtures(events)
            print(f"✅ Loaded {len(events)} fixtures from {latest}")
            print(f"📋 Sample: {events[0] if events else 'None'}")
            return events
    print("❌ No fixtures found")
    return []

if __name__ == "__main__":
    fetch()