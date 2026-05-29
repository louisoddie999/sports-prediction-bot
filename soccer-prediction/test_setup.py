"""
Quick Test Script - Test API connections and basic functionality
Run this first to verify everything is working!
"""

import requests
import pandas as pd
from datetime import datetime
import sys

print("=" * 70)
print(" SOCCER PREDICTION BOT - QUICK TEST")
print("=" * 70)
print()

# Import configuration
try:
    from config import (
        API_FOOTBALL_KEY,
        API_FOOTBALL_BASE_URL,
        API_FOOTBALL_HOST,
        FOOTBALL_DATA_ORG_KEY,
        FOOTBALL_DATA_BASE_URL,
        LEAGUES,
    )
    print("[OK] Configuration loaded successfully")
except ImportError as e:
    print(f"[ERROR] Error loading config: {e}")
    sys.exit(1)

print(f"   API-Football Key: {API_FOOTBALL_KEY[:10]}...")
print(f"   Football-Data Key: {FOOTBALL_DATA_ORG_KEY[:10]}...")
print()

# Test 1: API-Football Connection
print("-" * 70)
print("TEST 1: API-Football Connection")
print("-" * 70)

try:
    headers = {
        "x-rapidapi-key": API_FOOTBALL_KEY,
        "x-rapidapi-host": API_FOOTBALL_HOST,
    }
    
    # Get league info for Premier League
    response = requests.get(
        f"{API_FOOTBALL_BASE_URL}/leagues",
        headers=headers,
        params={"id": 39, "season": 2023},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get("errors") and len(data["errors"]) > 0:
            print(f"[ERROR] API Error: {data['errors']}")
        else:
            print("[OK] API-Football is working!")
            if data.get("response"):
                league_info = data["response"][0]
                print(f"   League: {league_info['league']['name']}")
                print(f"   Country: {league_info['country']['name']}")
                print(f"   Season: {league_info['seasons'][0]['year']}")
    else:
        print(f"[ERROR] HTTP Error {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"[ERROR] Connection Error: {e}")

print()

# Test 2: Football-Data.org Connection
print("-" * 70)
print("TEST 2: Football-Data.org Connection")
print("-" * 70)

try:
    headers = {
        "X-Auth-Token": FOOTBALL_DATA_ORG_KEY,
    }
    
    # Get Premier League standings
    response = requests.get(
        f"{FOOTBALL_DATA_BASE_URL}/competitions/PL/standings",
        headers=headers,
        params={"season": 2023},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        print("[OK] Football-Data.org is working!")
        if data.get("standings"):
            standings = data["standings"][0]["table"]
            print(f"   Competition: {data['competition']['name']}")
            print(f"   Top team: {standings[0]['team']['name']}")
            print(f"   Points: {standings[0]['points']}")
    else:
        print(f"[ERROR] HTTP Error {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except Exception as e:
    print(f"[ERROR] Connection Error: {e}")

print()

# Test 3: Check Python Dependencies
print("-" * 70)
print("TEST 3: Python Dependencies")
print("-" * 70)

required_packages = [
    "pandas",
    "numpy",
    "sklearn",
    "requests",
]

missing_packages = []

for package in required_packages:
    try:
        if package == "sklearn":
            import sklearn
        else:
            __import__(package)
        print(f"[OK] {package}")
    except ImportError:
        print(f"[ERROR] {package} - NOT INSTALLED")
        missing_packages.append(package)

if missing_packages:
    print()
    print("[WARNING] Missing packages detected!")
    print("   Install them with:")
    print(f"   py -m pip install {' '.join(missing_packages)}")
else:
    print()
    print("[OK] All dependencies are installed!")

print()

# Test 4: Test Data Processing
print("-" * 70)
print("TEST 4: Data Processing")
print("-" * 70)

try:
    # Create sample dataframe
    sample_data = {
        "home_team": ["Arsenal", "Liverpool", "Chelsea"],
        "away_team": ["Chelsea", "Manchester United", "Tottenham"],
        "home_goals": [2, 1, 0],
        "away_goals": [1, 1, 2],
    }
    
    df = pd.DataFrame(sample_data)
    print("[OK] Pandas is working!")
    print(f"   Created DataFrame with {len(df)} rows")
    
    # Test outcome calculation
    df["outcome"] = df.apply(
        lambda row: "H" if row["home_goals"] > row["away_goals"]
        else "D" if row["home_goals"] == row["away_goals"]
        else "A",
        axis=1
    )
    
    print("[OK] Data processing is working!")
    print(f"   Outcomes: {df['outcome'].tolist()}")
    
except Exception as e:
    print(f"[ERROR] Error: {e}")

print()

# Test 5: Directory Structure
print("-" * 70)
print("TEST 5: Directory Structure")
print("-" * 70)

import os

directories = ["data", "data/raw", "data/processed", "models", "logs"]

for directory in directories:
    if os.path.exists(directory):
        print(f"[OK] {directory}")
    else:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"[OK] {directory} (created)")
        except Exception as e:
            print(f"[ERROR] {directory} - Error: {e}")

print()

# Summary
print("=" * 70)
print(" TEST SUMMARY")
print("=" * 70)
print()
print("[OK] = Working | [ERROR] = Needs attention")
print()
print("Next steps:")
print("1. If all tests passed: Run 'py demo.py' for a demo")
print("2. If API tests failed: Check your API keys in config.py")
print("3. If dependencies failed: Run 'py -m pip install -r requirements.txt'")
print("4. For full pipeline: Run 'py main.py --step train'")
print()
print("=" * 70)
print()
