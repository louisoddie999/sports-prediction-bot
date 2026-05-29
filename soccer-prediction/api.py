"""
FastAPI Application
Web API for soccer prediction bot
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import pandas as pd
import joblib
import json
from datetime import datetime
import logging

from prediction import MatchPredictor
from data_collection import DataCollector
from config import LEAGUES, RESPONSIBLE_BETTING_WARNING, ETHICAL_NOTES

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Soccer Prediction Bot API",
    description="AI-powered soccer match predictions for major leagues",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models
MODELS = {}
LABEL_ENCODER = None
FEATURE_COLUMNS = []
PREDICTOR = None


# Pydantic models for API
class MatchQuery(BaseModel):
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    league: str = Field(..., description="League name (e.g., 'Premier League')")
    date: Optional[str] = Field(None, description="Match date (YYYY-MM-DD)")


class PredictionResponse(BaseModel):
    match: str
    timestamp: str
    outcome_prediction: Dict
    goal_prediction: Dict
    recommendation: Dict
    warning: str


class HealthResponse(BaseModel):
    status: str
    message: str
    models_loaded: bool


@app.on_event("startup")
async def startup_event():
    """
    Load models on startup
    """
    global MODELS, LABEL_ENCODER, FEATURE_COLUMNS, PREDICTOR

    try:
        # Load models (adjust paths as needed)
        logger.info("Loading models...")

        # Example: Load pre-trained models
        # MODELS["xgboost"] = joblib.load("models/xgboost_model.pkl")
        # MODELS["lightgbm"] = joblib.load("models/lightgbm_model.pkl")
        # LABEL_ENCODER = joblib.load("models/label_encoder.pkl")
        
        # with open("models/feature_columns.json", "r") as f:
        #     FEATURE_COLUMNS = json.load(f)

        # PREDICTOR = MatchPredictor(MODELS, LABEL_ENCODER, FEATURE_COLUMNS)

        # For now, set placeholder
        logger.warning("Models not loaded - using placeholder")
        PREDICTOR = None

        logger.info("Startup complete")

    except Exception as e:
        logger.error(f"Error during startup: {e}")


@app.get("/", response_model=HealthResponse)
async def root():
    """
    Health check endpoint
    """
    return {
        "status": "online",
        "message": "Soccer Prediction Bot API is running",
        "models_loaded": PREDICTOR is not None,
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Detailed health check
    """
    models_loaded = PREDICTOR is not None

    return {
        "status": "healthy" if models_loaded else "models_not_loaded",
        "message": "API is operational" if models_loaded else "Models need to be trained",
        "models_loaded": models_loaded,
    }


@app.get("/leagues")
async def get_leagues():
    """
    Get available leagues
    """
    return {
        "leagues": list(LEAGUES.keys()),
        "details": LEAGUES,
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict_match(query: MatchQuery):
    """
    Predict match outcome
    
    Example:
    {
        "home_team": "Manchester United",
        "away_team": "Liverpool",
        "league": "Premier League",
        "date": "2024-03-15"
    }
    """
    if PREDICTOR is None:
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Please train models first.",
        )

    try:
        # Validate league
        if query.league not in LEAGUES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid league. Available leagues: {list(LEAGUES.keys())}",
            )

        # TODO: Fetch real-time team data and features
        # For now, return example response
        logger.info(f"Prediction request: {query.home_team} vs {query.away_team}")

        # Mock prediction (replace with actual prediction logic)
        prediction = {
            "match": f"{query.home_team} vs {query.away_team}",
            "timestamp": datetime.now().isoformat(),
            "outcome_prediction": {
                "prediction": "H",
                "confidence": 0.65,
                "confidence_level": "MEDIUM",
                "probabilities": {"H": 0.65, "D": 0.20, "A": 0.15},
            },
            "goal_prediction": {
                "most_likely_score": "2-1",
                "most_likely_score_probability": 0.12,
                "expected_total_goals": 2.8,
                "over_2_5_probability": 0.58,
                "under_2_5_probability": 0.42,
                "btts_probability": 0.62,
                "top_5_scores": [
                    {"score": "2-1", "probability": 0.12},
                    {"score": "1-1", "probability": 0.10},
                    {"score": "2-0", "probability": 0.09},
                    {"score": "1-0", "probability": 0.08},
                    {"score": "3-1", "probability": 0.07},
                ],
            },
            "recommendation": {
                "recommendations": [
                    {
                        "market": "Match Result",
                        "bet": "Home Win",
                        "confidence": "MEDIUM",
                        "probability": 0.65,
                        "risk": "MEDIUM",
                    },
                    {
                        "market": "Total Goals",
                        "bet": "Over 2.5",
                        "confidence": "MEDIUM",
                        "probability": 0.58,
                        "risk": "MEDIUM",
                    },
                ],
                "overall_confidence": 0.65,
                "note": "Only bet what you can afford to lose.",
            },
            "warning": RESPONSIBLE_BETTING_WARNING,
        }

        return prediction

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/upcoming")
async def get_upcoming_matches(
    league: str = Query(..., description="League name"),
    days: int = Query(7, description="Days ahead to fetch"),
):
    """
    Get upcoming matches for a league
    """
    if league not in LEAGUES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid league. Available: {list(LEAGUES.keys())}",
        )

    # TODO: Fetch upcoming fixtures from API
    return {
        "league": league,
        "upcoming_matches": [
            {
                "date": "2024-03-15",
                "home_team": "Manchester United",
                "away_team": "Liverpool",
            },
            {
                "date": "2024-03-16",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
            },
        ],
        "note": "This is mock data. Implement real API fetching.",
    }


@app.get("/warnings")
async def get_warnings():
    """
    Get responsible betting warnings and ethical notes
    """
    return {
        "responsible_betting": RESPONSIBLE_BETTING_WARNING,
        "ethical_considerations": ETHICAL_NOTES,
    }


@app.get("/stats")
async def get_model_stats():
    """
    Get model performance statistics
    """
    if PREDICTOR is None:
        raise HTTPException(status_code=503, detail="Models not loaded")

    # TODO: Return actual model statistics
    return {
        "model_accuracy": {
            "xgboost": 0.58,
            "lightgbm": 0.56,
            "ensemble": 0.60,
        },
        "matches_analyzed": 5000,
        "leagues_covered": len(LEAGUES),
        "note": "These are example stats. Replace with actual metrics.",
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "path": str(request.url)},
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc)},
    )


# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
