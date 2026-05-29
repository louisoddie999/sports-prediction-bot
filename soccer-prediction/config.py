"""
Configuration file for the Soccer Prediction Bot
Contains API keys, database settings, and model parameters
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration — load from environment (.env). NEVER hardcode keys.
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")  # API-Sports key
API_FOOTBALL_HOST = "v3.football.api-sports.io"
API_FOOTBALL_BASE_URL = f"https://{API_FOOTBALL_HOST}"

# Alternative APIs (Free Tier)
FOOTBALL_DATA_ORG_KEY = os.getenv("FOOTBALL_DATA_ORG_KEY", "")  # Football-Data.org key
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

# Weather API (Optional - for weather-based features)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")  # OpenWeather key
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")  # get from BotFather
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # get from userinfobot
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"


# Data Paths
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed")
MODELS_DIR = "models"
LOGS_DIR = "logs"

# Create directories if they don't exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Leagues Configuration (API-Football IDs)
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
    "La Liga": {"id": 140, "country": "Spain"},
    "Bundesliga": {"id": 78, "country": "Germany"},
    "Serie A": {"id": 135, "country": "Italy"},
    "Ligue 1": {"id": 61, "country": "France"},
}

# Seasons to fetch (last 8 years for training)
# For testing, reduce to just recent seasons: [2022, 2023]
SEASONS = list(range(2015, 2024))

# Model Parameters
MODEL_CONFIG = {
    "test_size": 0.2,
    "validation_size": 0.15,
    "random_state": 42,
    "cv_folds": 5,
    "n_trials": 100,  # Optuna optimization trials
}

# XGBoost Hyperparameters
XGBOOST_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 3,  # Home Win, Draw, Away Win
    "max_depth": [6, 8, 10, 12],
    "learning_rate": [0.01, 0.05, 0.1],
    "n_estimators": [100, 200, 300, 500],
    "min_child_weight": [1, 3, 5],
    "gamma": [0, 0.1, 0.2],
    "subsample": [0.8, 0.9, 1.0],
    "colsample_bytree": [0.8, 0.9, 1.0],
    "reg_alpha": [0, 0.1, 0.5],
    "reg_lambda": [1, 1.5, 2],
    "tree_method": "hist",
    "device": "cpu",  # Change to "cuda" if GPU available
}

# LightGBM Hyperparameters
LIGHTGBM_PARAMS = {
    "objective": "multiclass",
    "num_class": 3,
    "boosting_type": ["gbdt", "dart"],
    "num_leaves": [31, 50, 70],
    "learning_rate": [0.01, 0.05, 0.1],
    "n_estimators": [100, 200, 300],
    "min_child_samples": [20, 30, 50],
    "subsample": [0.8, 0.9, 1.0],
    "colsample_bytree": [0.8, 0.9, 1.0],
    "reg_alpha": [0, 0.1, 0.5],
    "reg_lambda": [1, 1.5, 2],
    "device": "cpu",
}

# Feature Engineering Configuration
FEATURE_CONFIG = {
    "rolling_windows": [3, 5, 10],  # Last N matches
    "elo_k_factor": 32,
    "elo_initial": 1500,
    "home_advantage": 100,  # Elo points
    "form_weight_decay": 0.9,  # Recent matches more important
}

# Prediction Thresholds
PREDICTION_CONFIG = {
    "min_confidence": 0.60,  # Minimum probability to recommend
    "high_confidence": 0.75,  # High confidence threshold
    "expected_accuracy": 0.65,  # Realistic target (95% is unrealistic)
    "value_bet_threshold": 1.1,  # Odds ratio for value bets
}

# Real-time Update Settings
REALTIME_CONFIG = {
    "update_interval": 3600,  # Update every hour (in seconds)
    "pre_match_hours": 24,  # Start tracking 24 hours before match
    "api_rate_limit": 30,  # Requests per minute
}

# Database Configuration (Optional - for storing predictions)
DATABASE_CONFIG = {
    "sqlite_path": os.path.join(DATA_DIR, "predictions.db"),
    "table_predictions": "predictions",
    "table_results": "results",
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": os.path.join(LOGS_DIR, "bot.log"),
}

# Feature Importance Threshold
FEATURE_IMPORTANCE_THRESHOLD = 0.01  # Drop features with importance < 1%

# Warning Messages
RESPONSIBLE_BETTING_WARNING = """
⚠️ RESPONSIBLE BETTING WARNING ⚠️
This bot provides statistical predictions for educational purposes only.
- No prediction system guarantees 95%+ accuracy
- Soccer has inherent randomness (injuries, referee decisions, luck)
- Past performance does not guarantee future results
- Only bet what you can afford to lose
- Seek help if gambling becomes a problem
"""

# Ethical Considerations
ETHICAL_NOTES = """
LIMITATIONS:
1. Data Bias: Historical data may not reflect current team dynamics
2. External Factors: Weather, morale, tactical changes are hard to quantify
3. Black Swan Events: Unexpected red cards, VAR decisions, etc.
4. Overfitting Risk: Model may memorize patterns that don't generalize
5. API Limitations: Real-time data may have delays or inaccuracies

REALISTIC EXPECTATIONS:
- Top professional models achieve 50-55% accuracy on match outcomes
- Over/Under goals: 55-60% accuracy is excellent
- Correct score: 10-15% accuracy (high variance)
- A 65-70% success rate would be exceptional for this system
"""
