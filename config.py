# config.py – Draw Matrix Pro

import os
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# System
# ----------------------------
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/draw_matrix_pro.db")
SCHEDULE_INTERVAL = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", 30))

# ----------------------------
# API Keys
# ----------------------------
BZZOIRO_TOKEN = os.getenv("BZZOIRO_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ----------------------------
# Heatmap Weights
# ----------------------------
WEIGHTS = {
    "h2h_overall": 0.20,
    "h2h_recent": 0.20,
    "team_draw_form": 0.15,
    "team_streaks": 0.10,
    "league_draw_rate": 0.10,
    "match_importance": 0.05,
    "referee": 0.05,
    "odds_value": 0.15,
}

# ----------------------------
# League bonuses
# ----------------------------
LEAGUE_BONUSES = {
    "Argentina Primera B": 0.15,
    "Argentina Primera B Nacional": 0.15,
    "Ecuador LigaPro": 0.10,
    "Uruguay Primera": 0.10,
    "Paraguay Division Intermedia": 0.10,
    "K League 1": 0.10,
    "Brazil Serie B": 0.05,
    "default": 0.0,
}

# ----------------------------
# Odds preference
# ----------------------------
def odds_preference_score(odds: float) -> float:
    if odds is None or odds <= 0:
        return 0.5
    if 2.60 <= odds <= 2.90:
        return 1.0
    elif 2.91 <= odds <= 3.60:
        return 0.8
    elif 3.61 <= odds <= 4.50:
        return 0.5
    else:
        return 0.3

# ----------------------------
# Penalties
# ----------------------------
HEAVY_FAVOURITE_ODDS = 1.80
HEAVY_FAVOURITE_PENALTY = -0.15
LEAGUE_MATCH_BONUS = 0.05
FRIENDLY_PENALTY = -0.10
WOMEN_PENALTY = -0.20

# ----------------------------
# Thresholds
# ----------------------------
BET_THRESHOLD = 0.32
BORDERLINE_THRESHOLD = 0.28

# ----------------------------
# League draw rates (fallback)
# ----------------------------
LEAGUE_DRAW_RATES = {
    "Argentina Primera B": 0.35,
    "Argentina Primera B Nacional": 0.33,
    "Ecuador LigaPro": 0.28,
    "Uruguay Primera": 0.30,
    "Paraguay Division Intermedia": 0.32,
    "K League 1": 0.30,
    "Brazil Serie B": 0.28,
    "default": 0.25,
}