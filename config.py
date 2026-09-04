# config.py – Draw Matrix Pro (Updated with League Draw Rates)

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
    "h2h_overall": 0.15,
    "h2h_recent": 0.15,
    "team_draw_form": 0.12,
    "team_streaks": 0.08,
    "league_draw_rate": 0.12,
    "match_importance": 0.06,
    "referee": 0.04,
    "odds_value": 0.15,
    "motivation": 0.13,
}

# ----------------------------
# League bonuses (added to match_importance)
# ----------------------------
LEAGUE_BONUSES = {
    # South America
    "Argentina Primera B": 0.15,
    "Argentina Primera B Nacional": 0.15,
    "Liga Profesional de Fútbol": 0.10,
    "Ecuador LigaPro": 0.10,
    "Uruguay Primera": 0.10,
    "Paraguay Division Intermedia": 0.10,
    "Categoría Primera A": 0.05,
    "Brazil Serie B": 0.05,
    "Brazil Serie A": 0.03,
    
    # Europe
    "Ekstraklasa": 0.08,
    "Parva Liga": 0.05,
    "FA Cup": 0.05,
    "CAF Champions League": 0.05,
    "Ligue 2": 0.05,
    
    # Asia
    "Persian Gulf Pro League": 0.12,
    "Saudi Pro League": 0.05,
    
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
    # ---- South America ----
    "Argentina Primera B": 0.35,
    "Argentina Primera B Nacional": 0.33,
    "Liga Profesional de Fútbol": 0.33,
    "Ecuador LigaPro": 0.28,
    "Uruguay Primera": 0.30,
    "Paraguay Division Intermedia": 0.32,
    "Categoría Primera A": 0.28,
    "Primera División": 0.27,
    "Brazil Serie B": 0.28,
    "Brazil Serie A": 0.26,

    # ---- Europe ----
    "Premier League": 0.24,
    "La Liga": 0.25,
    "Segunda División": 0.28,
    "Bundesliga": 0.22,
    "Serie A": 0.27,
    "Ligue 1": 0.28,
    "Ligue 2": 0.30,
    "Eredivisie": 0.26,
    "Pro League": 0.28,
    "Superliga": 0.27,
    "Eliteserien": 0.26,
    "Allsvenskan": 0.27,
    "Ekstraklasa": 0.30,
    "Parva Liga": 0.28,
    "Trendyol Super Lig": 0.27,
    "Liga Portugal Betclic": 0.26,
    "Liga 3": 0.25,
    "National League": 0.28,
    "FA Cup": 0.30,
    "CAF Champions League": 0.32,
    "EFL Championship": 0.28,

    # ---- Asia ----
    "Saudi Pro League": 0.28,
    "J1 League": 0.27,
    "K League 1": 0.30,
    "K League 2": 0.40,
    "Persian Gulf Pro League": 0.37,
    "Iran Azadegan League": 0.41,

    # ---- North America ----
    "MLS": 0.26,
    "USL Championship": 0.29,
    "Liga MX": 0.30,

    # ---- Africa ----
    "Egyptian Premier League": 0.36,
    "Ethiopian Premier League": 0.43,
    "Sudan Premier League": 0.41,
    "Sierra Leone National Premier League": 0.39,

    # ---- Oceania ----
    "A-League": 0.28,

    # ---- Default ----
    "default": 0.25,
}