# Soccer Prediction Bot 🎯⚽

A highly accurate AI-powered soccer match prediction system for major European leagues (Premier League, La Liga, Bundesliga, Serie A, Ligue 1).

## ⚠️ Important Disclaimer

**REALISTIC EXPECTATIONS:**
- **95%+ accuracy is NOT achievable** in soccer prediction due to inherent randomness
- Professional sports betting models typically achieve 50-60% accuracy on match outcomes
- This system targets 65-70% accuracy, which would be exceptional
- Soccer has many unpredictable variables: injuries, referee decisions, weather, luck, etc.

**RESPONSIBLE USE:**
- This bot is for **educational and research purposes only**
- Never bet more than you can afford to lose
- Past performance does not guarantee future results
- Gambling can be addictive - seek help if needed

## 🚀 Features

- **Multi-Model Ensemble**: XGBoost, LightGBM, and CatBoost for robust predictions
- **Advanced Feature Engineering**: Elo ratings, rolling statistics, expected goals (xG), head-to-head records
- **Comprehensive Predictions**: Match outcomes, goal totals, correct scores, over/under markets
- **Real-time Analysis**: Support for live data integration
- **RESTful API**: FastAPI-based web service for easy integration
- **Backtesting**: Historical validation across multiple seasons
- **Confidence Scoring**: Risk assessment for each prediction

## 📊 System Architecture

```
Data Collection → Preprocessing → Feature Engineering → Model Training → Prediction → API
     (APIs)          (Cleaning)      (Elo, xG, Form)    (Ensemble)      (Outcomes)    (REST)
```

## 📁 Project Structure

```
soccer_prediction_bot/
├── config.py                  # Configuration and parameters
├── data_collection.py         # Fetch data from APIs
├── data_preprocessing.py      # Clean and prepare data
├── feature_engineering.py     # Create predictive features
├── model_training.py          # Train ensemble models
├── prediction.py              # Make predictions
├── api.py                     # FastAPI web service
├── main.py                    # Main execution script
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── data/                      # Data storage
│   ├── raw/                   # Raw API data
│   └── processed/             # Processed datasets
├── models/                    # Trained models
└── logs/                      # Execution logs
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+ (3.10 recommended)
- 4GB+ RAM
- Internet connection for API access

### Step 1: Clone Repository
```bash
cd C:\Users\FX
git clone <repository_url>
cd soccer_prediction_bot
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure API Keys

1. Get API keys:
   - **API-Football**: https://www.api-football.com/ (Free tier: 100 requests/day)
   - **Football-Data.org**: https://www.football-data.org/ (Free tier: 10 requests/minute)

2. Create `.env` file:
```bash
API_FOOTBALL_KEY=your_api_football_key_here
FOOTBALL_DATA_KEY=your_football_data_key_here
```

## 🚀 Quick Start

### Option 1: Full Pipeline (Recommended for First Run)

**WARNING**: Full data collection takes 6-12 hours and uses thousands of API calls.

```bash
python main.py --step full --api-key YOUR_API_KEY
```

### Option 2: Step-by-Step Execution

```bash
# Step 1: Collect data (takes hours - use carefully!)
python main.py --step collect

# Step 2: Preprocess data
python main.py --step preprocess

# Step 3: Engineer features
python main.py --step features

# Step 4: Train models (takes 30-60 minutes)
python main.py --step train

# Step 5: Make predictions
python main.py --step predict
```

### Option 3: Use Pre-collected Data

If you have preprocessed data, skip collection:

```bash
# Just train models
python main.py --step train

# Then make predictions
python main.py --step predict
```

## 🌐 API Usage

### Start the API Server

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Get Available Leagues
```bash
curl http://localhost:8000/leagues
```

#### Predict Match Outcome
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Manchester United",
    "away_team": "Liverpool",
    "league": "Premier League",
    "date": "2024-03-15"
  }'
```

Response:
```json
{
  "match": "Manchester United vs Liverpool",
  "timestamp": "2024-01-15T18:00:00",
  "outcome_prediction": {
    "prediction": "H",
    "confidence": 0.65,
    "confidence_level": "MEDIUM",
    "probabilities": {"H": 0.65, "D": 0.20, "A": 0.15}
  },
  "goal_prediction": {
    "most_likely_score": "2-1",
    "expected_total_goals": 2.8,
    "over_2_5_probability": 0.58,
    "btts_probability": 0.62
  },
  "recommendation": {
    "recommendations": [
      {
        "market": "Match Result",
        "bet": "Home Win",
        "confidence": "MEDIUM",
        "probability": 0.65,
        "risk": "MEDIUM"
      }
    ]
  }
}
```

## 📈 Model Performance

### Expected Accuracy (Realistic)
- **Match Outcome (Win/Draw/Loss)**: 60-65%
- **Over/Under 2.5 Goals**: 55-60%
- **Both Teams To Score**: 60-65%
- **Correct Score**: 10-15%

### Evaluation Metrics
- **Accuracy**: Percentage of correct predictions
- **Log Loss**: Probabilistic performance (lower is better)
- **Precision/Recall**: Per-class performance
- **ROI**: Return on investment for betting strategies

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Leagues (add or remove)
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
    "La Liga": {"id": 140, "country": "Spain"},
    # Add more...
}

# Seasons to train on
SEASONS = list(range(2015, 2024))  # 2015-2023

# Model parameters
MODEL_CONFIG = {
    "test_size": 0.2,
    "cv_folds": 5,
    "n_trials": 100,  # Optuna optimization trials
}

# Prediction thresholds
PREDICTION_CONFIG = {
    "min_confidence": 0.60,
    "high_confidence": 0.75,
}
```

## 🎯 Feature Engineering

### Key Features
1. **Elo Ratings**: Dynamic team strength ratings
2. **Rolling Averages**: Form over last 3, 5, 10 matches
3. **Expected Goals (xG)**: Simplified xG calculation
4. **Head-to-Head**: Historical matchup records
5. **League Position**: Standings-based features
6. **Streaks**: Win/loss sequences
7. **Poisson Probabilities**: Statistical goal modeling

### Feature Importance
Top 10 features typically:
1. Elo Rating Difference
2. Form (last 5 matches)
3. Goals Scored Average
4. Goals Conceded Average
5. Home Advantage
6. League Position Difference
7. H2H Win Rate
8. Expected Goals (xG)
9. Win Streak
10. BTTS Record

## 🧪 Testing & Validation

### Backtesting
```python
from model_training import SoccerPredictionModel
import pandas as pd

# Load test data
test_df = pd.read_csv("data/processed/test_set.csv")

# Evaluate
trainer = SoccerPredictionModel()
# ... load models ...
metrics = trainer.evaluate_model(model, X_test, y_test, "xgboost")
```

### Cross-Validation
```python
cv_results = trainer.cross_validate(X, y, model_type="xgboost")
print(f"CV Accuracy: {cv_results['mean_accuracy']:.4f}")
```

## 📊 Example Predictions

```python
from prediction import MatchPredictor
import joblib

# Load models
models = {"xgboost": joblib.load("models/xgboost_model.pkl")}
predictor = MatchPredictor(models, label_encoder, feature_columns)

# Predict match
prediction = predictor.predict_comprehensive(
    "Arsenal", "Chelsea", match_features
)

# Display
print(predictor.format_prediction_output(prediction))
```

Output:
```
============================================================
MATCH: Arsenal vs Chelsea
============================================================

📊 MATCH RESULT PREDICTION:
   Prediction: H (Home Win)
   Confidence: 68.50% (MEDIUM)

   Probabilities:
      H: 68.50%
      D: 18.20%
      A: 13.30%

⚽ GOALS PREDICTION:
   Expected Total Goals: 2.6
   Most Likely Score: 2-1 (12.40%)
   Over 2.5 Goals: 56.80%
   Both Teams Score: 64.20%

💡 RECOMMENDATIONS:
   [MEDIUM] Match Result: Home Win
      Probability: 68.50%, Risk: MEDIUM
   [MEDIUM] Total Goals: Over 2.5
      Probability: 56.80%, Risk: MEDIUM

⚠️  Only bet what you can afford to lose.
============================================================
```

## ⚙️ System Requirements

### Minimum
- CPU: Dual-core 2.0 GHz
- RAM: 4 GB
- Storage: 5 GB
- Internet: 10 Mbps

### Recommended
- CPU: Quad-core 3.0 GHz (or Apple Silicon M1/M2)
- RAM: 8 GB
- Storage: 20 GB SSD
- Internet: 50 Mbps
- GPU: CUDA-compatible (optional, for faster training)

### Training Time Estimates
- Data Collection: 6-12 hours (depends on API limits)
- Preprocessing: 10-20 minutes
- Feature Engineering: 20-30 minutes
- Model Training: 30-60 minutes (CPU), 10-15 minutes (GPU)

## 🐛 Troubleshooting

### API Rate Limiting
```
ERROR: Rate limit exceeded
```
**Solution**: Reduce `api_rate_limit` in `config.py` or upgrade API plan.

### Missing Data
```
WARNING: No fixtures to process
```
**Solution**: Check API keys, verify league IDs, ensure internet connection.

### Memory Error
```
MemoryError: Unable to allocate array
```
**Solution**: Reduce `SEASONS` range, process fewer leagues, increase RAM.

### Low Accuracy
```
Model accuracy: 45%
```
**Expected**: Soccer is hard to predict! 60-65% is realistic. Check:
- Feature quality
- Data completeness
- League-specific tuning

## 📚 Data Sources

### Recommended APIs
1. **API-Football** (Primary): https://www.api-football.com/
   - Coverage: 1000+ leagues
   - Free tier: 100 requests/day
   - Paid: $15-50/month

2. **Football-Data.org** (Backup): https://www.football-data.org/
   - Coverage: Major leagues
   - Free tier: 10 requests/minute
   - Paid: €5-20/month

3. **StatsBomb** (Advanced xG): https://statsbomb.com/
   - Requires special access
   - Best for xG data

### Alternative Free Sources
- **FBref.com**: Scrapable (check ToS)
- **Understat.com**: xG data
- **FootyStats**: Team statistics

## 🚀 Deployment

### Deploy to Vercel (Serverless)
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod
```

### Deploy to AWS EC2
```bash
# SSH to EC2
ssh -i key.pem ubuntu@ec2-instance

# Setup
git clone <repo>
cd soccer_prediction_bot
pip install -r requirements.txt

# Run API
nohup uvicorn api:app --host 0.0.0.0 --port 8000 &
```

### Docker Deployment
```dockerfile
# Dockerfile
FROM python:3.10

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t soccer-bot .
docker run -p 8000:8000 soccer-bot
```

## 📖 Further Reading

- **Soccer Analytics**: "The Numbers Game" by Anderson & Sally
- **Machine Learning**: "Hands-On Machine Learning" by Aurélien Géron
- **xG Models**: https://fbref.com/en/expected-goals-model-explained/
- **Betting Strategies**: https://www.pinnacle.com/en/betting-articles/educational

## 🤝 Contributing

Contributions welcome! Areas for improvement:
1. Add more leagues
2. Improve xG calculation (use StatsBomb)
3. Add player-level features
4. Implement live prediction updates
5. Build web UI (React/Vue)

## 📄 License

MIT License - See LICENSE file

## 📞 Support

- **Issues**: Open GitHub issue
- **Discussions**: GitHub Discussions
- **Email**: support@example.com

## 🙏 Acknowledgments

- API-Football for data access
- scikit-learn, XGBoost, LightGBM teams
- Soccer analytics community

---

**Remember**: This is an educational project. No prediction system is perfect, and gambling can be harmful. Use responsibly!

**Last Updated**: January 2026
**Version**: 1.0.0
