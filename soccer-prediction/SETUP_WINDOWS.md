# Soccer Prediction Bot - Complete Windows Setup Guide

## Step 1: Install Python (Required)

### Option A: Download from Python.org (Recommended)
1. Go to: https://www.python.org/downloads/
2. Click "Download Python 3.11.x" (latest version)
3. Run the installer
4. ⚠️ **IMPORTANT**: Check "Add Python to PATH" during installation
5. Click "Install Now"
6. Verify installation:
   ```cmd
   python --version
   ```

### Option B: Install via Microsoft Store
1. Open Microsoft Store
2. Search "Python 3.11"
3. Click "Get" to install
4. Verify:
   ```cmd
   python --version
   ```

### Option C: Install via Chocolatey (if you have it)
```cmd
choco install python
```

---

## Step 2: Install Dependencies

After Python is installed:

```cmd
cd C:\Users\FX\soccer_prediction_bot
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Expected time**: 5-10 minutes

---

## Step 3: Quick Demo (No API Key Needed)

Test the system with mock data:

```cmd
python demo.py
```

This will:
- Generate 100 mock matches
- Train a simple model
- Make demo predictions
- Show feature engineering concepts

---

## Step 4: Get API Keys (For Real Data)

### API-Football (Primary)
1. Go to: https://www.api-football.com/
2. Sign up for free account
3. Get API key from dashboard
4. Free tier: 100 requests/day

### Football-Data.org (Backup)
1. Go to: https://www.football-data.org/client/register
2. Register for free account
3. Get API token
4. Free tier: 10 requests/minute

---

## Step 5: Configure API Keys

Create `.env` file in `C:\Users\FX\soccer_prediction_bot\`:

```env
API_FOOTBALL_KEY=your_api_football_key_here
FOOTBALL_DATA_KEY=your_football_data_key_here
```

Or edit `config.py` directly:
```python
API_FOOTBALL_KEY = "your_key_here"
```

---

## Step 6: Run Full Pipeline

### Quick Test (1 league, 1 season)
Edit `config.py`:
```python
LEAGUES = {
    "Premier League": {"id": 39, "country": "England"},
}
SEASONS = [2023]  # Just 2023 season
```

Then run:
```cmd
python main.py --step train
```

### Full Pipeline (All leagues, all seasons)
⚠️ **WARNING**: Takes 8-12 hours and uses 5000+ API calls

```cmd
python main.py --step full
```

---

## Step 7: Start API Server

```cmd
python -m uvicorn api:app --reload
```

Then open: http://localhost:8000/docs

---

## Step 8: Make Predictions

### Via API
```cmd
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"home_team\":\"Manchester United\",\"away_team\":\"Liverpool\",\"league\":\"Premier League\"}"
```

### Via Python Script
```python
from prediction import MatchPredictor
import joblib

# Load models
models = {"xgboost": joblib.load("models/xgboost_model.pkl")}
predictor = MatchPredictor(models, label_encoder, feature_columns)

# Predict
prediction = predictor.predict_comprehensive("Arsenal", "Chelsea", features)
print(predictor.format_prediction_output(prediction))
```

---

## Common Issues & Fixes

### 1. Python Not Found
**Error**: `'python' is not recognized`
**Fix**: 
- Reinstall Python with "Add to PATH" checked
- Or use full path: `C:\Python311\python.exe`
- Or restart computer after installation

### 2. Pip Not Found
**Error**: `'pip' is not recognized`
**Fix**:
```cmd
python -m ensurepip --upgrade
python -m pip --version
```

### 3. Permission Denied
**Error**: `Access is denied`
**Fix**: Run Command Prompt as Administrator

### 4. Module Not Found
**Error**: `ModuleNotFoundError: No module named 'pandas'`
**Fix**:
```cmd
python -m pip install pandas numpy scikit-learn xgboost
```

### 5. API Rate Limit
**Error**: `Rate limit exceeded`
**Fix**: 
- Wait 1 hour
- Or reduce `api_rate_limit` in `config.py` to 5-10

### 6. Out of Memory
**Error**: `MemoryError`
**Fix**: 
- Reduce `SEASONS` to 1-2 years
- Close other applications
- Process one league at a time

---

## Alternative: Use Google Colab (No Installation)

If you can't install Python locally, use Google Colab:

1. Go to: https://colab.research.google.com/
2. Upload all `.py` files
3. Install dependencies:
   ```python
   !pip install pandas numpy scikit-learn xgboost lightgbm
   ```
4. Run scripts in notebook cells

---

## System Requirements

### Minimum
- Windows 10/11
- Python 3.8+
- 4GB RAM
- 5GB free disk space
- Internet connection

### Recommended
- Windows 11
- Python 3.10 or 3.11
- 8GB RAM
- 20GB free disk space
- Fast internet (50+ Mbps)

---

## Quick Commands Reference

```cmd
# Check Python
python --version

# Install dependencies
python -m pip install -r requirements.txt

# Run demo
python demo.py

# Run full pipeline
python main.py --step full

# Start API
python -m uvicorn api:app --reload

# Run specific step
python main.py --step train

# Check API health
curl http://localhost:8000/health
```

---

## Project Structure

```
soccer_prediction_bot/
├── api.py                     # Web API (FastAPI)
├── config.py                  # Configuration
├── data_collection.py         # Fetch data from APIs
├── data_preprocessing.py      # Clean data
├── feature_engineering.py     # Create features
├── model_training.py          # Train models
├── prediction.py              # Make predictions
├── main.py                    # Main pipeline
├── demo.py                    # Demo with mock data
├── requirements.txt           # Dependencies
├── README.md                  # Full documentation
├── QUICKSTART.md              # Quick start guide
├── SETUP_WINDOWS.md           # This file
├── data/                      # Data folder (created automatically)
│   ├── raw/                   # Raw API data
│   └── processed/             # Processed data
├── models/                    # Trained models (created automatically)
└── logs/                      # Log files (created automatically)
```

---

## Expected Timeline

| Step | Time | Requirements |
|------|------|--------------|
| Install Python | 5 min | Internet |
| Install dependencies | 10 min | Internet |
| Run demo | 2 min | None |
| Get API keys | 5 min | Email |
| Collect data (1 league, 1 season) | 30 min | API key |
| Collect data (all leagues, 8 years) | 8-12 hours | API key |
| Preprocess data | 10 min | Collected data |
| Feature engineering | 20 min | Preprocessed data |
| Train models | 45 min | Features |
| Make predictions | <1 sec | Trained models |

**Total (full pipeline)**: 10-14 hours

---

## Resource Usage

### API Calls (Free Tier Limits)
- **API-Football**: 100/day (collect 1 league/season per day)
- **Football-Data.org**: 10/minute (slower but more sustainable)

### Disk Space
- Raw data: 500MB - 2GB
- Processed data: 200MB - 1GB
- Models: 50MB - 200MB
- Logs: 10MB - 50MB
- **Total**: ~5GB recommended

### RAM Usage
- Data collection: 1-2GB
- Preprocessing: 2-3GB
- Training: 3-5GB
- Prediction: 500MB - 1GB
- API server: 500MB

---

## Next Steps After Setup

1. ✅ Install Python
2. ✅ Install dependencies
3. ✅ Run demo to verify setup
4. ✅ Get API keys
5. ✅ Start with 1 league & 1 season
6. ✅ Train models
7. ✅ Test predictions
8. 📊 Evaluate accuracy
9. 🚀 Deploy API (optional)
10. 💰 Use responsibly (never bet more than you can afford!)

---

## Getting Help

### Issues with Installation
- Check Python is in PATH: `echo %PATH%`
- Use Python Launcher: `py --version` instead of `python`
- Reinstall Python with "Add to PATH" option

### Issues with Code
- Check logs in `logs/bot.log`
- Enable debug mode in `config.py`: `LOGGING_CONFIG["level"] = "DEBUG"`
- Open GitHub issue with error message

### Issues with Data
- Verify API keys are correct
- Check API rate limits
- Try alternative data source

### Issues with Accuracy
- This is normal! Soccer is hard to predict
- 60-65% accuracy is excellent
- 95%+ is impossible

---

## Final Notes

**This bot is for educational purposes only.**

- No prediction system guarantees profits
- Soccer has inherent randomness
- Always bet responsibly
- Seek help if gambling becomes a problem

**Realistic Expectations:**
- Match outcome: 60-65% accuracy ✅
- Over/Under: 55-60% accuracy ✅
- Correct score: 10-15% accuracy ⚠️

**Good luck, and enjoy learning about sports analytics!** 🎯⚽

---

**Version**: 1.0  
**Last Updated**: January 2026  
**Support**: Check README.md or open GitHub issue
