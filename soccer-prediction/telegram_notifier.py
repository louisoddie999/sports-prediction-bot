"""
Telegram Notification Module
Sends predictions and updates to Telegram
"""

import logging
from typing import Dict, List, Optional
from telegram import Bot
from telegram.error import TelegramError
import asyncio

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends notifications to Telegram
    """

    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        Initialize Telegram bot
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Your Telegram chat ID
        """
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram bot token not configured")
            self.bot = None
        else:
            try:
                self.bot = Bot(token=self.bot_token)
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                self.bot = None

    async def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to Telegram
        
        Args:
            message: Message text
            parse_mode: Formatting mode (Markdown or HTML)
            
        Returns:
            True if sent successfully
        """
        if not self.bot or not self.chat_id:
            logger.warning("Telegram not configured, skipping notification")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info("Message sent to Telegram")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_message_sync(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Synchronous wrapper for send_message
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_message(message, parse_mode))

    def format_prediction(self, prediction: Dict) -> str:
        """
        Format prediction for Telegram message
        
        Args:
            prediction: Prediction dictionary from MatchPredictor
            
        Returns:
            Formatted message string
        """
        match = prediction["match"]
        outcome = prediction["outcome_prediction"]
        goals = prediction["goal_prediction"]
        rec = prediction["recommendation"]

        # Build message with emojis
        message = f"⚽ *SOCCER PREDICTION* ⚽\n\n"
        message += f"🏟️ *{match}*\n"
        message += f"━━━━━━━━━━━━━━━━━━━━\n\n"

        # Outcome prediction
        outcome_emoji = "🏠" if outcome["prediction"] == "H" else "🤝" if outcome["prediction"] == "D" else "✈️"
        outcome_text = "Home Win" if outcome["prediction"] == "H" else "Draw" if outcome["prediction"] == "D" else "Away Win"
        
        message += f"📊 *MATCH RESULT*\n"
        message += f"{outcome_emoji} *Prediction: {outcome_text}*\n"
        message += f"💯 Confidence: *{outcome['confidence']:.1%}* ({outcome['confidence_level']})\n\n"
        
        message += f"*Probabilities:*\n"
        message += f"   🏠 Home: {outcome['probabilities']['H']:.1%}\n"
        message += f"   🤝 Draw: {outcome['probabilities']['D']:.1%}\n"
        message += f"   ✈️ Away: {outcome['probabilities']['A']:.1%}\n\n"

        # Goals prediction
        message += f"⚽ *GOALS PREDICTION*\n"
        message += f"📊 Expected Goals: *{goals['expected_total_goals']:.1f}*\n"
        message += f"🎯 Most Likely Score: *{goals['most_likely_score']}* ({goals['most_likely_score_probability']:.1%})\n"
        message += f"📈 Over 2.5: {goals['over_2_5_probability']:.1%}\n"
        message += f"📉 Under 2.5: {goals['under_2_5_probability']:.1%}\n"
        message += f"⚽⚽ BTTS: {goals['btts_probability']:.1%}\n\n"

        # Recommendations
        if rec["recommendations"]:
            message += f"💡 *RECOMMENDATIONS*\n"
            for r in rec["recommendations"][:3]:  # Top 3
                confidence_emoji = "🟢" if r['confidence'] == "HIGH" else "🟡" if r['confidence'] == "MEDIUM" else "🔴"
                message += f"{confidence_emoji} *{r['market']}*: {r['bet']}\n"
                message += f"   📊 {r['probability']:.1%} | Risk: {r['risk']}\n"
            message += "\n"

        # Warning
        message += f"⚠️ *DISCLAIMER*\n"
        message += f"Educational purposes only. No guarantees.\n"
        message += f"Only bet what you can afford to lose.\n"
        
        return message

    def send_prediction(self, prediction: Dict) -> bool:
        """
        Send formatted prediction to Telegram
        """
        message = self.format_prediction(prediction)
        return self.send_message_sync(message)

    def send_batch_predictions(self, predictions: List[Dict]) -> bool:
        """
        Send multiple predictions to Telegram
        """
        if not predictions:
            return False

        summary = f"📊 *DAILY PREDICTIONS* ({len(predictions)} matches)\n"
        summary += f"{'='*30}\n\n"

        for i, pred in enumerate(predictions[:10], 1):  # Limit to 10
            match = pred["match"]
            outcome = pred["outcome_prediction"]
            outcome_text = "H" if outcome["prediction"] == "H" else "D" if outcome["prediction"] == "D" else "A"
            
            summary += f"{i}. *{match}*\n"
            summary += f"   Prediction: {outcome_text} ({outcome['confidence']:.0%})\n\n"

        if len(predictions) > 10:
            summary += f"_...and {len(predictions) - 10} more matches_\n"

        return self.send_message_sync(summary)

    def send_alert(self, title: str, message: str, alert_level: str = "INFO") -> bool:
        """
        Send alert notification
        
        Args:
            title: Alert title
            message: Alert message
            alert_level: INFO, WARNING, ERROR
        """
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }

        emoji = emoji_map.get(alert_level, "ℹ️")
        formatted = f"{emoji} *{title}*\n\n{message}"
        
        return self.send_message_sync(formatted)

    def test_connection(self) -> bool:
        """
        Test Telegram connection
        """
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _test():
            try:
                bot_info = await self.bot.get_me()
                test_message = f"✅ Bot Connected!\n\nBot Name: {bot_info.first_name}\nUsername: @{bot_info.username}"
                await self.send_message(test_message)
                return True
            except Exception as e:
                logger.error(f"Connection test failed: {e}")
                return False

        return loop.run_until_complete(_test())


# Example usage
if __name__ == "__main__":
    # Test notification
    notifier = TelegramNotifier()

    # Test connection
    print("Testing Telegram connection...")
    if notifier.test_connection():
        print("✅ Telegram connected!")
        
        # Send test prediction
        test_prediction = {
            "match": "Manchester United vs Liverpool",
            "outcome_prediction": {
                "prediction": "H",
                "confidence": 0.68,
                "confidence_level": "MEDIUM",
                "probabilities": {"H": 0.68, "D": 0.18, "A": 0.14}
            },
            "goal_prediction": {
                "expected_total_goals": 2.6,
                "most_likely_score": "2-1",
                "most_likely_score_probability": 0.124,
                "over_2_5_probability": 0.568,
                "under_2_5_probability": 0.432,
                "btts_probability": 0.642,
            },
            "recommendation": {
                "recommendations": [
                    {
                        "market": "Match Result",
                        "bet": "Home Win",
                        "confidence": "MEDIUM",
                        "probability": 0.68,
                        "risk": "MEDIUM"
                    },
                    {
                        "market": "Over/Under",
                        "bet": "Over 2.5",
                        "confidence": "MEDIUM",
                        "probability": 0.568,
                        "risk": "MEDIUM"
                    }
                ]
            }
        }

        print("\nSending test prediction...")
        notifier.send_prediction(test_prediction)
        print("✅ Test prediction sent!")
    else:
        print("❌ Telegram not configured")
        print("\nTo configure:")
        print("1. Create bot with @BotFather on Telegram")
        print("2. Get your chat ID from @userinfobot")
        print("3. Add to config.py:")
        print("   TELEGRAM_BOT_TOKEN = 'your_bot_token'")
        print("   TELEGRAM_CHAT_ID = 'your_chat_id'")
