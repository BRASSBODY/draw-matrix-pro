"""
Draw Matrix Pro – real form / streak / referee scorers
Replace the placeholder score_team_draw_form, score_team_streaks, score_referee
in draw_agent.py with these (or: from form_scoring import *).

Designed for flexible Bzzoiro-style payloads: dicts may nest under
home/away, teams, form, last_matches, recent, etc.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import config


# ---------------------------------------------------------------------------
# Helpers – normalise messy API shapes
# ---------------------------------------------------------------------------

def _get(d: Any, *keys: str, default: Any = None) -> Any:
    """Walk nested dicts; try several key names at each level."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _as_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _as_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except (TypeError, ValueError):
        return default


def _is_draw_result(item: Any) -> Optional[bool]:
    """
    Return True if draw, False if decisive, None if unknown.
    Accepts match dicts or single-letter form tokens W/D/L.
    """
    if item is None:
        return None
    if isinstance(item, str):
        t = item.strip().upper()
        if t in ("D", "DRAW"):
            return True
        if t in ("W", "L", "WIN", "LOSS", "HOME", "AWAY", "H", "A"):
            return False
        return None
    if not isinstance(item, dict):
        return None

    # Explicit result flags
    res = _get(item, "result", "outcome", "wdl", default=None)
    if isinstance(res, str):
        return _is_draw_result(res)

    hs = _get(item, "home_score", "home_goals", "score_home", "goals_home")
    aws = _get(item, "away_score", "away_goals", "score_away", "goals_away")
    if hs is not None and aws is not None:
        try:
            return int(hs) == int(aws)
        except (TypeError, ValueError):
            pass

    # Combined "1-1" / "1:1"
    score = _get(item, "score", "ft_score", "result_score")
    if isinstance(score, str) and ("-" in score or ":" in score):
        sep = "-" if "-" in score else ":"
        parts = score.replace(" ", "").split(sep)
        if len(parts) == 2:
            try:
                return int(parts[0]) == int(parts[1])
            except ValueError:
                pass

    return None


def _extract_side_block(stats: Dict, side: str) -> Dict:
    """Pull home/away sub-object from stats if present."""
    if not isinstance(stats, dict):
        return {}
    side = side.lower()
    candidates = []
    if side == "home":
        candidates = [
            stats.get("home"),
            stats.get("home_team"),
            stats.get("team_home"),
            _get(stats, "teams", default={}).get("home") if isinstance(stats.get("teams"), dict) else None,
        ]
    else:
        candidates = [
            stats.get("away"),
            stats.get("away_team"),
            stats.get("team_away"),
            _get(stats, "teams", default={}).get("away") if isinstance(stats.get("teams"), dict) else None,
        ]
    for c in candidates:
        if isinstance(c, dict):
            return c
    return stats  # flat payload – treat whole stats as shared


def _form_sequence(block: Dict, limit: int = 5) -> List[str]:
    """
    Build list of 'W'/'D'/'L' (most recent first when API provides order).
    """
    if not isinstance(block, dict):
        return []

    # Direct sequence strings: "WDLDW", "D,D,W,L,D"
    for key in ("form", "form_string", "last_5", "last5", "recent_form"):
        val = block.get(key)
        if isinstance(val, str) and val.strip():
            raw = val.replace(",", " ").replace("-", " ").split()
            if len(raw) == 1 and len(raw[0]) >= 3 and all(
                c.upper() in "WDL" for c in raw[0]
            ):
                return [c.upper() for c in raw[0][:limit]]
            out = []
            for tok in raw:
                t = tok.strip().upper()
                if t in ("W", "D", "L"):
                    out.append(t)
            if out:
                return out[:limit]

    # List of matches / results
    for key in (
        "last_matches",
        "recent_matches",
        "recent",
        "form_matches",
        "matches",
        "results",
        "last_5_matches",
    ):
        seq = block.get(key)
        if not isinstance(seq, list) or not seq:
            continue
        out: List[str] = []
        for m in seq[:limit]:
            d = _is_draw_result(m)
            if d is True:
                out.append("D")
            elif d is False:
                # Prefer explicit W/L if present
                if isinstance(m, dict):
                    res = str(_get(m, "result", "outcome", "wdl", default="") or "").upper()
                    if res in ("W", "WIN"):
                        out.append("W")
                    elif res in ("L", "LOSS"):
                        out.append("L")
                    else:
                        out.append("L")  # decisive but side unknown – treat as non-draw
                elif isinstance(m, str) and m.upper() in ("W", "L"):
                    out.append(m.upper())
                else:
                    out.append("L")
            # skip unknown
        if out:
            return out[:limit]

    # Numeric counts only
    return []


def _draw_rate_from_counts(draws: int, played: int, prior: float = 0.25, prior_n: float = 4.0) -> float:
    """Bayesian-ish shrink toward league prior when sample is small."""
    played = max(0, played)
    draws = max(0, min(draws, played))
    if played == 0:
        return prior
    return (draws + prior * prior_n) / (played + prior_n)


def _counts_from_form(seq: Sequence[str]) -> Tuple[int, int, int, int]:
    """wins, draws, losses, played"""
    w = sum(1 for x in seq if x == "W")
    d = sum(1 for x in seq if x == "D")
    l = sum(1 for x in seq if x == "L")
    return w, d, l, len(seq)


def _streak_len(seq: Sequence[str], kind: str) -> int:
    """Leading streak length for W or D (seq most-recent-first)."""
    n = 0
    for x in seq:
        if x == kind:
            n += 1
        else:
            break
    return n


def _extract_numeric_form(block: Dict) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """wins, draws, played from numeric fields if present."""
    wins = _get(block, "wins", "last_5_wins", "home_last_5_wins", "wins_last_5")
    draws = _get(block, "draws", "last_5_draws", "home_last_5_draws", "draws_last_5")
    played = _get(block, "played", "matches", "games", "last_5_played")
    w = _as_int(wins, -1)
    d = _as_int(draws, -1)
    p = _as_int(played, -1)
    if w < 0 and d < 0:
        return None, None, None
    w = max(0, w)
    d = max(0, d)
    if p < 0:
        p = max(w + d, 5)  # assume last-5 window if only W/D given
    return w, d, p


# ---------------------------------------------------------------------------
# Public scorers (0–1 range, used by compute_draw_score)
# ---------------------------------------------------------------------------

def score_team_draw_form(event: Dict, stats: Dict) -> float:
    """
    Higher when both teams draw often in recent form.
    Uses stats side blocks, then H2H-adjacent lists, then prior 0.25.
    """
    prior = float(config.LEAGUE_DRAW_RATES.get("default", 0.25))
    league = (event or {}).get("league_name") or (event or {}).get("tournament") or ""
    if league in config.LEAGUE_DRAW_RATES:
        prior = float(config.LEAGUE_DRAW_RATES[league])

    home_blk = _extract_side_block(stats or {}, "home")
    away_blk = _extract_side_block(stats or {}, "away")

    rates: List[float] = []
    for blk in (home_blk, away_blk):
        seq = _form_sequence(blk, limit=5)
        if seq:
            _, d, _, n = _counts_from_form(seq)
            rates.append(_draw_rate_from_counts(d, n, prior=prior))
            continue
        w, d, p = _extract_numeric_form(blk)
        if d is not None and p is not None and p > 0:
            rates.append(_draw_rate_from_counts(d, p, prior=prior))
            continue
        # Flat season draw rate on block
        sdr = _get(blk, "draw_rate", "season_draw_rate", "pct_draws")
        if sdr is not None:
            v = _as_float(sdr, -1.0)
            if v > 1.0:
                v = v / 100.0
            if 0.0 <= v <= 1.0:
                rates.append(v)

    if not rates:
        # Try top-level stats last_matches shared
        seq = _form_sequence(stats or {}, limit=5)
        if seq:
            _, d, _, n = _counts_from_form(seq)
            return _draw_rate_from_counts(d, n, prior=prior)
        return prior

    # Both teams available → average; one side only → shrink toward prior
    if len(rates) == 1:
        return 0.5 * rates[0] + 0.5 * prior
    return sum(rates) / len(rates)


def score_team_streaks(stats: Dict) -> float:
    """
    Favour draw-friendly patterns; penalise long win streaks.
    Returns ~0.2–0.8 typical, 0.55 neutral when unknown.
    """
    home_blk = _extract_side_block(stats or {}, "home")
    away_blk = _extract_side_block(stats or {}, "away")

    scores: List[float] = []
    for blk in (home_blk, away_blk):
        seq = _form_sequence(blk, limit=5)
        if not seq:
            # numeric win streak field
            ws = _as_int(_get(blk, "win_streak", "home_win_streak", "winning_streak"), -1)
            ds = _as_int(_get(blk, "draw_streak", "unbeaten_draw_streak"), -1)
            if ws < 0 and ds < 0:
                continue
            s = 0.55
            if ws >= 3:
                s -= 0.12 * min(ws, 5)  # hot team → fewer draws
            if ds >= 2:
                s += 0.08 * min(ds, 4)
            scores.append(max(0.15, min(0.85, s)))
            continue

        win_streak = _streak_len(seq, "W")
        draw_streak = _streak_len(seq, "D")
        _, draws, _, n = _counts_from_form(seq)
        draw_pct = draws / n if n else 0.0

        s = 0.50
        # Draw streak / density
        s += 0.10 * min(draw_streak, 3)
        s += 0.20 * draw_pct
        # Win streak kills draw equity (Matrix C7 style)
        if win_streak >= 3:
            s -= 0.10 * min(win_streak - 2, 3)
        # Both last two decisive wins
        if len(seq) >= 2 and seq[0] == "W" and seq[1] == "W":
            s -= 0.05
        scores.append(max(0.15, min(0.85, s)))

    if not scores:
        return 0.55  # neutral unknown
    return sum(scores) / len(scores)


def score_referee(event: Dict, stats: Optional[Dict] = None) -> float:
    """
    If API exposes referee draw rate / cards profile, use it; else neutral 0.5.
    """
    stats = stats or {}
    ref = (
        _get(event or {}, "referee", "ref", "match_referee")
        or _get(stats, "referee", "ref")
    )
    if isinstance(ref, dict):
        dr = _get(ref, "draw_rate", "pct_draws", "draws_pct")
        if dr is not None:
            v = _as_float(dr, -1.0)
            if v > 1.0:
                v = v / 100.0
            if 0.0 <= v <= 1.0:
                # Map 20–40% draw refs into ~0.35–0.70
                return max(0.2, min(0.8, 0.25 + v))
        draws = _as_int(_get(ref, "draws"), -1)
        matches = _as_int(_get(ref, "matches", "games"), -1)
        if draws >= 0 and matches > 0:
            return max(0.2, min(0.8, 0.25 + draws / matches))
    # Numeric on event
    dr = _get(event or {}, "referee_draw_rate")
    if dr is not None:
        v = _as_float(dr, -1.0)
        if v > 1.0:
            v = v / 100.0
        if 0.0 <= v <= 1.0:
            return max(0.2, min(0.8, 0.25 + v))
    return 0.50


def score_match_importance(event: Dict, odds: Dict) -> float:
    """
    Extended importance: league bonus, cup/friendly/women, heavy favourite, odds band.
    Drop-in replacement for draw_agent.score_match_importance.
    """
    importance = 0.40
    league_name = (event or {}).get("league_name") or (event or {}).get("tournament") or ""
    league_lower = league_name.lower()

    bonuses = getattr(config, "LEAGUE_BONUSES", {})
    if league_name in bonuses:
        importance += float(bonuses[league_name])
    elif "default" in bonuses:
        importance += float(bonuses.get("default", 0.0))

    if "friendly" in league_lower:
        importance += float(getattr(config, "FRIENDLY_PENALTY", -0.10))
    if "women" in league_lower or "feminine" in league_lower or league_lower.endswith(" w"):
        importance += float(getattr(config, "WOMEN_PENALTY", -0.20))
    if "cup" in league_lower or "puchar" in league_lower:
        importance += 0.0  # neutral; knockout variance handled elsewhere

    # Youth / reserve in team names
    home = str((event or {}).get("home_team") or (event or {}).get("home") or "")
    away = str((event or {}).get("away_team") or (event or {}).get("away") or "")
    blob = f"{home} {away}".lower()
    for tok in ("u19", "u20", "u21", "u23", "reserve", " reserves", " ii", " 2"):
        if tok in blob:
            importance -= 0.15
            break

    home_odds = _as_float((odds or {}).get("home_win"), 3.0)
    away_odds = _as_float((odds or {}).get("away_win"), 3.0)
    heavy = float(getattr(config, "HEAVY_FAVOURITE_ODDS", 1.80))
    if home_odds <= heavy or away_odds <= heavy:
        importance += float(getattr(config, "HEAVY_FAVOURITE_PENALTY", -0.15))

    draw_odds = _as_float((odds or {}).get("draw"), 0.0)
    if 2.60 <= draw_odds <= 2.90:
        importance += 0.05
    elif 2.91 <= draw_odds <= 3.60:
        importance += 0.03

    return max(0.0, min(1.0, importance))


# ---------------------------------------------------------------------------
# Optional hard gates (call from analyze_events before BET)
# ---------------------------------------------------------------------------

def hard_skip_reasons(
    event: Dict,
    odds: Dict,
    h2h: Dict,
    stats: Optional[Dict] = None,
) -> List[str]:
    """Return list of skip reasons; empty => may proceed to score thresholds."""
    reasons: List[str] = []
    draw_odds = _as_float((odds or {}).get("draw"), 0.0)
    stake_min = float(getattr(config, "ODDS_STAKE_MIN", 2.60))
    stake_max = float(getattr(config, "ODDS_STAKE_MAX", 3.60))
    if draw_odds > 0 and not (stake_min <= draw_odds <= stake_max):
        reasons.append(f"C4: Odds out of stake band ({draw_odds})")

    total = _as_int(_get(h2h or {}, "total_matches", "meetings", "played"), 0)
    min_m = int(getattr(config, "MIN_H2H_MEETINGS", 4))
    if total > 0 and total < min_m:
        reasons.append(f"C8: H2H sample too small ({total}<{min_m})")
    # If total==0, do not hard-skip here – scorer already shrinks to prior

    home = str((event or {}).get("home_team") or "")
    away = str((event or {}).get("away_team") or "")
    blob = f"{home} {away}".lower()
    for tok in ("u19", "u20", "u21", "u23"):
        if tok in blob:
            reasons.append(f"Youth side filtered ({tok})")
            break
    if "reserve" in blob:
        reasons.append("Reserve side filtered")

    # Form blowout from sequences (C1-like)
    stats = stats or {}
    hw = aw = None
    for side, target in (("home", "hw"), ("away", "aw")):
        blk = _extract_side_block(stats, side)
        seq = _form_sequence(blk, 5)
        if seq:
            w, _, _, _ = _counts_from_form(seq)
            if side == "home":
                hw = w
            else:
                aw = w
    if hw is not None and aw is not None and abs(hw - aw) >= 4:
        reasons.append("C1: Form blowout (win gap >= 4 in last 5)")

    return reasons
