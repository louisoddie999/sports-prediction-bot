"""
Model Training Module
Trains ensemble models (XGBoost, LightGBM) with hyperparameter tuning
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
import logging
import joblib
import json
from datetime import datetime

from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb
import lightgbm as lgb
# from catboost import CatBoostClassifier  # Removed - requires Visual Studio
import optuna
from optuna.samplers import TPESampler
# import shap  # Optional - for model interpretability

from config import (
    MODEL_CONFIG,
    XGBOOST_PARAMS,
    LIGHTGBM_PARAMS,
    MODELS_DIR,
    PROCESSED_DATA_DIR,
    FEATURE_IMPORTANCE_THRESHOLD,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SoccerPredictionModel:
    """
    Train and evaluate soccer match prediction models
    """

    def __init__(self):
        self.models = {}
        self.label_encoder = LabelEncoder()
        self.feature_columns = []
        self.training_history = []

    def prepare_data(
        self, df: pd.DataFrame, target_col: str = "outcome"
    ) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """
        Prepare data for training: select features, encode target
        
        Args:
            df: Featured DataFrame
            target_col: Target column name
            
        Returns:
            (X, y, feature_columns)
        """
        # Columns to exclude from features
        exclude_cols = [
            "fixture_id",
            "date",
            "timestamp",
            "home_team_id",
            "away_team_id",
            "home_team_name",
            "away_team_name",
            "league_id",
            "season",
            "round",
            "status",
            "referee",
            "venue",
            "city",
            "outcome",
            "home_goals",
            "away_goals",
            "total_goals",
            "goal_diff",
            "halftime_home",
            "halftime_away",
            "home_form",
            "away_form",
        ]

        # Select feature columns
        feature_cols = [
            col for col in df.columns 
            if col not in exclude_cols and df[col].dtype in ["int64", "float64"]
        ]

        X = df[feature_cols].copy()
        y = df[target_col].copy()

        # Handle missing values
        X = X.fillna(X.mean())

        # Encode target
        y_encoded = self.label_encoder.fit_transform(y)

        logger.info(f"Prepared data: {X.shape[0]} samples, {X.shape[1]} features")
        logger.info(f"Target distribution: {pd.Series(y).value_counts().to_dict()}")

        self.feature_columns = feature_cols

        return X, y_encoded, feature_cols

    def split_data(
        self, X: pd.DataFrame, y: np.ndarray, test_size: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
        """
        Split data into train and test sets (temporal split to avoid data leakage)
        """
        # Temporal split (last N% as test)
        split_idx = int(len(X) * (1 - test_size))

        X_train = X.iloc[:split_idx]
        X_test = X.iloc[split_idx:]
        y_train = y[:split_idx]
        y_test = y[split_idx:]

        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        return X_train, X_test, y_train, y_test

    def train_xgboost(
        self, X_train: pd.DataFrame, y_train: np.ndarray, X_val: pd.DataFrame, y_val: np.ndarray
    ) -> xgb.XGBClassifier:
        """
        Train XGBoost model with validation
        """
        logger.info("Training XGBoost model...")

        model = xgb.XGBClassifier(
            objective="multi:softprob",
            num_class=3,
            max_depth=8,
            learning_rate=0.05,
            n_estimators=300,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=MODEL_CONFIG["random_state"],
            tree_method="hist",
            device="cpu",
            enable_categorical=False,
        )

        # Train with early stopping
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        logger.info("XGBoost training complete")
        return model

    def train_lightgbm(
        self, X_train: pd.DataFrame, y_train: np.ndarray, X_val: pd.DataFrame, y_val: np.ndarray
    ) -> lgb.LGBMClassifier:
        """
        Train LightGBM model
        """
        logger.info("Training LightGBM model...")

        model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            boosting_type="gbdt",
            num_leaves=50,
            learning_rate=0.05,
            n_estimators=300,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=MODEL_CONFIG["random_state"],
            device="cpu",
            verbose=-1,
        )

        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.log_evaluation(period=0)],
        )

        logger.info("LightGBM training complete")
        return model

    def train_catboost(
        self, X_train: pd.DataFrame, y_train: np.ndarray, X_val: pd.DataFrame, y_val: np.ndarray
    ) -> CatBoostClassifier:
        """
        Train CatBoost model
        """
        logger.info("Training CatBoost model...")

        model = CatBoostClassifier(
            iterations=300,
            learning_rate=0.05,
            depth=8,
            loss_function="MultiClass",
            random_state=MODEL_CONFIG["random_state"],
            verbose=False,
        )

        model.fit(
            X_train,
            y_train,
            eval_set=(X_val, y_val),
            verbose=False,
        )

        logger.info("CatBoost training complete")
        return model

    def train_ensemble(
        self, X_train: pd.DataFrame, y_train: np.ndarray
    ) -> Dict[str, Any]:
        """
        Train ensemble of models (XGBoost, LightGBM, CatBoost)
        """
        # Further split train into train/validation
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train,
            y_train,
            test_size=MODEL_CONFIG["validation_size"],
            random_state=MODEL_CONFIG["random_state"],
            stratify=y_train,
        )

        logger.info(f"Training ensemble on {len(X_tr)} samples, validating on {len(X_val)}")

        # Train individual models
        models = {
            "xgboost": self.train_xgboost(X_tr, y_tr, X_val, y_val),
            "lightgbm": self.train_lightgbm(X_tr, y_tr, X_val, y_val),
            "catboost": self.train_catboost(X_tr, y_tr, X_val, y_val),
        }

        self.models = models
        logger.info("Ensemble training complete")

        return models

    def predict_ensemble(self, X: pd.DataFrame, weights: Dict[str, float] = None) -> np.ndarray:
        """
        Make predictions using ensemble (weighted average)
        
        Args:
            X: Features
            weights: Model weights (default: equal weight)
            
        Returns:
            Probability predictions (n_samples, n_classes)
        """
        if weights is None:
            weights = {name: 1.0 / len(self.models) for name in self.models.keys()}

        predictions = []

        for model_name, model in self.models.items():
            pred_proba = model.predict_proba(X)
            predictions.append(pred_proba * weights[model_name])

        # Average predictions
        ensemble_pred = np.sum(predictions, axis=0)

        return ensemble_pred

    def evaluate_model(
        self, model: Any, X_test: pd.DataFrame, y_test: np.ndarray, model_name: str
    ) -> Dict[str, float]:
        """
        Evaluate model performance
        """
        logger.info(f"Evaluating {model_name}...")

        # Predictions
        y_pred_proba = model.predict_proba(X_test)
        y_pred = model.predict(X_test)

        # Metrics
        accuracy = accuracy_score(y_test, y_pred)
        logloss = log_loss(y_test, y_pred_proba)
        precision = precision_score(y_test, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_test, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="weighted", zero_division=0)

        metrics = {
            "model": model_name,
            "accuracy": accuracy,
            "log_loss": logloss,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

        logger.info(f"{model_name} - Accuracy: {accuracy:.4f}, Log Loss: {logloss:.4f}")

        # Classification report
        target_names = self.label_encoder.classes_
        report = classification_report(y_test, y_pred, target_names=target_names)
        logger.info(f"\nClassification Report:\n{report}")

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        logger.info(f"\nConfusion Matrix:\n{cm}")

        return metrics

    def cross_validate(
        self, X: pd.DataFrame, y: np.ndarray, model_type: str = "xgboost"
    ) -> Dict[str, float]:
        """
        Perform cross-validation
        """
        logger.info(f"Cross-validating {model_type}...")

        if model_type == "xgboost":
            model = xgb.XGBClassifier(
                objective="multi:softprob",
                num_class=3,
                max_depth=8,
                learning_rate=0.05,
                n_estimators=200,
                random_state=MODEL_CONFIG["random_state"],
            )
        elif model_type == "lightgbm":
            model = lgb.LGBMClassifier(
                objective="multiclass",
                num_class=3,
                num_leaves=50,
                learning_rate=0.05,
                n_estimators=200,
                random_state=MODEL_CONFIG["random_state"],
                verbose=-1,
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Stratified K-Fold
        cv = StratifiedKFold(
            n_splits=MODEL_CONFIG["cv_folds"],
            shuffle=True,
            random_state=MODEL_CONFIG["random_state"],
        )

        # Cross-validation scores
        cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")

        results = {
            "mean_accuracy": cv_scores.mean(),
            "std_accuracy": cv_scores.std(),
            "cv_scores": cv_scores.tolist(),
        }

        logger.info(f"CV Accuracy: {results['mean_accuracy']:.4f} (+/- {results['std_accuracy']:.4f})")

        return results

    def analyze_feature_importance(self, model: Any, feature_names: List[str]) -> pd.DataFrame:
        """
        Analyze and plot feature importance
        """
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "get_feature_importance"):
            importances = model.get_feature_importance()
        else:
            logger.warning("Model does not support feature importance")
            return pd.DataFrame()

        # Create DataFrame
        importance_df = pd.DataFrame({
            "feature": feature_names,
            "importance": importances,
        }).sort_values("importance", ascending=False)

        # Log top features
        logger.info("\nTop 20 Important Features:")
        for idx, row in importance_df.head(20).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        return importance_df

    def save_models(self, models: Dict[str, Any], suffix: str = ""):
        """
        Save trained models
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for model_name, model in models.items():
            filename = f"{MODELS_DIR}/{model_name}_model{suffix}_{timestamp}.pkl"
            joblib.dump(model, filename)
            logger.info(f"Saved {model_name} to {filename}")

        # Save label encoder
        encoder_file = f"{MODELS_DIR}/label_encoder{suffix}_{timestamp}.pkl"
        joblib.dump(self.label_encoder, encoder_file)

        # Save feature columns
        features_file = f"{MODELS_DIR}/feature_columns{suffix}_{timestamp}.json"
        with open(features_file, "w") as f:
            json.dump(self.feature_columns, f)

        logger.info("All models saved successfully")

    def load_models(self, model_paths: Dict[str, str], encoder_path: str, features_path: str):
        """
        Load trained models
        """
        for model_name, path in model_paths.items():
            self.models[model_name] = joblib.load(path)
            logger.info(f"Loaded {model_name} from {path}")

        self.label_encoder = joblib.load(encoder_path)
        with open(features_path, "r") as f:
            self.feature_columns = json.load(f)

        logger.info("All models loaded successfully")


# Example usage
if __name__ == "__main__":
    from config import LEAGUES

    # Load featured data
    league_id = LEAGUES["Premier League"]["id"]
    season = 2023
    df = pd.read_csv(f"{PROCESSED_DATA_DIR}/league_{league_id}_featured_{season}.csv")

    print(f"Loaded data: {df.shape}")

    # Initialize model
    model_trainer = SoccerPredictionModel()

    # Prepare data
    X, y, feature_cols = model_trainer.prepare_data(df)

    # Split data
    X_train, X_test, y_train, y_test = model_trainer.split_data(X, y, test_size=0.2)

    # Train ensemble
    models = model_trainer.train_ensemble(X_train, y_train)

    # Evaluate each model
    results = []
    for model_name, model in models.items():
        metrics = model_trainer.evaluate_model(model, X_test, y_test, model_name)
        results.append(metrics)

    # Evaluate ensemble
    ensemble_pred_proba = model_trainer.predict_ensemble(X_test)
    ensemble_pred = np.argmax(ensemble_pred_proba, axis=1)

    ensemble_accuracy = accuracy_score(y_test, ensemble_pred)
    ensemble_logloss = log_loss(y_test, ensemble_pred_proba)

    print(f"\n{'='*50}")
    print(f"ENSEMBLE RESULTS:")
    print(f"Accuracy: {ensemble_accuracy:.4f}")
    print(f"Log Loss: {ensemble_logloss:.4f}")
    print(f"{'='*50}")

    # Feature importance
    importance_df = model_trainer.analyze_feature_importance(
        models["xgboost"], feature_cols
    )

    # Save models
    model_trainer.save_models(models, suffix="_premier_league_2023")

    print("\n✅ Training complete!")
