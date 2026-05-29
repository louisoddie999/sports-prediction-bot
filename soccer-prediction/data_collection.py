"""
Data Collection Module
Handles fetching data from Football APIs (API-Football, Football-Data.org)
"""

import requests
import pandas as pd
import time
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from ratelimit import limits, sleep_and_retry

from config import (
    API_FOOTBALL_KEY,
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_HOST,
    FOOTBALL_DATA_ORG_KEY,
    FOOTBALL_DATA_BASE_URL,
    LEAGUES,
    SEASONS,
    RAW_DATA_DIR,
    REALTIME_CONFIG,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCollector:
    """
    Collects soccer data from multiple APIs with rate limiting and error handling
    """

    def __init__(self):
        self.api_football_headers = {
            "x-rapidapi-key": API_FOOTBALL_KEY,
            "x-rapidapi-host": API_FOOTBALL_HOST,
        }
        self.football_data_headers = {
            "X-Auth-Token": FOOTBALL_DATA_ORG_KEY,
        }

    @sleep_and_retry
    @limits(calls=REALTIME_CONFIG["api_rate_limit"], period=60)
    def _api_football_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Make rate-limited request to API-Football
        
        Args:
            endpoint: API endpoint (e.g., "fixtures", "teams")
            params: Query parameters
            
        Returns:
            JSON response or None if error
        """
        try:
            url = f"{API_FOOTBALL_BASE_URL}/{endpoint}"
            response = requests.get(url, headers=self.api_football_headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("errors"):
                logger.error(f"API Error: {data['errors']}")
                return None

            return data.get("response", [])

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    @sleep_and_retry
    @limits(calls=10, period=60)  # Football-Data.org has stricter limits
    def _football_data_request(self, endpoint: str) -> Optional[Dict]:
        """
        Make rate-limited request to Football-Data.org (Free tier)
        """
        try:
            url = f"{FOOTBALL_DATA_BASE_URL}/{endpoint}"
            response = requests.get(url, headers=self.football_data_headers)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Football-Data request failed: {e}")
            return None

    def fetch_league_fixtures(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Fetch all fixtures for a league season
        
        Args:
            league_id: League ID from API-Football
            season: Year (e.g., 2023)
            
        Returns:
            DataFrame with match data
        """
        logger.info(f"Fetching fixtures for league {league_id}, season {season}")

        params = {"league": league_id, "season": season}
        data = self._api_football_request("fixtures", params)

        if not data:
            logger.warning(f"No data for league {league_id}, season {season}")
            return pd.DataFrame()

        # Parse fixture data
        fixtures = []
        for fixture in data:
            try:
                match_data = {
                    "fixture_id": fixture["fixture"]["id"],
                    "date": fixture["fixture"]["date"],
                    "timestamp": fixture["fixture"]["timestamp"],
                    "league_id": league_id,
                    "season": season,
                    "round": fixture["league"]["round"],
                    "home_team_id": fixture["teams"]["home"]["id"],
                    "home_team_name": fixture["teams"]["home"]["name"],
                    "away_team_id": fixture["teams"]["away"]["id"],
                    "away_team_name": fixture["teams"]["away"]["name"],
                    "home_goals": fixture["goals"]["home"],
                    "away_goals": fixture["goals"]["away"],
                    "status": fixture["fixture"]["status"]["short"],
                    "referee": fixture["fixture"].get("referee"),
                    "venue": fixture["fixture"]["venue"].get("name"),
                    "city": fixture["fixture"]["venue"].get("city"),
                }

                # Add detailed stats if available
                if fixture.get("score"):
                    match_data["halftime_home"] = fixture["score"]["halftime"]["home"]
                    match_data["halftime_away"] = fixture["score"]["halftime"]["away"]

                fixtures.append(match_data)

            except KeyError as e:
                logger.error(f"Error parsing fixture: {e}")
                continue

        df = pd.DataFrame(fixtures)
        logger.info(f"Fetched {len(df)} fixtures")
        return df

    def fetch_team_statistics(
        self, league_id: int, season: int, team_id: int
    ) -> Optional[Dict]:
        """
        Fetch detailed team statistics for a season
        """
        params = {"league": league_id, "season": season, "team": team_id}
        data = self._api_football_request("teams/statistics", params)

        if not data:
            return None

        try:
            stats = data[0]
            return {
                "team_id": team_id,
                "league_id": league_id,
                "season": season,
                "matches_played": stats["fixtures"]["played"]["total"],
                "wins_home": stats["fixtures"]["wins"]["home"],
                "wins_away": stats["fixtures"]["wins"]["away"],
                "draws_home": stats["fixtures"]["draws"]["home"],
                "draws_away": stats["fixtures"]["draws"]["away"],
                "losses_home": stats["fixtures"]["loses"]["home"],
                "losses_away": stats["fixtures"]["loses"]["away"],
                "goals_for_home": stats["goals"]["for"]["total"]["home"],
                "goals_for_away": stats["goals"]["for"]["total"]["away"],
                "goals_against_home": stats["goals"]["against"]["total"]["home"],
                "goals_against_away": stats["goals"]["against"]["total"]["away"],
                "clean_sheets_home": stats["clean_sheet"]["home"],
                "clean_sheets_away": stats["clean_sheet"]["away"],
                "failed_to_score_home": stats["failed_to_score"]["home"],
                "failed_to_score_away": stats["failed_to_score"]["away"],
                "avg_goals_for": stats["goals"]["for"]["average"]["total"],
                "avg_goals_against": stats["goals"]["against"]["average"]["total"],
            }

        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"Error parsing team stats: {e}")
            return None

    def fetch_h2h_records(self, team1_id: int, team2_id: int, last_n: int = 10) -> pd.DataFrame:
        """
        Fetch head-to-head records between two teams
        """
        params = {"h2h": f"{team1_id}-{team2_id}", "last": last_n}
        data = self._api_football_request("fixtures/headtohead", params)

        if not data:
            return pd.DataFrame()

        h2h_matches = []
        for match in data:
            try:
                h2h_matches.append({
                    "fixture_id": match["fixture"]["id"],
                    "date": match["fixture"]["date"],
                    "home_team_id": match["teams"]["home"]["id"],
                    "away_team_id": match["teams"]["away"]["id"],
                    "home_goals": match["goals"]["home"],
                    "away_goals": match["goals"]["away"],
                })
            except KeyError:
                continue

        return pd.DataFrame(h2h_matches)

    def fetch_player_statistics(
        self, league_id: int, season: int, team_id: int
    ) -> pd.DataFrame:
        """
        Fetch player statistics for a team (top scorers, assists)
        """
        params = {"league": league_id, "season": season, "team": team_id}
        data = self._api_football_request("players", params)

        if not data:
            return pd.DataFrame()

        players = []
        for player_data in data:
            try:
                player = player_data["player"]
                stats = player_data["statistics"][0]  # First league stats

                players.append({
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "team_id": team_id,
                    "position": stats["games"]["position"],
                    "matches_played": stats["games"]["appearences"],
                    "minutes": stats["games"]["minutes"],
                    "goals": stats["goals"]["total"] or 0,
                    "assists": stats["goals"]["assists"] or 0,
                    "yellow_cards": stats["cards"]["yellow"] or 0,
                    "red_cards": stats["cards"]["red"] or 0,
                    "rating": stats["games"].get("rating"),
                })
            except (KeyError, IndexError, TypeError):
                continue

        return pd.DataFrame(players)

    def fetch_injuries(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Fetch current injuries for a league
        """
        params = {"league": league_id, "season": season}
        data = self._api_football_request("injuries", params)

        if not data:
            return pd.DataFrame()

        injuries = []
        for injury in data:
            try:
                injuries.append({
                    "player_id": injury["player"]["id"],
                    "player_name": injury["player"]["name"],
                    "team_id": injury["team"]["id"],
                    "team_name": injury["team"]["name"],
                    "injury_type": injury["player"]["type"],
                    "reason": injury["player"]["reason"],
                })
            except KeyError:
                continue

        return pd.DataFrame(injuries)

    def fetch_standings(self, league_id: int, season: int) -> pd.DataFrame:
        """
        Fetch league standings
        """
        params = {"league": league_id, "season": season}
        data = self._api_football_request("standings", params)

        if not data:
            return pd.DataFrame()

        try:
            standings_data = data[0]["league"]["standings"][0]
            standings = []

            for team in standings_data:
                standings.append({
                    "team_id": team["team"]["id"],
                    "team_name": team["team"]["name"],
                    "rank": team["rank"],
                    "points": team["points"],
                    "matches_played": team["all"]["played"],
                    "wins": team["all"]["win"],
                    "draws": team["all"]["draw"],
                    "losses": team["all"]["lose"],
                    "goals_for": team["all"]["goals"]["for"],
                    "goals_against": team["all"]["goals"]["against"],
                    "goal_diff": team["goalsDiff"],
                    "form": team["form"],  # Last 5 matches: W/D/L
                })

            return pd.DataFrame(standings)

        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing standings: {e}")
            return pd.DataFrame()

    def collect_all_data_for_league(self, league_id: int, season: int) -> Dict[str, pd.DataFrame]:
        """
        Collect comprehensive data for a league season
        
        Returns:
            Dictionary with DataFrames: fixtures, team_stats, standings, injuries
        """
        logger.info(f"Collecting all data for league {league_id}, season {season}")

        data = {}

        # 1. Fixtures (matches)
        data["fixtures"] = self.fetch_league_fixtures(league_id, season)
        time.sleep(1)  # Rate limiting

        # 2. Standings
        data["standings"] = self.fetch_standings(league_id, season)
        time.sleep(1)

        # 3. Team statistics
        if not data["fixtures"].empty:
            team_ids = pd.concat([
                data["fixtures"]["home_team_id"],
                data["fixtures"]["away_team_id"]
            ]).unique()

            team_stats = []
            for team_id in team_ids:
                stats = self.fetch_team_statistics(league_id, season, team_id)
                if stats:
                    team_stats.append(stats)
                time.sleep(0.5)  # Rate limiting

            data["team_stats"] = pd.DataFrame(team_stats)

        # 4. Injuries (current season only)
        if season == datetime.now().year:
            data["injuries"] = self.fetch_injuries(league_id, season)
        else:
            data["injuries"] = pd.DataFrame()

        # Save raw data
        self._save_raw_data(data, league_id, season)

        return data

    def _save_raw_data(self, data: Dict[str, pd.DataFrame], league_id: int, season: int):
        """
        Save raw data to CSV files
        """
        for data_type, df in data.items():
            if not df.empty:
                filename = f"{RAW_DATA_DIR}/league_{league_id}_{data_type}_{season}.csv"
                df.to_csv(filename, index=False)
                logger.info(f"Saved {data_type} to {filename}")

    def collect_all_leagues_and_seasons(self):
        """
        Main collection function - fetch data for all configured leagues and seasons
        """
        logger.info("Starting data collection for all leagues and seasons")

        for league_name, league_info in LEAGUES.items():
            league_id = league_info["id"]
            logger.info(f"\n{'='*50}\nCollecting data for {league_name}\n{'='*50}")

            for season in SEASONS:
                try:
                    self.collect_all_data_for_league(league_id, season)
                    time.sleep(2)  # Rate limiting between seasons
                except Exception as e:
                    logger.error(f"Error collecting data for {league_name} {season}: {e}")
                    continue

        logger.info("Data collection complete!")


# Example usage
if __name__ == "__main__":
    collector = DataCollector()

    # Test with a single league/season
    league_id = LEAGUES["Premier League"]["id"]
    season = 2023
    data = collector.collect_all_data_for_league(league_id, season)

    print("\nData Summary:")
    for key, df in data.items():
        print(f"{key}: {len(df)} records")

    # Uncomment to collect all data (WARNING: Takes hours and many API calls)
    # collector.collect_all_leagues_and_seasons()
