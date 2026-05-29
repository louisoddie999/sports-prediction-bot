# ✅ FIXED THE TYPO! Now Install ML Libraries

## Issue Fixed:
- ✅ Fixed typo in `model_training.py`: `SoccerPredict ionModel` → `SoccerPredictionModel`

## Next Step: Install Machine Learning Libraries

You need to install the ML packages. Run this command:

```cmd
py -m pip install xgboost lightgbm catboost optuna
```

**Expected time**: 5-10 minutes (these are large packages)

---

## Quick Install Command

```cmd
cd C:\Users\FX\soccer_prediction_bot
py -m pip install xgboost lightgbm catboost optuna shap tqdm
```

---

## After Installation

Test again:
```cmd
py main.py --step collect
```

This will start collecting data from APIs.

---

## ⚠️ For Free API Tier

Before running `--step collect`, edit `config.py` to use less data:

```python
# Around line 38, change to:
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
}

# Around line 48, change to:
SEASONS = [2023]  # Just one season
```

This reduces API calls from 5000+ to ~500.

---

## Full Commands

```cmd
# 1. Install ML libraries
py -m pip install xgboost lightgbm catboost optuna

# 2. (Optional) Edit config.py for smaller dataset

# 3. Collect data
py main.py --step collect

# 4. Train models
py main.py --step train

# 5. Make predictions
py main.py --step predict
```

---

## Alternative: Install All At Once

```cmd
py -m pip install -r requirements.txt
```

This installs everything (takes 10-15 minutes).

---

**Run this now:**
```cmd
py -m pip install xgboost lightgbm catboost
```

Then try `py main.py --step collect` again!
