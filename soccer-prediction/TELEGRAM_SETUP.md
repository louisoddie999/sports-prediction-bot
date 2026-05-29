# 🤖 Telegram Integration Guide

## ✅ Step 1: Create Your Telegram Bot

1. Open Telegram app
2. Search for **@BotFather**
3. Send `/start` to BotFather
4. Send `/newbot` to create a new bot
5. Follow the prompts:
   - Choose a name (e.g., "My Soccer Predictions")
   - Choose a username (must end in 'bot', e.g., "my_soccer_predictions_bot")
6. **Save the token** BotFather gives you (looks like: `123456789:ABCdefGHI...`)

## ✅ Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send `/start` to it
3. It will reply with your **Chat ID** (a number like: `123456789`)
4. **Save this Chat ID**

## ✅ Step 3: Configure the Bot

### Option A: Edit config.py directly

Open `C:\Users\FX\soccer_prediction_bot\config.py` and add these lines after line 22:

```python
# Telegram Configuration
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with token from BotFather
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"  # Replace with ID from userinfobot
TELEGRAM_ENABLED = True  # Set to True to enable notifications
```

### Option B: Use environment variables

Create a `.env` file in `C:\Users\FX\soccer_prediction_bot\` with:

```
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE
```

Then in config.py:
```python
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_ENABLED = True
```

## ✅ Step 4: Test Connection

```cmd
cd C:\Users\FX\soccer_prediction_bot
py telegram_notifier.py
```

You should receive a test message on Telegram!

## 📱 How to Use

### Send Predictions to Telegram

```python
from telegram_notifier import TelegramNotifier
from prediction import MatchPredictor

# Initialize
notifier = TelegramNotifier()

# Make prediction
prediction = predictor.predict_comprehensive(
    "Arsenal", "Chelsea", match_features
)

# Send to Telegram
notifier.send_prediction(prediction)
```

### Send Batch Predictions

```python
# Get all today's matches
predictions = predictor.batch_predict(matches_df)

# Send summary to Telegram
notifier.send_batch_predictions(predictions)
```

### Send Custom Alerts

```python
notifier.send_alert(
    title="High Confidence Match!",
    message="Manchester United vs Liverpool\nHome Win: 78% confidence",
    alert_level="SUCCESS"
)
```

## 🎯 Automatic Notifications

The bot will automatically send Telegram notifications when:

1. **Predictions are ready** (before matches)
2. **High confidence matches** detected (>75%)
3. **Value bets** found
4. **Errors or warnings** occur

## 📊 Message Format

Telegram messages include:

- ⚽ Match information
- 📊 Outcome predictions with confidence
- 💯 Probability breakdown
- ⚽ Goals predictions (O/U, BTTS, correct score)
- 💡 Betting recommendations
- ⚠️ Risk assessment and warnings

## 🔧 Customization

Edit `telegram_notifier.py` to customize:

- Message format
- Emoji usage
- Notification frequency
- Alert thresholds

## 🐛 Troubleshooting

### "Bot not initialized"
- Check your bot token is correct
- Make sure token has no extra spaces
- Token should look like: `1234567890:ABCdefGHI...`

### "Chat ID error"
- Verify Chat ID is a number
- Start your bot first: Send `/start` to your bot on Telegram
- Then try sending message again

### "Telegram module not found"
```cmd
py -m pip install python-telegram-bot
```

### Messages not arriving
1. Make sure you've sent `/start` to your bot on Telegram
2. Check bot token and chat ID are correct
3. Verify `TELEGRAM_ENABLED = True` in config.py

## 📖 Example: Complete Workflow

```python
from prediction import MatchPredictor
from telegram_notifier import TelegramNotifier
import joblib

# 1. Load models
models = {"xgboost": joblib.load("models/xgboost_model.pkl")}
predictor = MatchPredictor(models, label_encoder, features)

# 2. Initialize Telegram
notifier = TelegramNotifier()

# 3. Make prediction
prediction = predictor.predict_comprehensive(
    "Manchester United",
    "Liverpool", 
    match_features
)

# 4. Send to Telegram
if notifier.send_prediction(prediction):
    print("✅ Sent to Telegram!")
else:
    print("❌ Failed to send")
```

## 🚀 Integration with Main Pipeline

The main prediction pipeline already includes Telegram support:

```cmd
# Run predictions and auto-send to Telegram
py main.py --step predict --telegram
```

## 💡 Tips

1. **Test first**: Run `py telegram_notifier.py` before using in production
2. **Limit notifications**: Don't spam yourself with too many messages
3. **High confidence only**: Set threshold to send only important predictions
4. **Schedule smartly**: Send morning summaries, not individual match notifications
5. **Keep secure**: Never share your bot token publicly

## 🔐 Security

- **Keep your bot token secret** - it's like a password
- Don't share your token in GitHub or public places
- Use environment variables or .env file
- Add `.env` to `.gitignore` if using version control

## 📞 Support

If you have issues:
1. Check Telegram API status: https://telegram.org/status
2. Verify bot token at @BotFather
3. Test with `py telegram_notifier.py`
4. Check logs in `logs/bot.log`

---

**Ready to use! Now your predictions will be sent directly to your Telegram! ⚽📱**
