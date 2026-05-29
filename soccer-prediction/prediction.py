"""
Prediction Module
Makes predictions for upcoming matches with confidence scores
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta

from config import PREDICTION_CONFIG, RESPONSIBLE_BETTING_WARNING
from feature_engineering import FeatureEngineer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MatchPredictor:
    """
    Makes predictions for soccer matches
    """

    def __init__(self, models: Dict, label_encoder, feature_columns: List[str]):
        self.models = models
        self.label_encoder = label_encoder
        self.feature_columns = feature_columns
        self.feature_engineer = FeatureEngineer()

    def predict_match(
        self,
        match_features: pd.DataFrame,
        return_probabilities: bool = True,
    ) -> Dict:
        """
        Predict outcome for a single match
        
        Args:
            match_features: DataFrame with match features
            return_probabilities: Whether to return class probabilities
            
        Returns:
            Dictionary with predictions and confidence
        """
        # Ensure features are in correct order
        X = match_features[self.feature_columns]

        # Handle missing values
        X = X.fillna(X.mean())

        # Get predictions from each model
        predictions = {}
        probabilities = {}

        for model_name, model in self.models.items():
            pred_proba = model.predict_proba(X)[0]
            pred_class = np.argmax(pred_proba)

            predictions[model_name] = self.label_encoder.inverse_transform([pred_class])[0]
            probabilities[model_name] = {
                self.label_encoder.classes_[i]: float(prob)
                for i, prob in enumerate(pred_proba)
            }

        # Ensemble prediction (average probabilities)
        ensemble_proba = np.mean(
            [model.predict_proba(X)[0] for model in self.models.values()],
            axis=0,
        )

        ensemble_pred_class = np.argmax(ensemble_proba)
        ensemble_pred = self.label_encoder.inverse_transform([ensemble_pred_class])[0]

        ensemble_probabilities = {
            self.label_encoder.classes_[i]: float(prob)
            for i, prob in enumerate(ensemble_proba)
        }

        # Confidence score (highest probability)
        confidence = float(np.max(ensemble_proba))

        # Determine confidence level
        if confidence >= PREDICTION_CONFIG["high_confidence"]:
            confidence_level = "HIGH"
        elif confidence >= PREDICTION_CONFIG["min_confidence"]:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        result = {
            "prediction": ensemble_pred,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "probabilities": ensemble_probabilities,
            "individual_predictions": predictions,
            "individual_probabilities": probabilities,
        }

        return result

    def predict_goals(
        self, home_xG: float, away_xG: float, match_features: pd.DataFrame
    ) -> Dict:
        """
        Predict goal-related outcomes (total goals, over/under, correct score)
        
        Uses Poisson distribution based on xG
        """
        from scipy.stats import poisson

        max_goals = 10

        # Build probability matrix
        prob_matrix = np.zeros((max_goals, max_goals))
        for home_goals in range(max_goals):
            for away_goals in range(max_goals):
                prob_matrix[home_goals, away_goals] = (
                    poisson.pmf(home_goals, home_xG) * poisson.pmf(away_goals, away_xG)
                )

        # Most likely score
        most_likely_idx = np.unravel_index(np.argmax(prob_matrix), prob_matrix.shape)
        most_likely_score = f"{most_likely_idx[0]}-{most_likely_idx[1]}"
        most_likely_prob = float(prob_matrix[most_likely_idx])

        # Over/Under 2.5 goals
        over_2_5_prob = 0
        under_2_5_prob = 0
        for i in range(max_goals):
            for j in range(max_goals):
                if i + j > 2.5:
                    over_2_5_prob += prob_matrix[i, j]
                else:
                    under_2_5_prob += prob_matrix[i, j]

        # Both teams to score
        btts_prob = 1 - (poisson.pmf(0, home_xG) + poisson.pmf(0, away_xG) - 
                         poisson.pmf(0, home_xG) * poisson.pmf(0, away_xG))

        # Expected total goals
        expected_total_goals = home_xG + away_xG

        # Top 5 most likely scores
        flat_probs = prob_matrix.flatten()
        top_5_indices = np.argsort(flat_probs)[-5:][::-1]
        top_scores = []

        for idx in top_5_indices:
            home_g, away_g = np.unravel_index(idx, prob_matrix.shape)
            top_scores.append({
                "score": f"{home_g}-{away_g}",
                "probability": float(prob_matrix[home_g, away_g]),
            })

        result = {
            "most_likely_score": most_likely_score,
            "most_likely_score_probability": most_likely_prob,
            "expected_total_goals": round(expected_total_goals, 2),
            "over_2_5_probability": float(over_2_5_prob),
            "under_2_5_probability": float(under_2_5_prob),
            "btts_probability": float(btts_prob),
            "top_5_scores": top_scores,
        }

        return result

    def predict_comprehensive(
        self,
        home_team_name: str,
        away_team_name: str,
        match_features: pd.DataFrame,
        home_xG: float = None,
        away_xG: float = None,
    ) -> Dict:
        """
        Comprehensive prediction including outcome, goals, and recommendations
        """
        logger.info(f"Predicting: {home_team_name} vs {away_team_name}")

        # Outcome prediction
        outcome_pred = self.predict_match(match_features)

        # Goal prediction (use xG from features if not provided)
        if home_xG is None or away_xG is None:
            if "home_xG_simple" in match_features.columns:
                home_xG = match_features["home_xG_simple"].values[0]
                away_xG = match_features["away_xG_simple"].values[0]
            else:
                home_xG, away_xG = 1.5, 1.2  # Default fallback

        goal_pred = self.predict_goals(home_xG, away_xG, match_features)

        # Build comprehensive result
        result = {
            "match": f"{home_team_name} vs {away_team_name}",
            "timestamp": datetime.now().isoformat(),
            "outcome_prediction": {
                "prediction": outcome_pred["prediction"],
                "confidence": outcome_pred["confidence"],
                "confidence_level": outcome_pred["confidence_level"],
                "probabilities": outcome_pred["probabilities"],
            },
            "goal_prediction": goal_pred,
            "recommendation": self._generate_recommendation(outcome_pred, goal_pred),
            "warning": RESPONSIBLE_BETTING_WARNING,
        }

        return result

    def _generate_recommendation(
        self, outcome_pred: Dict, goal_pred: Dict
    ) -> Dict:
        """
        Generate betting recommendations with risk assessment
        """
        confidence = outcome_pred["confidence"]
        prediction = outcome_pred["prediction"]
        probabilities = outcome_pred["probabilities"]

        recommendations = []

        # Outcome recommendation
        if confidence >= PREDICTION_CONFIG["high_confidence"]:
            recommendations.append({
                "market": "Match Result",
                "bet": prediction,
                "confidence": "HIGH",
                "probability": probabilities[prediction],
                "risk": "LOW",
            })
        elif confidence >= PREDICTION_CONFIG["min_confidence"]:
            recommendations.append({
                "market": "Match Result",
                "bet": prediction,
                "confidence": "MEDIUM",
                "probability": probabilities[prediction],
                "risk": "MEDIUM",
            })

        # Over/Under recommendation
        over_prob = goal_pred["over_2_5_probability"]
        under_prob = goal_pred["under_2_5_probability"]

        if over_prob > 0.65:
            recommendations.append({
                "market": "Total Goals",
                "bet": "Over 2.5",
                "confidence": "HIGH" if over_prob > 0.75 else "MEDIUM",
                "probability": over_prob,
                "risk": "LOW" if over_prob > 0.75 else "MEDIUM",
            })
        elif under_prob > 0.65:
            recommendations.append({
                "market": "Total Goals",
                "bet": "Under 2.5",
                "confidence": "HIGH" if under_prob > 0.75 else "MEDIUM",
                "probability": under_prob,
                "risk": "LOW" if under_prob > 0.75 else "MEDIUM",
            })

        # BTTS recommendation
        btts_prob = goal_pred["btts_probability"]
        if btts_prob > 0.65:
            recommendations.append({
                "market": "Both Teams To Score",
                "bet": "Yes",
                "confidence": "HIGH" if btts_prob > 0.75 else "MEDIUM",
                "probability": btts_prob,
                "risk": "LOW" if btts_prob > 0.75 else "MEDIUM",
            })
        elif btts_prob < 0.35:
            recommendations.append({
                "market": "Both Teams To Score",
                "bet": "No",
                "confidence": "HIGH" if btts_prob < 0.25 else "MEDIUM",
                "probability": 1 - btts_prob,
                "risk": "LOW" if btts_prob < 0.25 else "MEDIUM",
            })

        # Correct score (only if high confidence)
        most_likely_score = goal_pred["most_likely_score"]
        score_prob = goal_pred["most_likely_score_probability"]

        if score_prob > 0.15:  # Correct score is hard to predict
            recommendations.append({
                "market": "Correct Score",
                "bet": most_likely_score,
                "confidence": "MEDIUM",
                "probability": score_prob,
                "risk": "HIGH",  # Correct score always risky
            })

        return {
            "recommendations": recommendations,
            "overall_confidence": confidence,
            "note": "Only bet what you can afford to lose. Past performance doesn't guarantee future results.",
        }

    def batch_predict(
        self, matches_df: pd.DataFrame
    ) -> List[Dict]:
        """
        Predict multiple matches at once
        """
        predictions = []

        for idx, row in matches_df.iterrows():
            try:
                # Extract match info
                home_team = row.get("home_team_name", "Home Team")
                away_team = row.get("away_team_name", "Away Team")

                # Create single-row DataFrame for prediction
                match_features = matches_df.iloc[[idx]]

                # Get xG if available
                home_xG = row.get("home_xG_simple", 1.5)
                away_xG = row.get("away_xG_simple", 1.2)

                # Predict
                pred = self.predict_comprehensive(
                    home_team, away_team, match_features, home_xG, away_xG
                )

                predictions.append(pred)

            except Exception as e:
                logger.error(f"Error predicting match {idx}: {e}")
                continue

        logger.info(f"Batch prediction complete: {len(predictions)} matches")
        return predictions

    def format_prediction_output(self, prediction: Dict) -> str:
        """
        Format prediction for human-readable output
        """
        output = []
        output.append("=" * 60)
        output.append(f"MATCH: {prediction['match']}")
        output.append("=" * 60)

        # Outcome
        outcome = prediction["outcome_prediction"]
        output.append(f"\n📊 MATCH RESULT PREDICTION:")
        output.append(f"   Prediction: {outcome['prediction']}")
        output.append(f"   Confidence: {outcome['confidence']:.2%} ({outcome['confidence_level']})")
        output.append(f"\n   Probabilities:")
        for result, prob in outcome['probabilities'].items():
            output.append(f"      {result}: {prob:.2%}")

        # Goals
        goals = prediction["goal_prediction"]
        output.append(f"\n⚽ GOALS PREDICTION:")
        output.append(f"   Expected Total Goals: {goals['expected_total_goals']}")
        output.append(f"   Most Likely Score: {goals['most_likely_score']} ({goals['most_likely_score_probability']:.2%})")
        output.append(f"   Over 2.5 Goals: {goals['over_2_5_probability']:.2%}")
        output.append(f"   Under 2.5 Goals: {goals['under_2_5_probability']:.2%}")
        output.append(f"   Both Teams Score: {goals['btts_probability']:.2%}")

        # Recommendations
        rec = prediction["recommendation"]
        output.append(f"\n💡 RECOMMENDATIONS:")
        for r in rec['recommendations']:
            output.append(f"   [{r['confidence']}] {r['market']}: {r['bet']}")
            output.append(f"      Probability: {r['probability']:.2%}, Risk: {r['risk']}")

        output.append(f"\n⚠️  {rec['note']}")
        output.append("=" * 60)

        return "\n".join(output)


# Example usage
if __name__ == "__main__":
    import joblib
    from config import MODELS_DIR, PROCESSED_DATA_DIR, LEAGUES

    # Load models (use actual paths)
    # models = {"xgboost": joblib.load("models/xgboost_model.pkl")}
    # label_encoder = joblib.load("models/label_encoder.pkl")
    # feature_columns = json.load(open("models/feature_columns.json"))

    # predictor = MatchPredictor(models, label_encoder, feature_columns)

    # Load test data
    league_id = LEAGUES["Premier League"]["id"]
    df = pd.read_csv(f"{PROCESSED_DATA_DIR}/league_{league_id}_featured_2023.csv")

    # Get last match as example
    last_match = df.iloc[[-1]]

    print("Prediction example (requires trained models):")
    print(f"Match: {last_match['home_team_name'].values[0]} vs {last_match['away_team_name'].values[0]}")
    print(f"Actual result: {last_match['outcome'].values[0]}")
    print("\n[Note: Load actual trained models to see predictions]")
