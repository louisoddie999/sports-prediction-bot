"""
Simplified Main Script - Handles imports gracefully
"""

import argparse
import logging
from datetime import datetime
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required packages are installed"""
    required = {
        "pandas": "pandas",
        "numpy": "numpy",
        "sklearn": "scikit-learn",
        "xgboost": "xgboost",
        "lightgbm": "lightgbm",
        "requests": "requests",
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"\nInstall with: py -m pip install {' '.join(missing)}")
        sys.exit(1)


# Check dependencies first
check_dependencies()

# Now import modules
from config import LEAGUES, SEASONS, PROCESSED_DATA_DIR
from data_collection import DataCollector
from data_preprocessing import DataPreprocessor
from feature_engineering import FeatureEngineer
from model_training import SoccerPredictionModel
from prediction import MatchPredictor


def collect_data():
    """
    Step 1: Collect raw data from APIs
    """
    logger.info("=" * 60)
    logger.info("STEP 1: DATA COLLECTION")
    logger.info("=" * 60)

    collector = DataCollector()

    # Collect data for configured leagues and seasons
    for league_name, league_info in LEAGUES.items():
        league_id = league_info["id"]
        logger.info(f"\n{'='*50}\nCollecting data for {league_name}\n{'='*50}")

        for season in SEASONS:
            try:
                logger.info(f"Processing {league_name} - Season {season}")
                data = collector.collect_all_data_for_league(league_id, season)
                
                # Log summary
                for data_type, df in data.items():
                    logger.info(f"  {data_type}: {len(df)} records")
                
                import time
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error collecting {league_name} {season}: {e}")
                continue

    logger.info("\n✅ Data collection complete!")


def preprocess_data():
    """
    Step 2: Preprocess raw data
    """
    logger.info("=" * 60)
    logger.info("STEP 2: DATA PREPROCESSING")
    logger.info("=" * 60)

    preprocessor = DataPreprocessor()
    league_ids = [info["id"] for info in LEAGUES.values()]
    combined_df = preprocessor.preprocess_all_leagues(league_ids, SEASONS)

    logger.info(f"\n✅ Preprocessing complete. Total matches: {len(combined_df)}")
    return combined_df


def engineer_features():
    """
    Step 3: Engineer features
    """
    logger.info("=" * 60)
    logger.info("STEP 3: FEATURE ENGINEERING")
    logger.info("=" * 60)

    import pandas as pd
    combined_df = pd.read_csv(f"{PROCESSED_DATA_DIR}/all_leagues_preprocessed.csv")

    engineer = FeatureEngineer()
    featured_df = engineer.engineer_all_features(combined_df)

    output_file = f"{PROCESSED_DATA_DIR}/all_leagues_featured.csv"
    featured_df.to_csv(output_file, index=False)

    logger.info(f"\n✅ Feature engineering complete. Saved to {output_file}")
    return featured_df


def train_models():
    """
    Step 4: Train models
    """
    logger.info("=" * 60)
    logger.info("STEP 4: MODEL TRAINING")
    logger.info("=" * 60)

    import pandas as pd
    df = pd.read_csv(f"{PROCESSED_DATA_DIR}/all_leagues_featured.csv")

    trainer = SoccerPredictionModel()
    X, y, feature_cols = trainer.prepare_data(df)
    X_train, X_test, y_train, y_test = trainer.split_data(X, y, test_size=0.2)

    # Train ensemble
    models = trainer.train_ensemble(X_train, y_train)

    # Evaluate
    logger.info("\n" + "=" * 60)
    logger.info("MODEL EVALUATION")
    logger.info("=" * 60)

    for model_name, model in models.items():
        trainer.evaluate_model(model, X_test, y_test, model_name)

    # Ensemble evaluation
    import numpy as np
    from sklearn.metrics import accuracy_score, log_loss

    ensemble_pred_proba = trainer.predict_ensemble(X_test)
    ensemble_pred = np.argmax(ensemble_pred_proba, axis=1)

    accuracy = accuracy_score(y_test, ensemble_pred)
    logloss = log_loss(y_test, ensemble_pred_proba)

    logger.info("\n" + "=" * 60)
    logger.info("ENSEMBLE PERFORMANCE")
    logger.info(f"Accuracy: {accuracy:.4f}")
    logger.info(f"Log Loss: {logloss:.4f}")
    logger.info("=" * 60)

    # Save models
    trainer.save_models(models, suffix="_final")

    logger.info("\n✅ Training complete!")
    return trainer, models


def make_predictions(trainer: SoccerPredictionModel):
    """
    Step 5: Make predictions
    """
    logger.info("=" * 60)
    logger.info("STEP 5: MAKING PREDICTIONS")
    logger.info("=" * 60)

    import pandas as pd
    df = pd.read_csv(f"{PROCESSED_DATA_DIR}/all_leagues_featured.csv")

    # Get recent matches
    recent_matches = df.tail(10)

    # Initialize Telegram notifier
    try:
        from telegram_notifier import TelegramNotifier
        from config import TELEGRAM_ENABLED
        
        if TELEGRAM_ENABLED:
            notifier = TelegramNotifier()
            logger.info("Telegram notifier enabled")
        else:
            notifier = None
            logger.info("Telegram disabled - predictions will only print to console")
    except:
        notifier = None
        logger.warning("Telegram not configured")

    # Create predictor
    predictor = MatchPredictor(
        trainer.models, trainer.label_encoder, trainer.feature_columns
    )

    # Make predictions
    all_predictions = []
    
    for idx, row in recent_matches.iterrows():
        try:
            home_team = row.get("home_team_name", "Team A")
            away_team = row.get("away_team_name", "Team B")
            actual_outcome = row.get("outcome", "Unknown")

            match_features = recent_matches.iloc[[idx]]

            # Predict
            prediction = predictor.predict_comprehensive(
                home_team,
                away_team,
                match_features,
                home_xG=row.get("home_xG_simple", 1.5),
                away_xG=row.get("away_xG_simple", 1.2),
            )

            # Display
            output = predictor.format_prediction_output(prediction)
            print(output)
            print(f"\nACTUAL OUTCOME: {actual_outcome}\n")
            
            all_predictions.append(prediction)

            # Send to Telegram if enabled
            if notifier and TELEGRAM_ENABLED:
                try:
                    notifier.send_prediction(prediction)
                    logger.info(f"✅ Sent prediction to Telegram: {home_team} vs {away_team}")
                except Exception as e:
                    logger.error(f"Failed to send to Telegram: {e}")

        except Exception as e:
            logger.error(f"Error predicting match {idx}: {e}")
            continue

    logger.info(f"\n✅ Predictions complete! Processed {len(all_predictions)} matches")


def full_pipeline():
    """
    Run complete pipeline
    """
    start_time = datetime.now()

    logger.info("\n" + "=" * 60)
    logger.info("SOCCER PREDICTION BOT - FULL PIPELINE")
    logger.info("=" * 60 + "\n")

    try:
        # Step 1: Collect data
        collect_data()

        # Step 2: Preprocess
        preprocess_data()

        # Step 3: Features
        engineer_features()

        # Step 4: Train
        trainer, models = train_models()

        # Step 5: Predict
        make_predictions(trainer)

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise

    duration = datetime.now() - start_time
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Total duration: {duration}")
    logger.info("=" * 60 + "\n")


def main():
    """
    Main entry point
    """
    parser = argparse.ArgumentParser(description="Soccer Prediction Bot")

    parser.add_argument(
        "--step",
        type=str,
        choices=["collect", "preprocess", "features", "train", "predict", "full"],
        default="full",
        help="Which step to run",
    )

    args = parser.parse_args()

    logger.info(f"\nStarting step: {args.step}\n")

    # Run selected step
    if args.step == "collect":
        collect_data()
    elif args.step == "preprocess":
        preprocess_data()
    elif args.step == "features":
        engineer_features()
    elif args.step == "train":
        train_models()
    elif args.step == "predict":
        logger.warning("Prediction requires trained models. Run --step train first.")
        # make_predictions(trainer)  # Need to load models
    elif args.step == "full":
        full_pipeline()


if __name__ == "__main__":
    main()
