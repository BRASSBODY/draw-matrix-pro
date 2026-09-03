# Form scoring integration

## Files
- `form_scoring.py` – real implementations of form / streaks / referee / importance + hard skips

## Wire into draw_agent.py

1. Copy `form_scoring.py` next to `draw_agent.py` and `config.py`.

2. At top of `draw_agent.py` (after `import config`):

```python
from form_scoring import (
    score_team_draw_form,
    score_team_streaks,
    score_referee,
    score_match_importance,
    hard_skip_reasons,
)
```

3. **Remove** the old stub functions in `draw_agent.py`:
   - `score_team_draw_form`
   - `score_team_streaks`
   - `score_referee`
   - `score_match_importance` (replaced with version that applies WOMEN_PENALTY etc.)

4. In `compute_draw_score`, change:

```python
s7 = score_referee(event)
```
to:
```python
s7 = score_referee(event, stats)
```

5. In `analyze_events`, after you have `odds` / `h2h` / `stats` and a valid `draw_odds`:

```python
skips = hard_skip_reasons(event, odds, h2h, stats)
if skips:
    logger.info(f"Skipping {home} vs {away} – {'; '.join(skips)}")
    continue

draw_prob = compute_draw_score(event, odds, h2h, stats)
```

6. Optional: add to `config.py`:

```python
ODDS_STAKE_MIN = 2.60
ODDS_STAKE_MAX = 3.60
MIN_H2H_MEETINGS = 4
```

## Behaviour summary

| Scorer | Uses | Output |
|--------|------|--------|
| `score_team_draw_form` | last-5 WDL / draw counts / season draw % per side | ~0.15–0.45 typical |
| `score_team_streaks` | win streak penalty, draw streak / density bonus | ~0.15–0.85 |
| `score_referee` | referee draw rate if API sends it | 0.5 if unknown |
| `score_match_importance` | league bonus, friendly/women/youth, heavy fav, odds band | 0–1 |
| `hard_skip_reasons` | odds band, min H2H, youth/reserve, form blowout | list of reasons |

Unknown API fields → safe priors (not zeros). Log a sample `stats` / `h2h` JSON once and we can tighten key names to Bzzoiro exactly.
