# Soccer Prediction Bot - Quick Start Guide

## Prerequisites
- Python 3.8+
- API-Football key: https://www.api-football.com/
- 4GB RAM, 5GB disk space

## Installation (5 minutes)

```bash
# 1. Navigate to project folder
cd C:\Users\FX\soccer_prediction_bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
echo API_FOOTBALL_KEY=your_key_here > .env
```

## Quick Demo (No API Key Required)

```bash
# Run with mock data
python demo.py
```

## Full Pipeline (Requires API Key)

### Option A: Automated (Recommended)
```bash
python main.py --step full --api-key YOUR_KEY
```
⏱️ Time: 8-12 hours (includes data collection)

### Option B: Step-by-Step
```bash
# Step 1: Collect data (6-10 hours)
python main.py --step collect --api-key YOUR_KEY

# Step 2: Preprocess (10 min)
python main.py --step preprocess

# Step 3: Feature engineering (20 min)
python main.py --step features

# Step 4: Train models (45 min)
python main.py --step train

# Step 5: Make predictions
python main.py --step predict
```

## Start API Server

```bash
uvicorn api:app --reload
```

Then open: http://localhost:8000/docs

## Test Prediction

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Manchester United",
    "away_team": "Liverpool",
    "league": "Premier League"
  }'
```

## Common Issues

### 1. API Rate Limit
**Error**: `Rate limit exceeded`
**Fix**: Wait 1 hour or reduce `api_rate_limit` in `config.py`

### 2. Missing Models
**Error**: `Models not loaded`
**Fix**: Run `python main.py --step train` first

### 3. Import Errors
**Error**: `ModuleNotFoundError`
**Fix**: `pip install -r requirements.txt`

## File Overview

- `main.py` - Run pipeline
- `api.py` - Web API
- `config.py` - Settings
- `data_collection.py` - Fetch data
- `model_training.py` - Train models
- `prediction.py` - Make predictions

## Expected Results

### Model Accuracy (Realistic)
- Match Outcome: 60-65% ✅
- Over/Under: 55-60% ✅
- Correct Score: 10-15% ⚠️

**Note**: 95%+ accuracy is impossible in soccer prediction!

## Next Steps

1. ✅ Complete Quick Demo
2. ✅ Get API key
3. ✅ Run full pipeline
4. ✅ Start API server
5. ✅ Make predictions
6. 📊 Analyze results
7. 🚀 Deploy (optional)

## Help & Support

- Documentation: `README.md`
- Issues: GitHub Issues
- API Docs: http://localhost:8000/docs (when running)

## Key Commands

```bash
# Full pipeline
python main.py --step full

# Just training
python main.py --step train

# Start API
uvicorn api:app --reload

# Run tests
pytest tests/

# Check health
curl http://localhost:8000/health
```

## Resource Requirements

| Task | Time | API Calls | RAM |
|------|------|-----------|-----|
| Data Collection | 8-10h | 5000+ | 2GB |
| Preprocessing | 10min | 0 | 2GB |
| Training | 45min | 0 | 4GB |
| Prediction | <1s | 0 | 1GB |

## Tips for Success

1. **Start Small**: Test with 1 league & 2 seasons first
2. **Check Data**: Verify CSV files in `data/processed/`
3. **Monitor Logs**: Check `logs/bot.log` for errors
4. **Be Patient**: Data collection takes hours
5. **Realistic Expectations**: Aim for 60-65%, not 95%

## Example Output

```
============================================================
MATCH: Arsenal vs Chelsea
============================================================

📊 MATCH RESULT PREDICTION:
   Prediction: H (Home Win)
   Confidence: 68.50% (MEDIUM)

⚽ GOALS PREDICTION:
   Expected Total Goals: 2.6
   Most Likely Score: 2-1 (12.40%)

💡 RECOMMENDATIONS:
   [MEDIUM] Match Result: Home Win (68.5%)
   [MEDIUM] Over 2.5 Goals (56.8%)

⚠️  Only bet what you can afford to lose!
============================================================
```

## Configuration Tips

Edit `config.py`:

```python
# Reduce seasons for faster testing
SEASONS = [2022, 2023]  # Instead of 2015-2023

# Reduce leagues
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
}

# Lower API rate
REALTIME_CONFIG = {
    "api_rate_limit": 10,  # Requests per minute
}
```

## Deployment Options

1. **Local**: Run on your machine
2. **Vercel**: Serverless deployment
3. **AWS EC2**: Cloud server
4. **Docker**: Containerized deployment
5. **Heroku**: Free tier (limited)

---

**Ready to start? Run:**
```bash
python main.py --step full --api-key YOUR_KEY
```

**Need help? Check** `README.md` **or open an issue!**
