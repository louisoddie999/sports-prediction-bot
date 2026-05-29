"""
Feature Engineering Module
Creates advanced soccer-specific features: xG, Elo ratings, rolling stats, etc.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import logging
from scipy.stats import poisson

from config import FEATURE_CONFIG, PROCESSED_DATA_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Creates advanced features for soccer match prediction
    """

    def __init__(self):
        self.elo_ratings = {}  # Store Elo ratings for teams
        self.elo_k = FEATURE_CONFIG["elo_k_factor"]
        self.elo_initial = FEATURE_CONFIG["elo_initial"]
        self.home_advantage = FEATURE_CONFIG["home_advantage"]

    def calculate_elo_rating(
        self, team_elo: float, opponent_elo: float, result: float, is_home: bool = False
    ) -> float:
        """
        Calculate new Elo rating after a match
        
        Args:
            team_elo: Current Elo rating
            opponent_elo: Opponent's Elo rating
            result: Match result (1 = win, 0.5 = draw, 0 = loss)
            is_home: Whether team played at home
            
        Returns:
            Updated Elo rating
        """
        # Add home advantage
        if is_home:
            team_elo += self.home_advantage

        # Expected score
        expected = 1 / (1 + 10 ** ((opponent_elo - team_elo) / 400))

        # New rating
        new_rating = team_elo + self.elo_k * (result - expected)

        # Remove home advantage for storage
        if is_home:
            new_rating -= self.home_advantage

        return new_rating

    def initialize_elo_ratings(self, df: pd.DataFrame):
        """
        Initialize Elo ratings for all teams
        """
        team_ids = pd.concat([df["home_team_id"], df["away_team_id"]]).unique()

        for team_id in team_ids:
            if team_id not in self.elo_ratings:
                self.elo_ratings[team_id] = self.elo_initial

        logger.info(f"Initialized Elo ratings for {len(team_ids)} teams")

    def update_elo_ratings(self, row: pd.Series) -> Tuple[float, float]:
        """
        Update Elo ratings for a single match
        
        Returns:
            (home_elo_before_match, away_elo_before_match)
        """
        home_id = row["home_team_id"]
        away_id = row["away_team_id"]

        # Get current ratings
        home_elo = self.elo_ratings.get(home_id, self.elo_initial)
        away_elo = self.elo_ratings.get(away_id, self.elo_initial)

        # Store pre-match ratings
        pre_match_home_elo = home_elo
        pre_match_away_elo = away_elo

        # Determine result
        if row["outcome"] == "H":
            home_result, away_result = 1, 0
        elif row["outcome"] == "D":
            home_result, away_result = 0.5, 0.5
        else:
            home_result, away_result = 0, 1

        # Update ratings
        new_home_elo = self.calculate_elo_rating(home_elo, away_elo, home_result, is_home=True)
        new_away_elo = self.calculate_elo_rating(away_elo, home_elo, away_result, is_home=False)

        self.elo_ratings[home_id] = new_home_elo
        self.elo_ratings[away_id] = new_away_elo

        return pre_match_home_elo, pre_match_away_elo

    def add_elo_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Elo rating features to dataset
        """
        df_copy = df.copy()

        # Initialize ratings
        self.initialize_elo_ratings(df_copy)

        # Calculate Elo for each match
        elo_data = []
        for idx, row in df_copy.iterrows():
            home_elo, away_elo = self.update_elo_ratings(row)
            elo_data.append({
                "home_elo": home_elo,
                "away_elo": away_elo,
                "elo_diff": home_elo - away_elo,
            })

        # Add to dataframe
        elo_df = pd.DataFrame(elo_data)
        df_copy = pd.concat([df_copy.reset_index(drop=True), elo_df], axis=1)

        logger.info("Added Elo rating features")
        return df_copy

    def calculate_rolling_stats(
        self, df: pd.DataFrame, team_id_col: str, stat_cols: List[str], windows: List[int]
    ) -> pd.DataFrame:
        """
        Calculate rolling averages for statistics
        
        Args:
            df: DataFrame with match data
            team_id_col: Column name for team ID
            stat_cols: Columns to calculate rolling stats for
            windows: List of window sizes (e.g., [3, 5, 10])
        """
        df_copy = df.copy()

        for window in windows:
            for stat_col in stat_cols:
                if stat_col in df_copy.columns:
                    col_name = f"{stat_col}_rolling_{window}"
                    df_copy[col_name] = (
                        df_copy.groupby(team_id_col)[stat_col]
                        .transform(lambda x: x.rolling(window, min_periods=1).mean())
                    )

        return df_copy

    def calculate_form_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate team form metrics (weighted recent performance)
        """
        df_copy = df.copy()

        # Calculate points per match for home team
        df_copy["home_points"] = df_copy["outcome"].apply(
            lambda x: 3 if x == "H" else 1 if x == "D" else 0
        )

        # Calculate points per match for away team
        df_copy["away_points"] = df_copy["outcome"].apply(
            lambda x: 3 if x == "A" else 1 if x == "D" else 0
        )

        # Rolling form (last 5 matches)
        for window in FEATURE_CONFIG["rolling_windows"]:
            # Home team form
            df_copy[f"home_form_last_{window}"] = (
                df_copy.groupby("home_team_id")["home_points"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

            # Away team form
            df_copy[f"away_form_last_{window}"] = (
                df_copy.groupby("away_team_id")["away_points"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

        # Form difference
        df_copy["form_diff"] = (
            df_copy["home_form_last_5"] - df_copy["away_form_last_5"]
        )

        logger.info("Calculated form metrics")
        return df_copy

    def calculate_goal_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate goal-related statistics
        """
        df_copy = df.copy()

        windows = FEATURE_CONFIG["rolling_windows"]

        for window in windows:
            # Home team - goals scored/conceded
            df_copy[f"home_goals_scored_avg_{window}"] = (
                df_copy.groupby("home_team_id")["home_goals"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

            df_copy[f"home_goals_conceded_avg_{window}"] = (
                df_copy.groupby("home_team_id")["away_goals"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

            # Away team - goals scored/conceded
            df_copy[f"away_goals_scored_avg_{window}"] = (
                df_copy.groupby("away_team_id")["away_goals"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

            df_copy[f"away_goals_conceded_avg_{window}"] = (
                df_copy.groupby("away_team_id")["home_goals"]
                .transform(lambda x: x.rolling(window, min_periods=1).mean())
            )

        # Expected goals (simple approximation based on shots and league average)
        # In real implementation, would use actual xG data from StatsBomb or similar
        league_avg_goals = df_copy["total_goals"].mean()

        df_copy["home_xG_simple"] = (
            df_copy["home_goals_scored_avg_5"] * 0.7 + league_avg_goals * 0.3
        )
        df_copy["away_xG_simple"] = (
            df_copy["away_goals_scored_avg_5"] * 0.7 + league_avg_goals * 0.3
        )

        # Goal difference trends
        df_copy["home_goal_diff_avg_5"] = (
            df_copy["home_goals_scored_avg_5"] - df_copy["home_goals_conceded_avg_5"]
        )
        df_copy["away_goal_diff_avg_5"] = (
            df_copy["away_goals_scored_avg_5"] - df_copy["away_goals_conceded_avg_5"]
        )

        logger.info("Calculated goal statistics")
        return df_copy

    def calculate_h2h_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate head-to-head statistics
        """
        df_copy = df.copy()

        # Create H2H key
        df_copy["h2h_key"] = df_copy.apply(
            lambda row: tuple(sorted([row["home_team_id"], row["away_team_id"]])),
            axis=1,
        )

        # Calculate H2H stats (last 5 meetings)
        h2h_stats = []

        for idx, row in df_copy.iterrows():
            # Get previous matches between these teams
            h2h_matches = df_copy[
                (df_copy["h2h_key"] == row["h2h_key"]) & (df_copy.index < idx)
            ].tail(5)

            if len(h2h_matches) == 0:
                h2h_stats.append({
                    "h2h_home_wins": 0,
                    "h2h_draws": 0,
                    "h2h_away_wins": 0,
                    "h2h_home_goals_avg": 0,
                    "h2h_away_goals_avg": 0,
                })
            else:
                # Count outcomes
                home_wins = (h2h_matches["home_goals"] > h2h_matches["away_goals"]).sum()
                draws = (h2h_matches["home_goals"] == h2h_matches["away_goals"]).sum()
                away_wins = (h2h_matches["home_goals"] < h2h_matches["away_goals"]).sum()

                h2h_stats.append({
                    "h2h_home_wins": home_wins,
                    "h2h_draws": draws,
                    "h2h_away_wins": away_wins,
                    "h2h_home_goals_avg": h2h_matches["home_goals"].mean(),
                    "h2h_away_goals_avg": h2h_matches["away_goals"].mean(),
                })

        h2h_df = pd.DataFrame(h2h_stats)
        df_copy = pd.concat([df_copy.reset_index(drop=True), h2h_df], axis=1)

        logger.info("Calculated H2H features")
        return df_copy

    def calculate_streak_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate win/loss streaks
        """
        df_copy = df.copy()

        def calculate_streak(group, outcome_col, target_outcome):
            """Calculate current streak for target outcome"""
            streaks = []
            current_streak = 0

            for outcome in group[outcome_col]:
                if outcome == target_outcome:
                    current_streak += 1
                else:
                    current_streak = 0
                streaks.append(current_streak)

            return streaks

        # Home team streaks
        df_copy["home_win_streak"] = (
            df_copy.groupby("home_team_id")
            .apply(lambda g: pd.Series(calculate_streak(g, "outcome", "H"), index=g.index))
            .reset_index(level=0, drop=True)
        )

        df_copy["home_loss_streak"] = (
            df_copy.groupby("home_team_id")
            .apply(lambda g: pd.Series(calculate_streak(g, "outcome", "A"), index=g.index))
            .reset_index(level=0, drop=True)
        )

        # Away team streaks
        df_copy["away_win_streak"] = (
            df_copy.groupby("away_team_id")
            .apply(lambda g: pd.Series(calculate_streak(g, "outcome", "A"), index=g.index))
            .reset_index(level=0, drop=True)
        )

        df_copy["away_loss_streak"] = (
            df_copy.groupby("away_team_id")
            .apply(lambda g: pd.Series(calculate_streak(g, "outcome", "H"), index=g.index))
            .reset_index(level=0, drop=True)
        )

        logger.info("Calculated streak features")
        return df_copy

    def calculate_league_position_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate features based on league standings
        """
        df_copy = df.copy()

        if "home_rank" in df_copy.columns and "away_rank" in df_copy.columns:
            # Rank difference
            df_copy["rank_diff"] = df_copy["home_rank"] - df_copy["away_rank"]

            # Points difference
            if "home_points" in df_copy.columns and "away_points" in df_copy.columns:
                df_copy["points_diff"] = df_copy["home_points"] - df_copy["away_points"]

            logger.info("Calculated league position features")

        return df_copy

    def calculate_poisson_probabilities(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate outcome probabilities using Poisson distribution
        (Based on average goals scored/conceded)
        """
        df_copy = df.copy()

        # Use rolling averages for goals
        if "home_goals_scored_avg_5" not in df_copy.columns:
            logger.warning("Goal statistics not available for Poisson calculation")
            return df_copy

        def poisson_probability(home_lambda, away_lambda, max_goals=10):
            """
            Calculate match outcome probabilities using Poisson
            """
            prob_matrix = np.zeros((max_goals, max_goals))

            for home_goals in range(max_goals):
                for away_goals in range(max_goals):
                    prob_matrix[home_goals, away_goals] = (
                        poisson.pmf(home_goals, home_lambda) * 
                        poisson.pmf(away_goals, away_lambda)
                    )

            # Outcome probabilities
            home_win = np.sum(np.tril(prob_matrix, -1))  # Home scores more
            draw = np.trace(prob_matrix)  # Equal scores
            away_win = np.sum(np.triu(prob_matrix, 1))  # Away scores more

            # Over/Under 2.5 goals
            over_2_5 = 0
            for i in range(max_goals):
                for j in range(max_goals):
                    if i + j > 2.5:
                        over_2_5 += prob_matrix[i, j]

            return home_win, draw, away_win, over_2_5

        # Calculate Poisson probabilities
        poisson_data = []
        for idx, row in df_copy.iterrows():
            home_lambda = row.get("home_goals_scored_avg_5", 1.5)
            away_lambda = row.get("away_goals_scored_avg_5", 1.5)

            if pd.isna(home_lambda) or pd.isna(away_lambda):
                home_lambda, away_lambda = 1.5, 1.5

            home_prob, draw_prob, away_prob, over_prob = poisson_probability(
                home_lambda, away_lambda
            )

            poisson_data.append({
                "poisson_home_prob": home_prob,
                "poisson_draw_prob": draw_prob,
                "poisson_away_prob": away_prob,
                "poisson_over_2_5_prob": over_prob,
            })

        poisson_df = pd.DataFrame(poisson_data)
        df_copy = pd.concat([df_copy.reset_index(drop=True), poisson_df], axis=1)

        logger.info("Calculated Poisson probabilities")
        return df_copy

    def engineer_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all feature engineering steps
        
        Args:
            df: Preprocessed DataFrame
            
        Returns:
            DataFrame with engineered features
        """
        logger.info("Starting feature engineering")

        # Ensure data is sorted by date
        df = df.sort_values(["league_id", "date"]).reset_index(drop=True)

        # 1. Elo ratings
        df = self.add_elo_features(df)

        # 2. Form metrics
        df = self.calculate_form_metrics(df)

        # 3. Goal statistics
        df = self.calculate_goal_statistics(df)

        # 4. H2H features
        df = self.calculate_h2h_features(df)

        # 5. Streak features
        df = self.calculate_streak_features(df)

        # 6. League position features
        df = self.calculate_league_position_features(df)

        # 7. Poisson probabilities
        df = self.calculate_poisson_probabilities(df)

        # Drop intermediate columns
        cols_to_drop = ["h2h_key", "home_points", "away_points"]
        df = df.drop(columns=[col for col in cols_to_drop if col in df.columns])

        logger.info(f"Feature engineering complete. Shape: {df.shape}")
        return df


# Example usage
if __name__ == "__main__":
    from config import LEAGUES

    engineer = FeatureEngineer()

    # Load preprocessed data
    league_id = LEAGUES["Premier League"]["id"]
    season = 2023
    df = pd.read_csv(f"{PROCESSED_DATA_DIR}/league_{league_id}_preprocessed_{season}.csv")

    print("Original shape:", df.shape)

    # Engineer features
    df_featured = engineer.engineer_all_features(df)

    print("Engineered shape:", df_featured.shape)
    print("\nNew features:", [col for col in df_featured.columns if col not in df.columns][:20])

    # Save
    output_file = f"{PROCESSED_DATA_DIR}/league_{league_id}_featured_{season}.csv"
    df_featured.to_csv(output_file, index=False)
    print(f"\nSaved to {output_file}")
