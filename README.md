# Sports Prediction Bot

A self-learning football prediction system combining a statistical ensemble with expected-value (EV) filtering to surface value bets. Two components:

- **`soccer-prediction/`** — data → model → prediction ML pipeline
- **`value-bet-analyzer/`** — bookmaker-margin removal + EV calculation (v7.3)

> **Note:** Sanitized portfolio version. All API keys and tokens removed — configure your own via `.env` (see `.env.example`).

## Highlights

- **82+ matches analyzed daily**
- Ensemble beats single models by **~5%**; accuracy improves via automated calibration
- **3–5 EV-positive bets/day** at a 4–8% modeled ROI
- Ensemble of **Poisson · Dixon-Coles · ELO · form adjustment**
- **Platt calibration** + league-wide Dixon-Coles normalization (v7.3)
- Multi-source data with fallbacks; Telegram alerts; professional reporting

## How It Works

| Module | Responsibility |
|--------|----------------|
| `soccer-prediction/main.py` | Prediction pipeline entry point |
| `soccer-prediction/model_training.py` | Feature engineering + model training |
| `soccer-prediction/prediction.py` | Live prediction generation |
| `value-bet-analyzer/value_bet_analyzer_v7.3.py` | Margin removal, EV, signal-convergence filtering |

## Tech Stack

Python · API-Football / Football-Data.org · statistical modeling (Poisson, Dixon-Coles, ELO) · Platt calibration · Telegram alerts

## Setup

```bash
cp .env.example .env      # fill in your own API keys
python -m pip install -r requirements.txt   # if present
python soccer-prediction/main.py
```

All keys load from environment variables — nothing is hardcoded.

## Disclaimer

For educational and research purposes only. No prediction guarantees profit. Betting carries financial risk — gamble responsibly and only where legal.

---
Built by **Louis Odiatu** · github.com/louisoddie999
