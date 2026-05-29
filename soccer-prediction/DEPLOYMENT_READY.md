# ✅ COMPLETE INSTALLATION & DEPLOYMENT GUIDE

## 🎯 Current Status

✅ **Python 3.14.2 installed**
✅ **API keys configured**
✅ **Telegram integration added**
✅ **Core packages installed** (requests, pandas, numpy, scikit-learn)
✅ **ML packages installed** (xgboost, lightgbm, optuna, shap)
✅ **Telegram packages installed** (python-telegram-bot, ratelimit)
✅ **Code fixed** (typo in model_training.py)
✅ **CatBoost removed** (doesn't work without Visual Studio)

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Verify Installation (1 minute)

```cmd
cd C:\Users\FX\soccer_prediction_bot
py test_setup.py
```

**Expected output**: All tests show `[OK]`

---

### Step 2: Run Demo (2 minutes)

```cmd
py demo.py
```

This will:
- Generate 100 mock matches
- Train a simple model  
- Show predictions
- Demonstrate features

**No API calls required!**

---

### Step 3: Configure for Limited Data Collection (Recommended First)

Edit `config.py` around line 35:

```python
# Change this:
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
    "La Liga": {"id": 140, "country": "Spain"},
    "Bundesliga": {"id": 78, "country": "Germany"},
    "Serie A": {"id": 135, "country": "Italy"},
    "Ligue 1": {"id": 61, "country": "France"},
}

# To this (for testing):
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
}
```

And around line 45:

```python
# Change this:
SEASONS = list(range(2015, 2024))

# To this (for testing):
SEASONS = [2023, 2024]  # Just 2 seasons
```

This reduces API calls from 5000+ to ~1000.

---

### Step 4: Collect Data (30-60 minutes)

```cmd
py main.py --step collect
```

**What it does:**
- Fetches match data from API-Football
- Downloads team statistics
- Saves to `data/raw/` folder

**Expected time**: 30-60 minutes for 1 league, 2 seasons
**API calls**: ~1000 (within free tier if spread over 10 days)

---

### Step 5: Preprocess Data (5 minutes)

```cmd
py main.py --step preprocess
```

**What it does:**
- Cleans raw data
- Handles missing values
- Creates base features
- Saves to `data/processed/`

---

### Step 6: Engineer Features (10 minutes)

```cmd
py main.py --step features
```

**What it does:**
- Calculates Elo ratings
- Creates rolling averages
- Computes H2H statistics
- Generates 100+ features

---

### Step 7: Train Models (30 minutes)

```cmd
py main.py --step train
```

**What it does:**
- Trains XGBoost model
- Trains LightGBM model
- Creates ensemble
- Evaluates performance
- Saves models to `models/` folder

**Expected accuracy**: 58-65% on match outcomes

---

### Step 8: Make Predictions (instant)

```cmd
py main.py --step predict
```

**What it does:**
- Loads trained models
- Makes predictions on test matches
- Shows confidence scores
- Displays recommendations

---

### Step 9: Set Up Telegram (5 minutes)

1. **Create Telegram Bot:**
   - Open Telegram
   - Message `@BotFather`
   - Send `/newbot`
   - Follow prompts
   - **Copy the bot token**

2. **Get Your Chat ID:**
   - Message `@userinfobot`
   - **Copy your Chat ID**

3. **Configure:**
   - Edit `config.py`
   - Add after line 22:

```python
# Telegram Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"
TELEGRAM_ENABLED = True
```

4. **Test:**
```cmd
py telegram_notifier.py
```

You should get a message on Telegram!

---

### Step 10: Deploy API (Optional)

```cmd
py -m pip install fastapi uvicorn
py -m uvicorn api:app --reload
```

Then open: http://localhost:8000/docs

---

## 📊 FULL AUTOMATED PIPELINE

### Option A: Quick Test (1 hour total)

```cmd
# 1. Edit config.py to use 1 league, 1 season
# 2. Run full pipeline
py main.py --step full
```

### Option B: Production (8-10 hours)

```cmd
# Leave all leagues and seasons
py main.py --step full
```

This runs everything automatically:
- Data collection
- Preprocessing  
- Feature engineering
- Model training
- Predictions

---

## 🤖 USING TELEGRAM NOTIFICATIONS

Once Telegram is configured, predictions are automatically sent!

### Send Single Prediction

```python
from prediction import MatchPredictor
from telegram_notifier import TelegramNotifier

# Load models
# ... (model loading code) ...

# Make prediction
prediction = predictor.predict_comprehensive(
    "Arsenal", "Chelsea", match_features
)

# Send to Telegram
notifier = TelegramNotifier()
notifier.send_prediction(prediction)
```

### Automated Daily Predictions

Create `daily_predictions.py`:

```python
from data_collection import DataCollector
from prediction import MatchPredictor
from telegram_notifier import TelegramNotifier
from datetime import datetime, timedelta

# Get today's matches
collector = DataCollector()
today = datetime.now().strftime("%Y-%m-%d")

# ... fetch matches ...
# ... make predictions ...

# Send to Telegram
notifier = TelegramNotifier()
notifier.send_batch_predictions(predictions)
```

Then schedule it with Windows Task Scheduler!

---

## 📅 AUTOMATED SCHEDULING (Windows Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Name: "Soccer Predictions"
4. Trigger: Daily at 9:00 AM
5. Action: Start a program
   - Program: `C:\Users\FX\AppData\Local\Programs\Python\Python314\python.exe`
   - Arguments: `daily_predictions.py`
   - Start in: `C:\Users\FX\soccer_prediction_bot`
6. Finish

Now you get predictions every day automatically on Telegram!

---

## 🔧 TROUBLESHOOTING

### Data Collection Too Slow
**Solution**: Use smaller dataset
```python
LEAGUES = {"Premier League": {"id": 39, "country": "England"}}
SEASONS = [2023]
```

### API Rate Limit Hit
**Solution**: Lower rate limit
```python
REALTIME_CONFIG = {"api_rate_limit": 5}
```

### Low Accuracy
**Expected!** Soccer is hard to predict.
- 60-65% is excellent
- 50-55% is professional level
- 95% is impossible

### Telegram Not Working
1. Check bot token and chat ID
2. Send `/start` to your bot first
3. Run `py telegram_notifier.py` to test

---

## 📊 MONITORING & MAINTENANCE

### Check Logs
```cmd
type logs\bot.log
```

### View Collected Data
```cmd
dir data\raw
dir data\processed
```

### View Trained Models
```cmd
dir models
```

### Test API Health
```cmd
py test_setup.py
```

---

## 🎯 RECOMMENDED WORKFLOW

### For Testing (First Time):
1. ✅ Run `py test_setup.py`
2. ✅ Run `py demo.py`
3. ✅ Edit config.py (1 league, 1 season)
4. ✅ Run `py main.py --step collect` (wait 30 min)
5. ✅ Run `py main.py --step train` (wait 30 min)
6. ✅ Run `py main.py --step predict`
7. ✅ Set up Telegram
8. ✅ Test `py telegram_notifier.py`

### For Production:
1. ✅ Configure all leagues and 8 years of data
2. ✅ Run `py main.py --step full` (wait 8-10 hours)
3. ✅ Set up Telegram notifications
4. ✅ Schedule daily predictions
5. ✅ Deploy API (optional)
6. ✅ Monitor accuracy weekly
7. ✅ Retrain models monthly with new data

---

## 💻 SYSTEM COMMANDS REFERENCE

```cmd
# Installation
py -m pip install -r requirements.txt

# Testing
py test_setup.py              # Test everything
py demo.py                    # Demo with mock data
py telegram_notifier.py       # Test Telegram

# Data Pipeline
py main.py --step collect     # Collect data (30 min - 8 hours)
py main.py --step preprocess  # Clean data (5 min)
py main.py --step features    # Engineer features (10 min)
py main.py --step train       # Train models (30 min)
py main.py --step predict     # Make predictions (<1 sec)
py main.py --step full        # Run everything (8-10 hours)

# API Server
py -m uvicorn api:app --reload  # Start API server
# Then visit: http://localhost:8000/docs

# Maintenance
type logs\bot.log             # View logs
dir data\raw                  # Check raw data
dir models                    # Check trained models
```

---

## 📱 TELEGRAM MESSAGE EXAMPLE

When configured, you'll get messages like:

```
⚽ SOCCER PREDICTION ⚽

🏟️ Manchester United vs Liverpool
━━━━━━━━━━━━━━━━━━━━

📊 MATCH RESULT
🏠 Prediction: Home Win
💯 Confidence: 68.0% (MEDIUM)

Probabilities:
   🏠 Home: 68.0%
   🤝 Draw: 18.0%
   ✈️ Away: 14.0%

⚽ GOALS PREDICTION
📊 Expected Goals: 2.6
🎯 Most Likely Score: 2-1 (12.4%)
📈 Over 2.5: 56.8%
⚽⚽ BTTS: 64.2%

💡 RECOMMENDATIONS
🟡 Match Result: Home Win
   📊 68.0% | Risk: MEDIUM

⚠️ DISCLAIMER
Educational purposes only. No guarantees.
```

---

## ✅ VERIFICATION CHECKLIST

Before running data collection:

- [x] Python installed (py --version shows Python 3.14.2)
- [x] Dependencies installed (py -m pip list shows xgboost, lightgbm, etc.)
- [x] API keys configured in config.py
- [x] test_setup.py runs successfully
- [x] demo.py works
- [ ] Telegram configured (optional)
- [ ] config.py edited for smaller dataset (recommended)

---

## 🚀 READY TO GO!

Run this now:

```cmd
cd C:\Users\FX\soccer_prediction_bot
py main.py --step collect
```

This will start collecting soccer data from APIs!

**Note**: With current config (all leagues, 8 years), this takes 8-10 hours.
**Recommendation**: Edit config.py first to use 1 league, 1-2 seasons (takes 30-60 min)

---

## 📞 NEED HELP?

- **Logs**: Check `logs\bot.log`
- **Test**: Run `py test_setup.py`
- **Demo**: Run `py demo.py`
- **Docs**: Read README.md, QUICKSTART.md

---

**Everything is installed and ready! Start with `py demo.py` to see it in action!** 🎯⚽
