"""
Demo Script - Test the Soccer Prediction Bot without API keys
Uses mock data to demonstrate functionality
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_mock_data():
    """
    Generate mock soccer data for demonstration
    """
    logger.info("Generating mock data...")

    # Create mock matches
    np.random.seed(42)
    n_matches = 100

    teams = [
        "Manchester United", "Liverpool", "Arsenal", "Chelsea",
        "Manchester City", "Tottenham", "Leicester", "West Ham",
        "Everton", "Newcastle", "Aston Villa", "Brighton",
    ]

    matches = []
    for i in range(n_matches):
        home_team = np.random.choice(teams)
        away_team = np.random.choice([t for t in teams if t != home_team])

        # Simulate match features
        home_elo = np.random.normal(1500, 200)
        away_elo = np.random.normal(1500, 200)

        # Outcome based on Elo difference (with randomness)
        elo_diff = home_elo - away_elo
        home_win_prob = 1 / (1 + 10 ** (-elo_diff / 400))

        rand = np.random.random()
        if rand < home_win_prob * 0.7:  # 70% of expected
            outcome = "H"
            home_goals = np.random.poisson(2)
            away_goals = np.random.poisson(1)
        elif rand < home_win_prob * 0.7 + 0.25:
            outcome = "D"
            goals = np.random.poisson(1.5)
            home_goals = away_goals = int(goals)
        else:
            outcome = "A"
            home_goals = np.random.poisson(1)
            away_goals = np.random.poisson(2)

        match = {
            "fixture_id": i + 1,
            "date": datetime.now() - timedelta(days=n_matches - i),
            "home_team_name": home_team,
            "away_team_name": away_team,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "outcome": outcome,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": elo_diff,
            "home_form_last_5": np.random.uniform(0, 3),
            "away_form_last_5": np.random.uniform(0, 3),
            "home_goals_scored_avg_5": np.random.uniform(1, 3),
            "away_goals_scored_avg_5": np.random.uniform(1, 3),
            "home_goals_conceded_avg_5": np.random.uniform(0.5, 2.5),
            "away_goals_conceded_avg_5": np.random.uniform(0.5, 2.5),
            "home_xG_simple": np.random.uniform(1, 2.5),
            "away_xG_simple": np.random.uniform(0.8, 2.2),
            "month": (datetime.now() - timedelta(days=n_matches - i)).month,
            "day_of_week": (datetime.now() - timedelta(days=n_matches - i)).weekday(),
        }

        matches.append(match)

    df = pd.DataFrame(matches)
    logger.info(f"Generated {len(df)} mock matches")

    return df


def train_simple_model(df):
    """
    Train a simple model on mock data
    """
    logger.info("Training simple model...")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report

    # Select features
    feature_cols = [
        "home_elo", "away_elo", "elo_diff",
        "home_form_last_5", "away_form_last_5",
        "home_goals_scored_avg_5", "away_goals_scored_avg_5",
        "home_xG_simple", "away_xG_simple",
    ]

    X = df[feature_cols]
    y = df["outcome"]

    # Encode target
    le = LabelEncoder()
    y_encoded = le.fit_transform(y)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    logger.info(f"Model Accuracy: {accuracy:.2%}")
    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    return model, le, feature_cols


def make_demo_prediction(model, le, feature_cols):
    """
    Make a demo prediction
    """
    logger.info("\n" + "=" * 60)
    logger.info("DEMO PREDICTION: Manchester United vs Liverpool")
    logger.info("=" * 60)

    # Create mock match features
    match_data = {
        "home_elo": 1650,
        "away_elo": 1620,
        "elo_diff": 30,
        "home_form_last_5": 2.4,
        "away_form_last_5": 2.1,
        "home_goals_scored_avg_5": 2.2,
        "away_goals_scored_avg_5": 1.9,
        "home_xG_simple": 2.0,
        "away_xG_simple": 1.7,
    }

    X_pred = pd.DataFrame([match_data])

    # Predict
    pred_proba = model.predict_proba(X_pred)[0]
    pred_class = model.predict(X_pred)[0]
    pred_label = le.inverse_transform([pred_class])[0]

    # Display results
    print("\n📊 MATCH RESULT PREDICTION:")
    print(f"   Prediction: {pred_label} ({'Home Win' if pred_label == 'H' else 'Draw' if pred_label == 'D' else 'Away Win'})")
    print(f"   Confidence: {pred_proba[pred_class]:.2%}")
    print("\n   Probabilities:")
    for i, outcome in enumerate(le.classes_):
        label = "Home Win" if outcome == "H" else "Draw" if outcome == "D" else "Away Win"
        print(f"      {outcome} ({label}): {pred_proba[i]:.2%}")

    # Simulate goal prediction
    home_xG = match_data["home_xG_simple"]
    away_xG = match_data["away_xG_simple"]

    print("\n⚽ GOALS PREDICTION:")
    print(f"   Home xG: {home_xG:.2f}")
    print(f"   Away xG: {away_xG:.2f}")
    print(f"   Expected Total Goals: {home_xG + away_xG:.2f}")
    print(f"   Most Likely Score: 2-1")
    print(f"   Over 2.5 Goals Probability: {0.58:.2%}")

    print("\n💡 RECOMMENDATIONS:")
    if pred_proba[pred_class] > 0.6:
        confidence = "MEDIUM" if pred_proba[pred_class] < 0.75 else "HIGH"
        print(f"   [{confidence}] Match Result: {pred_label}")
        print(f"      Probability: {pred_proba[pred_class]:.2%}")
        print(f"      Risk: {'LOW' if confidence == 'HIGH' else 'MEDIUM'}")

    print("\n⚠️  DISCLAIMER:")
    print("   This is a DEMO with mock data for educational purposes only.")
    print("   Real predictions require trained models with actual match data.")
    print("   Never bet more than you can afford to lose!")
    print("=" * 60)


def demo_feature_engineering():
    """
    Demonstrate feature engineering concepts
    """
    logger.info("\n" + "=" * 60)
    logger.info("FEATURE ENGINEERING DEMO")
    logger.info("=" * 60)

    print("\n🔧 Key Features for Soccer Prediction:\n")

    features = [
        ("Elo Rating", "Dynamic team strength (like chess ratings)", "High"),
        ("Form (Last 5)", "Points from recent matches", "High"),
        ("Goals Scored Avg", "Attacking strength", "High"),
        ("Goals Conceded Avg", "Defensive weakness", "High"),
        ("Home Advantage", "Home team boost (~0.5 goals)", "Medium"),
        ("Head-to-Head", "Historical matchup records", "Medium"),
        ("League Position", "Current standings", "Medium"),
        ("xG (Expected Goals)", "Shot quality metric", "High"),
        ("Win Streak", "Momentum indicator", "Low"),
        ("Travel Distance", "Fatigue factor", "Low"),
    ]

    for feature, description, importance in features:
        print(f"   • {feature:20} {description:40} Importance: {importance}")

    print("\n📊 Feature Engineering Steps:")
    print("   1. Calculate Elo ratings (updated after each match)")
    print("   2. Compute rolling averages (last 3, 5, 10 matches)")
    print("   3. Extract head-to-head records")
    print("   4. Normalize features (StandardScaler)")
    print("   5. Create interaction features (e.g., form_diff)")

    print("\n✅ Result: 100+ features ready for ML models")
    print("=" * 60)


def demo_model_comparison():
    """
    Show model comparison
    """
    logger.info("\n" + "=" * 60)
    logger.info("MODEL COMPARISON")
    logger.info("=" * 60)

    models_performance = [
        ("XGBoost", 0.612, 0.89, "Excellent for structured data, handles non-linearity"),
        ("LightGBM", 0.608, 0.91, "Faster training, good feature importance"),
        ("CatBoost", 0.605, 0.90, "Handles categorical features well"),
        ("Random Forest", 0.580, 0.95, "Stable, but less accurate than boosting"),
        ("Logistic Regression", 0.520, 1.15, "Baseline, too simple for soccer"),
        ("Ensemble (Weighted)", 0.628, 0.87, "Best overall, combines strengths"),
    ]

    print("\n📊 Model Performance (Mock Data):\n")
    print(f"   {'Model':<25} {'Accuracy':>10} {'Log Loss':>10} {'Notes':<50}")
    print("   " + "-" * 100)

    for model, acc, logloss, notes in models_performance:
        print(f"   {model:<25} {acc:>9.1%} {logloss:>10.2f} {notes:<50}")

    print("\n🎯 Recommended Approach:")
    print("   • Train XGBoost, LightGBM, and CatBoost separately")
    print("   • Combine predictions using weighted average")
    print("   • Weights based on validation performance")
    print("   • Retrain models after each matchday")

    print("\n📈 Realistic Expectations:")
    print("   • Match Outcome: 60-65% accuracy (excellent)")
    print("   • Over/Under 2.5: 55-60% accuracy")
    print("   • Correct Score: 10-15% accuracy (very hard)")
    print("   • BTTS: 60-65% accuracy")

    print("\n⚠️  Note: 95%+ accuracy is IMPOSSIBLE due to:")
    print("   • Referee decisions, red cards, VAR")
    print("   • Injuries during match")
    print("   • Weather conditions")
    print("   • Player morale, tactics changes")
    print("   • Pure luck (deflections, woodwork)")

    print("=" * 60)


def main():
    """
    Run demo
    """
    print("\n")
    print("=" * 60)
    print(" SOCCER PREDICTION BOT - DEMO")
    print("=" * 60)
    print("\nThis demo uses mock data to demonstrate the bot's capabilities.")
    print("For real predictions, you'll need:")
    print("  1. API keys (API-Football)")
    print("  2. Historical data (5000+ matches)")
    print("  3. Trained models (XGBoost, LightGBM)")
    print("\n" + "=" * 60 + "\n")

    # Generate mock data
    df = generate_mock_data()

    # Show sample data
    logger.info("\nSample Match Data:")
    print(df[["home_team_name", "away_team_name", "home_goals", "away_goals", "outcome"]].head(10))

    # Train simple model
    model, le, feature_cols = train_simple_model(df)

    # Make demo prediction
    make_demo_prediction(model, le, feature_cols)

    # Show feature engineering concepts
    demo_feature_engineering()

    # Show model comparison
    demo_model_comparison()

    # Final notes
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("\n1. Get API key: https://www.api-football.com/")
    print("2. Configure config.py with your API key")
    print("3. Run: python main.py --step full")
    print("4. Wait 8-12 hours for data collection")
    print("5. Models will be saved in models/ folder")
    print("6. Start API: uvicorn api:app --reload")
    print("7. Make real predictions!")
    print("\nRead QUICKSTART.md for detailed instructions.")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
