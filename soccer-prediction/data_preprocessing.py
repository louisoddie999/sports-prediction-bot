"""
Data Preprocessing Module
Handles data cleaning, normalization, and transformation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.impute import SimpleImputer
import warnings

warnings.filterwarnings("ignore")

from config import PROCESSED_DATA_DIR, RAW_DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    Preprocesses raw soccer data for machine learning
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy="mean")

    def load_raw_data(self, league_id: int, season: int) -> Dict[str, pd.DataFrame]:
        """
        Load raw data from CSV files
        """
        data = {}
        data_types = ["fixtures", "team_stats", "standings", "injuries"]

        for data_type in data_types:
            try:
                filename = f"{RAW_DATA_DIR}/league_{league_id}_{data_type}_{season}.csv"
                df = pd.read_csv(filename)
                data[data_type] = df
                logger.info(f"Loaded {data_type}: {len(df)} records")
            except FileNotFoundError:
                logger.warning(f"File not found: {filename}")
                data[data_type] = pd.DataFrame()

        return data

    def clean_fixtures(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        """
        Clean fixture data: handle missing values, convert types
        """
        if fixtures.empty:
            return fixtures

        df = fixtures.copy()

        # Convert date to datetime
        df["date"] = pd.to_datetime(df["date"])

        # Filter only completed matches (FT = Full Time)
        df = df[df["status"] == "FT"].copy()

        # Handle missing goals (shouldn't happen for completed matches)
        df["home_goals"] = df["home_goals"].fillna(0).astype(int)
        df["away_goals"] = df["away_goals"].fillna(0).astype(int)

        # Create outcome labels
        df["outcome"] = df.apply(
            lambda row: (
                "H" if row["home_goals"] > row["away_goals"]
                else "D" if row["home_goals"] == row["away_goals"]
                else "A"
            ),
            axis=1,
        )

        # Total goals
        df["total_goals"] = df["home_goals"] + df["away_goals"]

        # Goal difference
        df["goal_diff"] = df["home_goals"] - df["away_goals"]

        # Sort by date
        df = df.sort_values("date").reset_index(drop=True)

        logger.info(f"Cleaned fixtures: {len(df)} completed matches")
        return df

    def handle_missing_values(self, df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        """
        Handle missing values using mean imputation for numerical columns
        """
        df_copy = df.copy()

        for col in columns:
            if col in df_copy.columns:
                if df_copy[col].isnull().any():
                    if df_copy[col].dtype in ["float64", "int64"]:
                        # Mean imputation
                        mean_val = df_copy[col].mean()
                        df_copy[col].fillna(mean_val, inplace=True)
                        logger.info(f"Imputed {col} with mean: {mean_val:.2f}")
                    else:
                        # Forward fill for categorical
                        df_copy[col].fillna(method="ffill", inplace=True)

        return df_copy

    def normalize_features(
        self, df: pd.DataFrame, feature_columns: List[str]
    ) -> Tuple[pd.DataFrame, StandardScaler]:
        """
        Normalize numerical features using StandardScaler
        """
        df_copy = df.copy()

        # Select only existing columns
        existing_cols = [col for col in feature_columns if col in df_copy.columns]

        if not existing_cols:
            logger.warning("No columns to normalize")
            return df_copy, None

        # Fit and transform
        scaler = StandardScaler()
        df_copy[existing_cols] = scaler.fit_transform(df_copy[existing_cols])

        logger.info(f"Normalized {len(existing_cols)} features")
        return df_copy, scaler

    def create_match_dataset(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        """
        Create a base match dataset with basic features
        """
        df = fixtures.copy()

        # Extract time features
        df["month"] = df["date"].dt.month
        df["day_of_week"] = df["date"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

        # Extract round number if available
        if "round" in df.columns:
            # Parse round (e.g., "Regular Season - 10" -> 10)
            df["round_number"] = (
                df["round"]
                .str.extract(r"(\d+)")
                .astype(float)
                .fillna(0)
                .astype(int)
            )
        else:
            df["round_number"] = 0

        logger.info("Created base match dataset")
        return df

    def merge_team_stats(
        self,
        matches: pd.DataFrame,
        team_stats: pd.DataFrame,
        standings: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge team statistics and standings into match data
        """
        if matches.empty:
            return matches

        df = matches.copy()

        # Merge team stats for home team
        if not team_stats.empty:
            home_stats = team_stats.copy()
            home_stats.columns = [f"home_{col}" if col != "team_id" else col for col in home_stats.columns]
            df = df.merge(
                home_stats,
                left_on=["home_team_id", "league_id", "season"],
                right_on=["team_id", "home_league_id", "home_season"],
                how="left",
            )

            # Merge team stats for away team
            away_stats = team_stats.copy()
            away_stats.columns = [f"away_{col}" if col != "team_id" else col for col in away_stats.columns]
            df = df.merge(
                away_stats,
                left_on=["away_team_id", "league_id", "season"],
                right_on=["team_id", "away_league_id", "away_season"],
                how="left",
            )

        # Merge standings for home team
        if not standings.empty:
            home_standings = standings.copy()
            home_standings.columns = [f"home_{col}" if col != "team_id" else col for col in home_standings.columns]
            df = df.merge(
                home_standings[["team_id", "home_rank", "home_points", "home_form"]],
                left_on="home_team_id",
                right_on="team_id",
                how="left",
                suffixes=("", "_standings"),
            )

            # Merge standings for away team
            away_standings = standings.copy()
            away_standings.columns = [f"away_{col}" if col != "team_id" else col for col in away_standings.columns]
            df = df.merge(
                away_standings[["team_id", "away_rank", "away_points", "away_form"]],
                left_on="away_team_id",
                right_on="team_id",
                how="left",
                suffixes=("", "_standings"),
            )

        logger.info("Merged team statistics and standings")
        return df

    def encode_form(self, form_string: str) -> Dict[str, int]:
        """
        Encode form string (e.g., "WWDLW") into numerical features
        
        Returns:
            Dictionary with wins, draws, losses counts
        """
        if pd.isna(form_string) or not form_string:
            return {"wins": 0, "draws": 0, "losses": 0, "points": 0}

        # Count results in last 5 matches
        wins = form_string.count("W")
        draws = form_string.count("D")
        losses = form_string.count("L")
        points = wins * 3 + draws

        return {"wins": wins, "draws": draws, "losses": losses, "points": points}

    def calculate_form_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate form-based features from form strings
        """
        df_copy = df.copy()

        # Home team form
        if "home_form" in df_copy.columns:
            form_features = df_copy["home_form"].apply(self.encode_form)
            df_copy["home_form_wins"] = form_features.apply(lambda x: x["wins"])
            df_copy["home_form_draws"] = form_features.apply(lambda x: x["draws"])
            df_copy["home_form_losses"] = form_features.apply(lambda x: x["losses"])
            df_copy["home_form_points"] = form_features.apply(lambda x: x["points"])

        # Away team form
        if "away_form" in df_copy.columns:
            form_features = df_copy["away_form"].apply(self.encode_form)
            df_copy["away_form_wins"] = form_features.apply(lambda x: x["wins"])
            df_copy["away_form_draws"] = form_features.apply(lambda x: x["draws"])
            df_copy["away_form_losses"] = form_features.apply(lambda x: x["losses"])
            df_copy["away_form_points"] = form_features.apply(lambda x: x["points"])

        logger.info("Calculated form features")
        return df_copy

    def preprocess_league_season(
        self, league_id: int, season: int
    ) -> pd.DataFrame:
        """
        Complete preprocessing pipeline for a league season
        
        Returns:
            Preprocessed DataFrame ready for feature engineering
        """
        logger.info(f"Preprocessing league {league_id}, season {season}")

        # Load raw data
        data = self.load_raw_data(league_id, season)

        # Clean fixtures
        fixtures = self.clean_fixtures(data["fixtures"])

        if fixtures.empty:
            logger.warning("No fixtures to process")
            return pd.DataFrame()

        # Create base dataset
        df = self.create_match_dataset(fixtures)

        # Merge team stats and standings
        df = self.merge_team_stats(df, data["team_stats"], data["standings"])

        # Calculate form features
        df = self.calculate_form_features(df)

        # Handle missing values for numerical columns
        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        df = self.handle_missing_values(df, numerical_cols)

        # Save preprocessed data
        output_file = f"{PROCESSED_DATA_DIR}/league_{league_id}_preprocessed_{season}.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"Saved preprocessed data to {output_file}")

        return df

    def preprocess_all_leagues(self, league_ids: List[int], seasons: List[int]) -> pd.DataFrame:
        """
        Preprocess all leagues and seasons, combine into single dataset
        """
        all_data = []

        for league_id in league_ids:
            for season in seasons:
                try:
                    df = self.preprocess_league_season(league_id, season)
                    if not df.empty:
                        all_data.append(df)
                except Exception as e:
                    logger.error(f"Error preprocessing league {league_id}, season {season}: {e}")
                    continue

        if not all_data:
            logger.error("No data to combine")
            return pd.DataFrame()

        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"Combined data: {len(combined_df)} matches from {len(all_data)} datasets")

        # Save combined data
        output_file = f"{PROCESSED_DATA_DIR}/all_leagues_preprocessed.csv"
        combined_df.to_csv(output_file, index=False)
        logger.info(f"Saved combined data to {output_file}")

        return combined_df


# Example usage
if __name__ == "__main__":
    from config import LEAGUES, SEASONS

    preprocessor = DataPreprocessor()

    # Preprocess a single league
    league_id = LEAGUES["Premier League"]["id"]
    season = 2023
    df = preprocessor.preprocess_league_season(league_id, season)

    print("\nPreprocessed Data Shape:", df.shape)
    print("\nColumns:", df.columns.tolist()[:20], "...")
    print("\nOutcome Distribution:")
    if not df.empty and "outcome" in df.columns:
        print(df["outcome"].value_counts())

    # Uncomment to preprocess all leagues
    # league_ids = [info["id"] for info in LEAGUES.values()]
    # combined_df = preprocessor.preprocess_all_leagues(league_ids, SEASONS)
