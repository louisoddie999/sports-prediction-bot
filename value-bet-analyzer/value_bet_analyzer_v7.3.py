"""
╔═════════════════════════════════════════════════════════════════════╗
║           VALUE BET ANALYZER v7.3 — Powered by API-Football         ║
║     Higher Confidence — Signal Convergence — Strict EV Filtering    ║
║     Platt Calibration — League-Wide DC Normalisation — v7.3 Fixes   ║
╚═════════════════════════════════════════════════════════════════════╝

v7.2 calibration fixes:
  Brier improved from 0.30 → 0.22. League tier caps, H2H penalties,
  fallback xG caps, DQ ceilings per tier.

v7.3 calibration fixes (based on 43-sample Brier analysis):
  80–90%% model prob bucket still hitting only 57.9%% — over-trusted H2H.
  Root causes identified and fixed:

  F. [H2H BLEND]     H2H blend reduced from 70/30 → 80/20 (Poisson/H2H).
                     H2H was dominating probability when home_wr=9/10 → pushed
                     blended prob to 85%%+ but real hit rate was ~58%%.
                     Poisson xG model is more reliable — trust it more.

  G. [DC DAMPENER]   Double Chance markets (dc_1x, dc_x2) now apply a 0.96
                     probability dampener before EV calculation.
                     DC covers 2/3 outcomes so bookmakers price them tighter;
                     model was systematically overconfident on DC specifically.
                     Also reduced DC market bonus: dc_1x 4→2, dc_x2 3→1.

  H. [THRESHOLD]     HIGH confidence threshold raised 85→88, MED-HIGH 72→74,
                     MIN_CONFIDENCE 68→70. Forces model to be stricter before
                     calling anything HIGH — fewer picks but higher precision.
"""

import os
import csv
import requests
import json
import math
import time
import sys
import sqlite3
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    class _Noop:
        def __getattr__(self, _): return ""
    Fore = Style = _Noop()
    HAS_COLOR = False

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
def _load_env_file():
    """
    Load a .env file from the script's directory (supports both
    'KEY=value' and Windows 'set KEY=value' formats).
    Does NOT override existing environment variables.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in (".env", "_env", "env.txt"):
        env_path = os.path.join(script_dir, fname)
        if os.path.isfile(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Strip Windows 'set ' prefix
                    if line.lower().startswith("set "):
                        line = line[4:].strip()
                    if "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val
            print(f"  ✓ Loaded env vars from: {env_path}")
            return
    # No .env file found — that's fine, env vars may already be set

_load_env_file()

# [FIX 1] API key from env var — never hardcode secrets
API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
if not API_KEY:
    print("  ⚠  ERROR: API_FOOTBALL_KEY env var not set.")
    print("  ⚠  Set it in your .env file: API_FOOTBALL_KEY=your_key_here\n")

BASE_URL     = "https://v3.football.api-sports.io"
OFFLINE_MODE = False

# [FIX 2] Auto-derive current season (Aug→Dec = new season year; Jan→Jul = prior year)
def _auto_season():
    today = date.today()
    env_s = os.environ.get("SEASON")
    if env_s and env_s.isdigit():
        return int(env_s)
    # Football seasons: new season starts ~August; Jan-Jul = season that started prior year
    return today.year if today.month >= 8 else today.year - 1

CURRENT_SEASON = _auto_season()

# Odds window
MIN_ODDS        = 1.25
MAX_ODDS        = 1.95

# v7.3: tightened thresholds (raised from v7.2 — 80-90% bucket still hitting 57.9%)
# Fewer picks but higher precision. Brier analysis: need stricter gate for HIGH.
MIN_PROBABILITY = 0.60
MIN_EV          = 0.025
MIN_CONFIDENCE  = 70     # was 68
CONF_HIGH       = 88     # was 85 — requires stronger signal alignment for HIGH
CONF_MEDHIGH    = 74     # was 72

# v7.2: data quality requirements (MIN_FIXTURES raised 3→5)
MIN_FIXTURES           = 5
MIN_TEAM_FORM          = 3
MIN_FORM_FOR_HIGH      = 5
MIN_H2H_FOR_HIGH_BONUS = 5

# [FIX 8] Configurable injury penalty cap
INJ_MAX_PENALTY = float(os.environ.get("INJ_MAX_PENALTY", "0.25"))  # 0.0–0.40

MAX_WORKERS     = 4
REQUESTS_PER_MINUTE = 28

# [FIX 10] Token-bucket rate limiter using Semaphore (thread-safe, no race window)
_rate_sem       = threading.Semaphore(1)
_last_req_time  = [0.0]
_rate_lock      = threading.Lock()

HEADERS = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io",
}

EXCLUDED_LEAGUES = {
    "Friendlies Clubs", "Friendlies Women", "World Friendlies",
    "Club Friendlies", "International Champions Cup",
}

# ── v7: new config additions ─────────────────
BOOKMAKER_PRIORITY = [
    "bet365", "bwin", "unibet", "william hill",
    "pinnacle", "betway", "1xbet", "sportybet",
]
CALIB_DB                = os.path.join(os.path.expanduser("~"), ".value_bet_analyzer", "calibration.db")
CALIB_MIN_SAMPLES       = 30
PLATT_LR                = 0.01
PLATT_EPOCHS            = 2000
LEAGUE_RATINGS_TTL_HOURS = 24
# [FIX A] Max probability allowed when xG is form-based (no standings data)
FALLBACK_PROB_CAP        = 0.82

# [FIX 9] Telegram config from env vars
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


# ─────────────────────────────────────────────
#  v7.2: LEAGUE TIER CLASSIFICATION  [FIX C]
# ─────────────────────────────────────────────
# Tier 1 — Top European + major global leagues: no probability cap
# Tier 2 — Secondary domestic leagues: prob capped at 0.88
# Tier 3 — Regional, cup, lower division, unknown: prob capped at 0.78

TIER1_LEAGUES = {
    # England
    "Premier League", "Championship", "FA Cup", "EFL Cup",
    # Spain
    "La Liga", "La Liga 2", "Copa del Rey",
    # Germany
    "Bundesliga", "2. Bundesliga", "DFB Pokal",
    # Italy
    "Serie A", "Serie B", "Coppa Italia",
    # France
    "Ligue 1", "Ligue 2", "Coupe de France",
    # Portugal
    "Primeira Liga", "Liga Portugal 2",
    # Netherlands
    "Eredivisie", "Eerste Divisie",
    # Belgium
    "Pro League",
    # Turkey
    "Süper Lig",
    # Russia
    "Premier League",   # also matched under Russia
    # Brazil
    "Serie A", "Serie B",
    # Argentina
    "Liga Profesional Argentina", "Primera Nacional",
    # Major European competitions
    "UEFA Champions League", "UEFA Europa League",
    "UEFA Conference League", "UEFA Champions League Women",
    # USA
    "MLS",
    # Mexico
    "Liga MX",
    # Major Asian
    "Indian Super League", "J1 League", "K League 1",
    "Saudi Professional League", "Chinese Super League",
    # Africa
    "Egypt Premier League",
}

TIER2_LEAGUES = {
    # Secondary European
    "Scottish Premiership", "Scottish Championship",
    "Ekstraklasa",           # Poland
    "Czech Liga",
    "HNL",                   # Croatia
    "SuperLiga",             # Serbia / Denmark
    "Allsvenskan",           # Sweden
    "Eliteserien",           # Norway
    "Veikkausliiga",         # Finland
    "Super League",          # Greece / Switzerland
    "Super Lig",             # Turkey 2nd
    "Jupiler Pro League",
    "Primeira Liga",
    # South America secondary
    "Brasileirao Serie C",
    "Torneo Betsson",
    "Division Profesional",
    "Division Profesional - Apertura",
    "Division Profesional - Clausura",
    # Asia secondary
    "Thai League 1", "Thai League 2",
    "Vietnam League 1",
    "AFC Champions League",
    # Africa secondary
    "CAF Champions League",
    "Saudi Division 1", "Division 1",
    # Middle East
    "UAE Pro League", "Qatar Stars League",
}

# Everything not in Tier1 or Tier2 is automatically Tier3
TIER_PROB_CAPS = {1: 1.00, 2: 0.88, 3: 0.78}
TIER_DQ_CEILING = {1: 1.00, 2: 0.95, 3: 0.88}  # [FIX D] max DQ per tier


def get_league_tier(league_name: str) -> int:
    """Return 1, 2, or 3 for a given league name."""
    if not league_name:
        return 3
    # Exact match first
    if league_name in TIER1_LEAGUES:
        return 1
    if league_name in TIER2_LEAGUES:
        return 2
    # Partial match (handles country-prefixed names etc.)
    ln = league_name.lower()
    for t1 in TIER1_LEAGUES:
        if t1.lower() in ln or ln in t1.lower():
            return 1
    for t2 in TIER2_LEAGUES:
        if t2.lower() in ln or ln in t2.lower():
            return 2
    return 3


def apply_league_prob_cap(prob: float, league_name: str) -> float:
    """[FIX C] Cap probability based on league tier."""
    tier = get_league_tier(league_name)
    cap  = TIER_PROB_CAPS[tier]
    return min(prob, cap)


def apply_league_dq_ceiling(dq: float, league_name: str) -> float:
    """[FIX D] Cap data quality score based on league tier."""
    tier    = get_league_tier(league_name)
    ceiling = TIER_DQ_CEILING[tier]
    return min(dq, ceiling)


CACHE_DB = os.path.join(os.path.expanduser("~"), ".value_bet_analyzer", "api_cache.db")
_db_lock = threading.Lock()


def _init_db():
    os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
    with sqlite3.connect(CACHE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                key   TEXT PRIMARY KEY,
                data  TEXT NOT NULL,
                ts    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _cache_get(key, ttl_hours=24):
    try:
        with sqlite3.connect(CACHE_DB) as conn:
            row = conn.execute(
                "SELECT data, ts FROM api_cache WHERE key=?", (key,)
            ).fetchone()
            if not row:
                return None
            # TTL check — treat stale entries as cache misses
            try:
                cached_ts = datetime.fromisoformat(row[1])
                age_hours = (datetime.utcnow() - cached_ts).total_seconds() / 3600
                if age_hours > ttl_hours:
                    return None
            except Exception:
                pass   # if ts is unparseable, serve it anyway
            return json.loads(row[0])
    except Exception:
        return None


def _cache_set(key, data):
    try:
        with _db_lock:
            with sqlite3.connect(CACHE_DB) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO api_cache (key, data) VALUES (?,?)",
                    (key, json.dumps(data))
                )
    except Exception:
        pass


# ─────────────────────────────────────────────
#  API HELPER
# ─────────────────────────────────────────────
_session = requests.Session()
_session.headers.update(HEADERS)


def _global_rate_wait():
    """[FIX 10] Thread-safe token-bucket rate limiter using Semaphore.
    Acquires semaphore before computing sleep, releases after — no race window
    between simultaneous threads both reading _last_req_time before either updates it.
    """
    min_gap = 60.0 / REQUESTS_PER_MINUTE
    with _rate_lock:
        now     = time.time()
        elapsed = now - _last_req_time[0]
        wait    = min_gap - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_req_time[0] = time.time()


def api_get(endpoint, params=None, bypass_cache=False, ttl_hours=24):
    if params is None:
        params = {}
    key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
    if not bypass_cache:
        hit = _cache_get(key, ttl_hours=ttl_hours)
        if hit is not None:
            return hit
    if OFFLINE_MODE:
        return []
    for attempt in range(3):
        _global_rate_wait()
        try:
            r = _session.get(f"{BASE_URL}/{endpoint}", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            errs = data.get("errors")
            if errs and errs not in ([], {}):
                msg = str(errs).lower()
                if "limit" in msg or "requests" in msg:
                    print(f"  ⚠ Rate limit — backing off 65s (attempt {attempt+1}/3)")
                    time.sleep(65)
                    continue
                return []
            result = data.get("response", [])
            _cache_set(key, result)
            return result
        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout on {endpoint} (attempt {attempt+1}/3)")
        except requests.exceptions.RequestException:
            pass
    return []


# ─────────────────────────────────────────────
#  FIXTURES
# ─────────────────────────────────────────────
def fetch_fixtures(day: str):
    raw = api_get("fixtures", {"date": day, "timezone": "UTC"})
    return [
        f for f in raw
        if f["fixture"]["status"]["short"] == "NS"
        and f["league"]["name"] not in EXCLUDED_LEAGUES
    ]


def fetch_finished_fixtures(day: str):
    """Fetch finished fixtures for a given date (used by --update).
    Always bypasses cache — the same date key was written as NS fixtures
    earlier in the day and must not be served stale for result resolution.
    """
    raw = api_get("fixtures", {"date": day, "timezone": "UTC"}, bypass_cache=True)
    return [
        f for f in raw
        if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")
        and f["league"]["name"] not in EXCLUDED_LEAGUES
    ]


# ─────────────────────────────────────────────
#  TEAM STATISTICS
# ─────────────────────────────────────────────
def _stats_from_form(matches, team_id):
    if not matches:
        return None
    hsc = hco = hcs = hft = hc = 0
    asc = aco = acs = aft = ac = 0
    for m in matches:
        hg = m["goals"].get("home")
        ag = m["goals"].get("away")
        if hg is None or ag is None:
            continue
        is_home = m["teams"]["home"]["id"] == team_id
        if is_home:
            hsc += hg; hco += ag
            if ag == 0: hcs += 1
            if hg == 0: hft += 1
            hc += 1
        else:
            asc += ag; aco += hg
            if hg == 0: acs += 1
            if ag == 0: aft += 1
            ac += 1
    if hc == 0 and ac == 0:
        return None
    return {
        "fixtures": {"home": {"played": hc}, "away": {"played": ac}},
        "goals": {
            "for":     {"average": {"home": f"{hsc/hc:.2f}" if hc else "1.20",
                                    "away": f"{asc/ac:.2f}" if ac else "1.00"}},
            "against": {"average": {"home": f"{hco/hc:.2f}" if hc else "1.20",
                                    "away": f"{aco/ac:.2f}" if ac else "1.30"}},
        },
        "clean_sheet":     {"home": hcs, "away": acs},
        "failed_to_score": {"home": hft, "away": aft},
    }


def fetch_stats(team_id, league_id):
    s = api_get("teams/statistics", {
        "team": team_id, "league": league_id, "season": CURRENT_SEASON
    })
    if s:
        return s
    recent = fetch_form(team_id, 10)
    return _stats_from_form(recent, team_id) if recent else None


def parse_goals(stats, venue):
    if not stats:
        return (1.2, 1.2, 0.0, 0.0)
    try:
        g  = stats.get("goals", {})
        sc = float(g["for"]["average"].get(venue) or 1.2)
        co = float(g["against"]["average"].get(venue) or 1.2)
        pl = stats.get("fixtures", {}).get(venue, {}).get("played", 0) or 0
        cs = stats.get("clean_sheet", {}).get(venue, 0) or 0
        ft = stats.get("failed_to_score", {}).get(venue, 0) or 0
        return sc, co, (cs / pl if pl else 0.0), (ft / pl if pl else 0.0)
    except Exception:
        return (1.2, 1.2, 0.0, 0.0)


# ─────────────────────────────────────────────
#  HEAD TO HEAD
# ─────────────────────────────────────────────
def fetch_h2h(hid, aid):
    return api_get("fixtures/headtohead", {"h2h": f"{hid}-{aid}", "last": 10, "status": "FT"})


def analyze_h2h(data, home_id, away_id):
    if not data or len(data) < MIN_FIXTURES:
        return None
    hw = aw = dr = bt = o25 = 0
    goals = []
    for m in data:
        rhs = m["goals"]["home"]
        ras = m["goals"]["away"]
        if rhs is None or ras is None:
            continue
        hist_home = m["teams"]["home"]["id"]
        if hist_home == home_id:
            ths, tas = rhs, ras
        elif hist_home == away_id:
            ths, tas = ras, rhs
        else:
            continue
        goals.append(ths + tas)
        if ths > tas:   hw += 1
        elif tas > ths: aw += 1
        else:           dr += 1
        if ths > 0 and tas > 0: bt  += 1
        if ths + tas > 2:       o25 += 1
    n = len(goals)
    if n == 0:
        return None
    return {
        "n":         n,
        "home_wins": hw,  "away_wins": aw,  "draws": dr,
        "home_wr":   hw / n, "away_wr": aw / n, "draw_r": dr / n,
        "btts_r":    bt  / n,
        "over25_r":  o25 / n,
        "over15_r":  sum(1 for g in goals if g > 1) / n,
        "avg_goals": sum(goals) / n,
    }


# ─────────────────────────────────────────────
#  RECENT FORM
# ─────────────────────────────────────────────
def fetch_form(team_id, last=10):
    return api_get("fixtures", {"team": team_id, "last": last, "status": "FT"})


# ─────────────────────────────────────────────
#  v7.1: INJURIES
# ─────────────────────────────────────────────
def fetch_injuries(fid):
    """Fetch injury/suspension list for a fixture. Cached 6h — can change day-of."""
    return api_get("injuries", {"fixture": fid}, ttl_hours=6)


def _injury_factors(injury_data, team_id):
    """
    Returns (atk_factor, def_factor, injured_count) for team_id.

    atk_factor < 1.0 → team's attack is weakened (key forwards/mids out)
    def_factor < 1.0 → team's defense is weakened (key defenders/GK out)
    Both capped at (1.0 - INJ_MAX_PENALTY) — configurable via INJ_MAX_PENALTY env var.
    [FIX 8] Cap is now configurable; default 0.25 (same as before).
    """
    injuries = [
        p for p in (injury_data or [])
        if p.get("team", {}).get("id") == team_id
    ]
    atk_pen = 0.0
    def_pen = 0.0

    for inj in injuries:
        pos    = (inj.get("player", {}).get("type",   "") or "").lower()
        reason = (inj.get("player", {}).get("reason", "") or "").lower()
        # Questionable players count half
        weight = 0.5 if "questionable" in reason else 1.0

        if any(x in pos for x in ("forward", "attacker")):
            atk_pen += 0.07 * weight
        elif "midfielder" in pos:
            atk_pen += 0.035 * weight
            def_pen += 0.015 * weight
        elif "defender" in pos:
            def_pen += 0.05 * weight
        elif "goalkeeper" in pos:
            def_pen += 0.08 * weight

    cap = max(0.0, min(INJ_MAX_PENALTY, 0.50))   # hard-limit cap to [0, 0.50]
    atk_factor = max(1.0 - cap, 1.0 - min(atk_pen, cap))
    def_factor = max(1.0 - cap, 1.0 - min(def_pen, cap))
    return round(atk_factor, 3), round(def_factor, 3), len(injuries)


# ─────────────────────────────────────────────
#  v7.1: API-FOOTBALL PREDICTIONS
# ─────────────────────────────────────────────
def fetch_predictions(fid):
    """Fetch API-Football's own prediction for a fixture. Cached 12h."""
    raw = api_get("predictions", {"fixture": fid}, ttl_hours=12)
    return raw[0] if raw else None


def parse_api_predictions(pred_data):
    """
    Extracts probabilities from API-Football's prediction endpoint.

    Returns dict with keys matching our internal market keys:
      home_win, draw, away_win, dc_1x, dc_x2, dc_12, over25, under25
    Returns None if data is missing or malformed.
    """
    if not pred_data:
        return None
    try:
        pct = pred_data.get("predictions", {}).get("percent", {})

        def to_f(s):
            return float(str(s).replace("%", "").strip()) / 100.0 if s else None

        hw = to_f(pct.get("home"))
        dr = to_f(pct.get("draw"))
        aw = to_f(pct.get("away"))

        result = {}
        if hw is not None: result["home_win"] = hw
        if dr is not None: result["draw"]     = dr
        if aw is not None: result["away_win"] = aw

        if hw is not None and dr is not None:
            result["dc_1x"] = min(hw + dr, 1.0)
            result["dc_12"] = min(hw + (aw or 0.0), 1.0)
        if aw is not None and dr is not None:
            result["dc_x2"] = min(aw + dr, 1.0)
        if hw is not None: result["dnb_home"] = hw
        if aw is not None: result["dnb_away"] = aw

        # under_over: "+2.5" → predict Over 2.5,  "-2.5" → predict Under 2.5
        uo = pred_data.get("predictions", {}).get("under_over", "") or ""
        if uo.startswith("+"):
            result["over25"]  = 0.65
            result["under25"] = 0.35
        elif uo.startswith("-"):
            result["under25"] = 0.65
            result["over25"]  = 0.35

        return result if result else None
    except Exception:
        return None


def _api_pred_rate_for(api_pred, key):
    """Return the API-Football predicted rate for a given market key."""
    if not api_pred:
        return None
    return api_pred.get(key)


def analyze_form(matches, team_id, venue=None):
    if not matches:
        return None
    filtered = []
    for m in matches:
        hid = m["teams"]["home"]["id"]
        aid = m["teams"]["away"]["id"]
        hs  = m["goals"]["home"]
        as_ = m["goals"]["away"]
        if hs is None or as_ is None:
            continue
        if venue == "home" and hid != team_id:
            continue
        if venue == "away" and aid != team_id:
            continue
        filtered.append(m)
    if not filtered:
        return None
    weights = [math.exp(-0.15 * i) for i in range(len(filtered))]
    scored_l = []; conceded_l = []; results = []
    bt = o25 = 0
    for i, m in enumerate(filtered):
        hid = m["teams"]["home"]["id"]
        hs  = m["goals"]["home"]
        as_ = m["goals"]["away"]
        s = hs if hid == team_id else as_
        c = as_ if hid == team_id else hs
        scored_l.append(s); conceded_l.append(c)
        if hs > 0 and as_ > 0: bt  += 1
        if hs + as_ > 2:       o25 += 1
        results.append(("W" if s > c else "D" if s == c else "L", weights[i]))
    if not results:
        return None
    n  = len(results)
    wt = sum(w for _, w in results)
    wp = sum((1.0 if r == "W" else 0.4 if r == "D" else 0.0) * w for r, w in results)

    # v7 fix: compute unweighted W/D/L rates for dc_1x / dc_x2 form signals
    wins   = sum(1 for r, _ in results if r == "W")
    draws  = sum(1 for r, _ in results if r == "D")
    losses = sum(1 for r, _ in results if r == "L")

    return {
        "form_score":   wp / wt,
        "avg_scored":   sum(scored_l)   / n,
        "avg_conceded": sum(conceded_l) / n,
        "btts_r":       bt  / n,
        "over25_r":     o25 / n,
        "over15_r":     sum(1 for s, c in zip(scored_l, conceded_l) if s + c > 1) / n,
        "n":            n,
        "recent":       [r for r, _ in results[:5]],
        # v7: W/D/L rates (unweighted)
        "win_rate":     wins   / n,
        "draw_rate":    draws  / n,
        "loss_rate":    losses / n,
    }


# ─────────────────────────────────────────────
#  v7: LEAGUE RATINGS (Dixon-Coles per-league)
# ─────────────────────────────────────────────
class LeagueRatings:
    """
    Fetches league standings and computes attack/defense strength ratings
    relative to the league-wide average — fixing v6's 2-team micro-average bias.

    Cached per league for LEAGUE_RATINGS_TTL_HOURS hours in memory.
    Falls back to form-based estimate if standings unavailable.
    """

    def __init__(self):
        self._cache = {}          # lid -> (timestamp, ratings_dict)
        self._lock  = threading.Lock()

    def _fetch_standings(self, lid):
        raw = api_get("standings", {"league": lid, "season": CURRENT_SEASON})
        if not raw:
            return None
        # standings response is a list of league objects
        try:
            standings = raw[0]["league"]["standings"][0]
            return standings
        except (IndexError, KeyError, TypeError):
            return None

    def _compute_ratings(self, standings):
        """
        Compute per-team attack/defense ratings normalized to league average.

        Returns dict:
          team_id -> {
            atk_home, def_home,   # strengths when playing at home
            atk_away, def_away,   # strengths when playing away
          }
        Also returns (league_avg_home, league_avg_away) tuple.
        """
        home_scored_list  = []
        away_scored_list  = []

        team_home_scored  = {}   # team_id -> total home goals for
        team_home_conceded= {}
        team_home_played  = {}
        team_away_scored  = {}
        team_away_conceded= {}
        team_away_played  = {}

        for entry in standings:
            tid = entry["team"]["id"]
            h = entry.get("home", {})
            a = entry.get("away", {})

            hp = h.get("played", 0) or 0
            ap = a.get("played", 0) or 0
            hg = (h.get("goals", {}) or {})
            ag = (a.get("goals", {}) or {})

            hsf = hg.get("for",     0) or 0
            hsa = hg.get("against", 0) or 0
            asf = ag.get("for",     0) or 0
            asa = ag.get("against", 0) or 0

            if hp > 0:
                home_scored_list.append(hsf / hp)
                team_home_scored[tid]   = hsf / hp
                team_home_conceded[tid] = hsa / hp
                team_home_played[tid]   = hp

            if ap > 0:
                away_scored_list.append(asf / ap)
                team_away_scored[tid]   = asf / ap
                team_away_conceded[tid] = asa / ap
                team_away_played[tid]   = ap

        if not home_scored_list or not away_scored_list:
            return None, (1.45, 1.15)

        league_avg_home = sum(home_scored_list) / len(home_scored_list)
        league_avg_away = sum(away_scored_list) / len(away_scored_list)

        if league_avg_home <= 0:
            league_avg_home = 1.2
        if league_avg_away <= 0:
            league_avg_away = 1.0

        ratings = {}
        for tid in set(team_home_scored) | set(team_away_scored):
            # Attack strength = team avg goals / league avg
            atk_home = (team_home_scored.get(tid, league_avg_home)  / league_avg_home)
            atk_away = (team_away_scored.get(tid, league_avg_away)   / league_avg_away)
            # Defense strength = team avg goals conceded / league avg scored (opponent perspective)
            def_home = (team_home_conceded.get(tid, league_avg_away) / league_avg_away)
            def_away = (team_away_conceded.get(tid, league_avg_home) / league_avg_home)
            ratings[tid] = {
                "atk_home": max(atk_home, 0.2),
                "def_home": max(def_home, 0.2),
                "atk_away": max(atk_away, 0.2),
                "def_away": max(def_away, 0.2),
            }

        return ratings, (league_avg_home, league_avg_away)

    def _get_for_league(self, lid):
        with self._lock:
            entry = self._cache.get(lid)
            if entry:
                ts, data = entry
                if time.time() - ts < LEAGUE_RATINGS_TTL_HOURS * 3600:
                    return data

        standings = self._fetch_standings(lid)
        if not standings:
            return None

        ratings, league_avgs = self._compute_ratings(standings)
        result = {"ratings": ratings, "league_avgs": league_avgs}

        with self._lock:
            self._cache[lid] = (time.time(), result)

        return result

    def team_strengths(self, lid, season, hid, aid, hfall=None, afall=None):
        """
        Returns (home_xg, away_xg, used_fallback) using league-normalized DC strengths.

        used_fallback=True means standings were unavailable — caller should apply
        a probability cap to prevent false high-confidence from form-only data. [FIX A]
        """
        data = self._get_for_league(lid)

        if data and data["ratings"]:
            ratings = data["ratings"]
            league_avg_home, league_avg_away = data["league_avgs"]

            hr = ratings.get(hid)
            ar = ratings.get(aid)

            if hr and ar:
                home_xg = hr["atk_home"] * ar["def_away"] * league_avg_home
                away_xg = ar["atk_away"] * hr["def_home"] * league_avg_away
                home_xg = max(0.20, min(home_xg, 5.0))
                away_xg = max(0.20, min(away_xg, 5.0))
                return home_xg, away_xg, False   # full standings data — no cap needed

        # Fallback: form-based estimate (v6 behaviour)
        # [FIX A] Flag this so caller caps probabilities at FALLBACK_PROB_CAP
        h_atk = hfall["avg_scored"]   if hfall else 1.2
        h_def = 1 / max(hfall["avg_conceded"] if hfall else 1.2, 0.25)
        a_atk = afall["avg_scored"]   if afall else 1.0
        a_def = 1 / max(afall["avg_conceded"] if afall else 1.2, 0.25)

        avg = (h_atk + a_atk) / 2.0 or 1.0
        h_atk /= avg; a_atk /= avg
        h_def /= avg; a_def /= avg

        # Use league avgs from data if available, else safe defaults
        if data:
            lha, laa = data["league_avgs"]
        else:
            lha, laa = 1.45, 1.15

        home_xg = max(0.20, min(h_atk * a_def * lha, 5.0))
        away_xg = max(0.20, min(a_atk * h_def * laa, 5.0))
        return home_xg, away_xg, True   # fallback — caller applies prob cap



_league_ratings = LeagueRatings()


# ─────────────────────────────────────────────
#  v7: DIXON-COLES TAU + POISSON MARKETS
# ─────────────────────────────────────────────
def _dc_tau(h, a, hxg, axg, rho=-0.12):
    """Dixon-Coles low-score correction factor."""
    if h == 0 and a == 0: return 1.0 - hxg * axg * rho
    if h == 0 and a == 1: return 1.0 + hxg * rho
    if h == 1 and a == 0: return 1.0 + axg * rho
    if h == 1 and a == 1: return 1.0 - rho
    return 1.0


def _pois(lam, k):
    return math.exp(-lam) * (lam ** k) / math.factorial(k) if lam > 0 else 0.0


def poisson_markets(home_xg, away_xg):
    """
    v7: Takes pre-computed xG values (league-normalised by LeagueRatings).
    Applies Dixon-Coles tau correction for low-score cells.
    Renormalises after DC correction.
    """
    hxg = home_xg
    axg = away_xg
    M   = 8

    sm = {
        (h, a): _pois(hxg, h) * _pois(axg, a) * _dc_tau(h, a, hxg, axg)
        for h in range(M) for a in range(M)
    }
    t  = sum(sm.values())
    sm = {k: v / t for k, v in sm.items()}   # renormalise after DC correction

    hw  = sum(v for (h, a), v in sm.items() if h > a)
    dr  = sum(v for (h, a), v in sm.items() if h == a)
    aw  = sum(v for (h, a), v in sm.items() if h < a)
    o25 = sum(v for (h, a), v in sm.items() if h + a > 2)
    o15 = sum(v for (h, a), v in sm.items() if h + a > 1)
    o35 = sum(v for (h, a), v in sm.items() if h + a > 3)
    bt  = sum(v for (h, a), v in sm.items() if h > 0 and a > 0)
    ho  = sum(v for (h, a), v in sm.items() if h > 1)
    ao  = sum(v for (h, a), v in sm.items() if a > 1)
    dnbh = hw / (hw + aw) if hw + aw else 0.5
    dnba = aw / (hw + aw) if hw + aw else 0.5

    return {
        "hxg": round(hxg, 2), "axg": round(axg, 2),
        "home_win":  round(hw,    4), "draw":     round(dr,    4), "away_win":  round(aw,    4),
        "over35":    round(o35,   4),
        "over25":    round(o25,   4), "under25":  round(1-o25, 4),
        "over15":    round(o15,   4), "under15":  round(1-o15, 4),
        "btts":      round(bt,    4), "no_btts":  round(1-bt,  4),
        "dc_1x":     round(hw+dr, 4), "dc_x2":   round(aw+dr, 4), "dc_12": round(hw+aw, 4),
        "home_ov15": round(ho,    4), "away_ov15": round(ao,  4),
        "dnb_home":  round(dnbh,  4), "dnb_away": round(dnba, 4),
    }


# ─────────────────────────────────────────────
#  BOOKMAKER ODDS
# ─────────────────────────────────────────────
def fetch_odds(fid):
    return api_get("odds", {"fixture": fid}, ttl_hours=2)


def _parse_odds(odds_data):
    """
    v7 fix: deterministic bookmaker selection using BOOKMAKER_PRIORITY list.
    First-matching preferred bookmaker wins; falls back to first available.
    """
    bk_map = {}
    for entry in odds_data:
        for bk in entry.get("bookmakers", []):
            name = bk.get("name", "").lower().strip()
            if name and name not in bk_map:
                bk_map[name] = bk.get("bets", [])

    chosen_bets = None
    for preferred in BOOKMAKER_PRIORITY:
        for bk_name, bets in bk_map.items():
            if preferred in bk_name:
                chosen_bets = bets
                break
        if chosen_bets:
            break

    if not chosen_bets and bk_map:
        chosen_bets = next(iter(bk_map.values()))

    out = {}
    for bet in (chosen_bets or []):
        nm   = bet["name"].lower().strip()
        vals = {v["value"]: float(v["odd"]) for v in bet.get("values", []) if "odd" in v}
        out[nm] = vals
    return out


_ODDS_MAP = {
    "home_win":  ("match winner",     "Home"),
    "draw":      ("match winner",     "Draw"),
    "away_win":  ("match winner",     "Away"),
    "dc_1x":     ("double chance",    "Home/Draw"),
    "dc_x2":     ("double chance",    "Draw/Away"),
    "dc_12":     ("double chance",    "Home/Away"),
    "over25":    ("goals over/under", "Over 2.5"),
    "under25":   ("goals over/under", "Under 2.5"),
    "over15":    ("goals over/under", "Over 1.5"),
    "under15":   ("goals over/under", "Under 1.5"),
    "btts":      ("both teams score", "Yes"),
    "no_btts":   ("both teams score", "No"),
    "dnb_home":  ("draw no bet",      "Home"),
    "dnb_away":  ("draw no bet",      "Away"),
    "home_ov15": ("team goals",       "Home Over 1.5"),
    "away_ov15": ("team goals",       "Away Over 1.5"),
}


def real_odds_for(parsed, key):
    if key not in _ODDS_MAP:
        return None
    market, outcome = _ODDS_MAP[key]
    return parsed.get(market, {}).get(outcome)


def est_odds(prob, margin=0.05):
    return round((1.0 / prob) * (1.0 - margin), 2) if prob > 0 else 99.0


# ─────────────────────────────────────────────
#  EXPECTED VALUE
# ─────────────────────────────────────────────
def ev(prob, odds):
    return round(prob * (odds - 1) - (1 - prob), 4) if odds >= 1.01 else -999.0


# ─────────────────────────────────────────────
#  MARKET SELECTOR
# ─────────────────────────────────────────────
_MARKETS = [
    ("over15",    "Over 1.5 Goals"),
    ("btts",      "BTTS YES (GG)"),
    ("no_btts",   "BTTS NO (NG)"),
    ("over25",    "Over 2.5 Goals"),
    ("under25",   "Under 2.5 Goals"),
    ("dc_1x",     "Double Chance 1X ({h} or Draw)"),
    ("dc_x2",     "Double Chance X2 ({a} or Draw)"),
    ("home_win",  "{h} Win (1X2)"),
    ("away_win",  "{a} Win (1X2)"),
    ("dnb_home",  "Draw No Bet — {h}"),
    ("dnb_away",  "Draw No Bet — {a}"),
    ("under15",   "Under 1.5 Goals"),
    ("over35",    "Over 3.5 Goals"),
    ("home_ov15", "{h} Over 1.5 Goals"),
    ("away_ov15", "{a} Over 1.5 Goals"),
    ("dc_12",     "No Draw (Home or Away)"),
]


def select_markets(probs, parsed_odds, hn, an):
    cands = []
    for key, tmpl in _MARKETS:
        p = probs.get(key, 0)

        # [v7.3 Fix G] DC markets: apply dampener before probability/EV checks.
        # DC covers 2/3 outcomes — bookmakers price tight and model over-estimates.
        # 0.96 dampener corrects the ~4-6% systematic overconfidence observed.
        if key in DC_MARKETS:
            p = round(p * DC_DAMPENER, 4)

        if p < MIN_PROBABILITY:
            continue
        label   = tmpl.replace("{h}", hn).replace("{a}", an)
        bk_odd  = real_odds_for(parsed_odds, key)
        is_real = bk_odd is not None
        if not is_real:
            bk_odd = est_odds(p)
        if not (MIN_ODDS <= bk_odd <= MAX_ODDS):
            continue
        e = ev(p, bk_odd)
        if e < MIN_EV:
            continue
        cands.append({
            "key": key, "market": label,
            "prob": p, "odds": bk_odd, "ev": e, "real": is_real,
        })
    cands.sort(key=lambda x: x["ev"], reverse=True)
    return cands


# ─────────────────────────────────────────────
#  v6: SIGNAL CONVERGENCE
# ─────────────────────────────────────────────
_SIGNAL_THRESHOLDS = {
    "over15":   0.62,
    "over25":   0.55,
    "over35":   0.52,
    "btts":     0.52,
    "no_btts":  0.52,
    "under25":  0.52,
    "under15":  0.52,
    "home_win": 0.45,
    "away_win": 0.38,
    "dc_1x":    0.60,
    "dc_x2":    0.55,
    "dc_12":    0.58,
    "dnb_home": 0.52,
    "dnb_away": 0.45,
    "home_ov15":0.52,
    "away_ov15":0.45,
}


def _h2h_rate_for(h2h, key):
    if not h2h:
        return None
    if key == "over15":                              return h2h.get("over15_r")
    if key in ("under15", "no_btts"):                return 1 - h2h.get("over15_r", 0.6)
    if key in ("over25", "over35"):                  return h2h.get("over25_r")
    # [FIX 3] BTTS uses btts_r (how often BOTH teams scored), not over25_r
    if key == "btts":                                return h2h.get("btts_r")
    if key == "under25":                             return 1 - h2h.get("over25_r", 0.5)
    if key in ("home_win", "dnb_home", "dc_1x"):     return h2h.get("home_wr")
    if key in ("away_win", "dnb_away", "dc_x2"):     return h2h.get("away_wr")
    if key == "dc_12":                               return 1 - h2h.get("draw_r", 0.25)
    return None


def _form_rate_for(hf, af, key):
    """
    v7 fix: dc_1x/dc_x2/dc_12 now use actual win_rate + draw_rate
    instead of the always-passing formula that could never return < 0.25.
    """
    if not hf or not af:
        return None
    if key == "over15":
        return (hf.get("over15_r", 0.6) + af.get("over15_r", 0.6)) / 2
    if key in ("under15", "no_btts"):
        return 1 - (hf.get("over15_r", 0.6) + af.get("over15_r", 0.6)) / 2
    if key in ("over25", "over35", "btts"):
        return (hf.get("over25_r", 0.5) + af.get("over25_r", 0.5)) / 2
    if key == "under25":
        return 1 - (hf.get("over25_r", 0.5) + af.get("over25_r", 0.5)) / 2
    if key in ("home_win", "dnb_home"):
        return hf["form_score"]
    if key in ("away_win", "dnb_away"):
        return af["form_score"]
    # v7 fix: was min((form_score + 0.5) / 2, 1.0) — always ≥ 0.25
    if key == "dc_1x":
        return hf.get("win_rate", 0.0) + hf.get("draw_rate", 0.0)
    if key == "dc_x2":
        return af.get("win_rate", 0.0) + af.get("draw_rate", 0.0)
    if key == "dc_12":
        return (hf.get("win_rate", 0.0) + af.get("win_rate", 0.0)) / 2
    return None


def signal_convergence(key, poisson_prob, h2h, hfall, afall, api_pred=None):
    threshold = _SIGNAL_THRESHOLDS.get(key, 0.52)
    signals   = []

    # Signal 1: Poisson model (index 0 — used for HIGH-tier enforcement below)
    poisson_agrees = poisson_prob >= threshold
    signals.append(poisson_agrees)

    # Signal 2: H2H historical rate
    h2h_rate = _h2h_rate_for(h2h, key)
    if h2h_rate is not None:
        signals.append(h2h_rate >= threshold)

    # Signal 3: Recent form rate
    form_rate = _form_rate_for(hfall, afall, key)
    if form_rate is not None:
        signals.append(form_rate >= threshold)

    # Signal 4: API-Football predictions (free 4th signal)
    api_rate = _api_pred_rate_for(api_pred, key)
    if api_rate is not None:
        signals.append(api_rate >= threshold)

    total    = len(signals)
    agreeing = sum(signals)

    # Hard veto: if 3+ signals available and ≤1 agree → reject
    if total >= 3 and agreeing <= 1:
        return -1, total

    # [FIX 6] For full convergence (all signals agree), Poisson must be one of them.
    # This prevents non-Poisson signals from manufacturing false HIGH-tier picks
    # when the core model disagrees.
    if agreeing == total and total >= 3 and not poisson_agrees:
        return agreeing - 1, total   # demote: treated as partial convergence

    return agreeing, total


# ─────────────────────────────────────────────
#  v6: CONFIDENCE SCORING
# ─────────────────────────────────────────────
_MARKET_BONUS = {
    "over15":   4,
    "dc_1x":    2,     # [v7.3 Fix G] was 4 — DC overconfident, reduced bonus
    "dc_x2":    1,     # [v7.3 Fix G] was 3 — DC overconfident, reduced bonus
    "dc_12":    2,
    "dnb_home": 3,
    "dnb_away": 3,
    "btts":     2,
    "no_btts":  2,
    "over25":   1,
    "under25":  1,
    "over35":   2,
}

# [v7.3 Fix G] DC probability dampener — applied before EV calculation.
# DC markets cover 2/3 outcomes; bookmakers price tight; model was ~6% overconfident.
DC_DAMPENER = 0.96
DC_MARKETS  = {"dc_1x", "dc_x2", "dc_12"}


def h2h_support(h2h, key):
    if not h2h:
        return 0.5
    if key == "over15":                           return h2h.get("over15_r", 0.6)
    if key == "under15":                          return 1 - h2h.get("over15_r", 0.6)
    if "over25" in key or key == "btts":          return h2h.get("over25_r", 0.5)
    if "under25" in key or key == "no_btts":      return 1 - h2h.get("over25_r", 0.5)
    if key in ("home_win", "dnb_home"):           return h2h.get("home_wr", 0.5)
    if key in ("away_win", "dnb_away"):           return h2h.get("away_wr", 0.5)
    if key == "dc_1x":  return min(h2h.get("home_wr", 0.5) + h2h.get("draw_r", 0.2), 1.0)
    if key == "dc_x2":  return min(h2h.get("away_wr", 0.5) + h2h.get("draw_r", 0.2), 1.0)
    return 0.55


def form_support(hf, af, key):
    """
    v7 fix: dc_1x/dc_x2 now use win_rate + draw_rate (same fix as _form_rate_for).
    """
    if not hf or not af:
        return 0.5
    if key == "over15":                            return (hf.get("over15_r", 0.6) + af.get("over15_r", 0.6)) / 2
    if key == "under15":                           return 1 - (hf.get("over15_r", 0.6) + af.get("over15_r", 0.6)) / 2
    if key in ("over25", "over35", "btts"):        return (hf.get("over25_r", 0.5) + af.get("over25_r", 0.5)) / 2
    if key in ("under25", "no_btts"):              return 1 - (hf.get("over25_r", 0.5) + af.get("over25_r", 0.5)) / 2
    if key in ("home_win", "dnb_home"):            return hf["form_score"]
    if key in ("away_win", "dnb_away"):            return af["form_score"]
    # v7 fix: was min((form_score + 0.5) / 2, 1.0)
    if key == "dc_1x":  return hf.get("win_rate", 0.0) + hf.get("draw_rate", 0.0)
    if key == "dc_x2":  return af.get("win_rate", 0.0) + af.get("draw_rate", 0.0)
    if key == "dc_12":  return (hf.get("win_rate", 0.0) + af.get("win_rate", 0.0)) / 2
    return 0.55


def confidence_score(prob, h2hs, forms, dq, ev_val, key, h2h, conv_count, conv_total):
    prob_pts = prob * 40
    h2h_pts  = h2hs * 22
    form_pts = forms * 18
    ev_norm  = min(max(ev_val / 0.20, 0), 1)
    ev_pts   = ev_norm * 8

    if conv_count == conv_total and conv_total >= 3:
        conv_pts = 10
    elif conv_count == conv_total and conv_total == 2:
        conv_pts = 6
    elif conv_count >= 2:
        conv_pts = 4
    else:
        conv_pts = 0

    # [Fix E] H2H depth: reward large samples, penalise tiny samples
    # Previously only rewarded large H2H — now actively penalises < 5 matches
    if h2h:
        n = h2h.get("n", 0)
        if n >= MIN_H2H_FOR_HIGH_BONUS:   # 5+
            h2h_depth = 4
        elif n >= 3:
            h2h_depth = 0       # neutral — was +2, now 0 (3 matches not enough to reward)
        else:
            h2h_depth = -4      # actively penalise tiny H2H (was 0, now -4)
    else:
        h2h_depth = -2          # no H2H at all — mild penalty

    # [Fix B] H2H convergence signal weighted by sample size
    # Convergence from 3 matches is weaker than convergence from 10 matches
    if h2h and conv_count >= 2:
        n = h2h.get("n", 0)
        if n < 5:
            conv_pts = round(conv_pts * 0.50)   # halve convergence points for tiny H2H
        elif n < 10:
            conv_pts = round(conv_pts * 0.75)   # reduce for medium H2H

    mkt_pts = _MARKET_BONUS.get(key, 0)

    raw = prob_pts + h2h_pts + form_pts + ev_pts + conv_pts + h2h_depth + mkt_pts
    return round(raw * dq, 1)



# ─────────────────────────────────────────────
#  v7: OUTCOME DETERMINATION
# ─────────────────────────────────────────────
def _determine_result(market_key, home_goals, away_goals):
    """Maps market key + actual score -> 1 (hit) or 0 (miss). None if unknown market."""
    total = home_goals + away_goals
    return {
        "home_win":  int(home_goals > away_goals),
        "away_win":  int(away_goals > home_goals),
        "draw":      int(home_goals == away_goals),
        "over15":    int(total > 1),  "under15": int(total <= 1),
        "over25":    int(total > 2),  "under25": int(total <= 2),
        "over35":    int(total > 3),
        "btts":      int(home_goals > 0 and away_goals > 0),
        "no_btts":   int(not (home_goals > 0 and away_goals > 0)),
        "dc_1x":     int(home_goals >= away_goals),
        "dc_x2":     int(away_goals >= home_goals),
        "dc_12":     int(home_goals != away_goals),
        "dnb_home":  int(home_goals > away_goals),
        "dnb_away":  int(away_goals > home_goals),
        "home_ov15": int(home_goals > 1),
        "away_ov15": int(away_goals > 1),
    }.get(market_key)


# ─────────────────────────────────────────────
#  v7: CALIBRATION DB (Platt scaling)
# ─────────────────────────────────────────────
class CalibrationDB:
    """
    Tracks picks in SQLite and applies Platt scaling after CALIB_MIN_SAMPLES
    resolved outcomes.

    Schema: calibration_log(id, fixture_id, market_key, raw_prob, bk_odds,
                             kickoff, result, logged_at)

    [FIX 7] Per-market Platt params stored in platt_params table.
    A single 'global' row (market_key='__global__') is used as fallback.
    Individual market rows are used when that market has >= CALIB_MIN_SAMPLES samples.
    """

    # Default Platt params structure: market_key -> (A, B)
    _DEFAULT_PARAMS = (1.0, 0.0)

    def __init__(self):
        self._lock   = threading.Lock()
        self._params = {}           # market_key -> (A, B)
        self._A      = 1.0         # global fallback (legacy attribute kept for display)
        self._B      = 0.0
        self._init_schema()
        self._load_platt()

    def _init_schema(self):
        os.makedirs(os.path.dirname(CALIB_DB), exist_ok=True)
        with sqlite3.connect(CALIB_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calibration_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id INTEGER NOT NULL,
                    market_key TEXT    NOT NULL,
                    raw_prob   REAL    NOT NULL,
                    bk_odds    REAL    NOT NULL,
                    kickoff    TEXT,
                    result     INTEGER,          -- 1=hit 0=miss NULL=pending
                    logged_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(fixture_id, market_key)
                )
            """)

            # ── Schema migration: v7.0 → v7.1 ──────────────────────────────
            # Old table had: id INTEGER PRIMARY KEY CHECK(id=1), A, B, n
            # New table has: market_key TEXT UNIQUE, A, B, n
            # Detect old schema by checking for market_key column existence.
            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(platt_params)").fetchall()
            } if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='platt_params'"
            ).fetchone() else set()

            if not existing_cols:
                # Table doesn't exist yet — create fresh
                conn.execute("""
                    CREATE TABLE platt_params (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        market_key TEXT    NOT NULL DEFAULT '__global__',
                        A          REAL    NOT NULL DEFAULT 1.0,
                        B          REAL    NOT NULL DEFAULT 0.0,
                        n          INTEGER NOT NULL DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(market_key)
                    )
                """)
                conn.execute(
                    "INSERT OR IGNORE INTO platt_params(market_key,A,B,n) VALUES('__global__',1.0,0.0,0)"
                )
            elif "market_key" not in existing_cols:
                # Old v7.0 schema detected — migrate it
                print("  ℹ  Migrating platt_params table from v7.0 → v7.1 schema...")
                # Grab old A/B values if any
                old_row = conn.execute("SELECT A, B, n FROM platt_params WHERE id=1").fetchone()
                old_A, old_B, old_n = old_row if old_row else (1.0, 0.0, 0)
                # Drop old table and recreate
                conn.execute("DROP TABLE platt_params")
                conn.execute("""
                    CREATE TABLE platt_params (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        market_key TEXT    NOT NULL DEFAULT '__global__',
                        A          REAL    NOT NULL DEFAULT 1.0,
                        B          REAL    NOT NULL DEFAULT 0.0,
                        n          INTEGER NOT NULL DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(market_key)
                    )
                """)
                # Preserve old global calibration data
                conn.execute(
                    "INSERT INTO platt_params(market_key,A,B,n) VALUES('__global__',?,?,?)",
                    (old_A, old_B, old_n)
                )
                print(f"  ✓  Migration complete. Preserved global A={old_A:.4f} B={old_B:.4f} n={old_n}")
            else:
                # Table already has new schema — just ensure global row exists
                conn.execute(
                    "INSERT OR IGNORE INTO platt_params(market_key,A,B,n) VALUES('__global__',1.0,0.0,0)"
                )

    def _load_platt(self):
        """Load all per-market Platt params from DB into self._params."""
        try:
            with sqlite3.connect(CALIB_DB) as conn:
                rows = conn.execute("SELECT market_key, A, B FROM platt_params").fetchall()
                for mkey, A, B in rows:
                    self._params[mkey] = (A, B)
                global_row = self._params.get("__global__", self._DEFAULT_PARAMS)
                self._A, self._B = global_row
        except Exception:
            pass

    def log_pick(self, fixture_id, market_key, raw_prob, bk_odds, kickoff):
        try:
            with self._lock:
                with sqlite3.connect(CALIB_DB) as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO calibration_log
                           (fixture_id, market_key, raw_prob, bk_odds, kickoff)
                           VALUES (?,?,?,?,?)""",
                        (fixture_id, market_key, raw_prob, bk_odds, kickoff)
                    )
        except Exception:
            pass

    def update_results(self, day_str):
        """
        Fetch finished fixtures for day_str, resolve pending picks.
        Returns count of picks resolved.
        """
        finished = fetch_finished_fixtures(day_str)
        if not finished:
            print(f"  No finished fixtures found for {day_str}.")
            return 0

        fid_scores = {}
        for fx in finished:
            fid = fx["fixture"]["id"]
            hg  = fx["goals"].get("home")
            ag  = fx["goals"].get("away")
            if hg is not None and ag is not None:
                fid_scores[fid] = (int(hg), int(ag))

        resolved = 0
        try:
            with self._lock:
                with sqlite3.connect(CALIB_DB) as conn:
                    pending = conn.execute(
                        "SELECT id, fixture_id, market_key FROM calibration_log WHERE result IS NULL"
                    ).fetchall()

                    for row_id, fid, mkey in pending:
                        score = fid_scores.get(fid)
                        if score is None:
                            continue
                        res = _determine_result(mkey, score[0], score[1])
                        if res is not None:
                            conn.execute(
                                "UPDATE calibration_log SET result=? WHERE id=?",
                                (res, row_id)
                            )
                            resolved += 1
        except Exception as e:
            print(f"  Error updating results: {e}")

        if resolved > 0:
            self._compute_platt()

        return resolved

    def _sigmoid(self, x):
        return 1.0 / (1.0 + math.exp(-x))

    def _compute_platt(self):
        """
        [FIX 7] Gradient descent Platt scaling per market key.
        Fits a global model (market_key='__global__') from all resolved picks,
        plus individual models for each market with >= CALIB_MIN_SAMPLES samples.
        No scipy required.
        """
        try:
            with sqlite3.connect(CALIB_DB) as conn:
                all_rows = conn.execute(
                    "SELECT market_key, raw_prob, result FROM calibration_log WHERE result IS NOT NULL"
                ).fetchall()
        except Exception:
            return

        if len(all_rows) < CALIB_MIN_SAMPLES:
            return

        # Group by market
        from collections import defaultdict
        market_groups = defaultdict(list)
        for mkey, prob, result in all_rows:
            market_groups[mkey].append((prob, result))
        market_groups["__global__"] = [(p, r) for _, p, r in all_rows]

        for mkey, samples in market_groups.items():
            if len(samples) < CALIB_MIN_SAMPLES:
                continue
            probs = [s[0] for s in samples]
            ys    = [s[1] for s in samples]
            n     = len(samples)
            A, B  = 1.0, 0.0
            for _ in range(PLATT_EPOCHS):
                preds = [self._sigmoid(A * p + B) for p in probs]
                dA = sum((preds[i] - ys[i]) * probs[i] for i in range(n)) / n
                dB = sum( preds[i] - ys[i]              for i in range(n)) / n
                A -= PLATT_LR * dA
                B -= PLATT_LR * dB
            self._params[mkey] = (A, B)
            if mkey == "__global__":
                self._A, self._B = A, B
            try:
                with self._lock:
                    with sqlite3.connect(CALIB_DB) as conn:
                        conn.execute(
                            """INSERT INTO platt_params(market_key,A,B,n)
                               VALUES(?,?,?,?)
                               ON CONFLICT(market_key) DO UPDATE
                               SET A=excluded.A, B=excluded.B, n=excluded.n,
                                   updated_at=CURRENT_TIMESTAMP""",
                            (mkey, A, B, n)
                        )
            except Exception:
                pass

    def calibrate(self, raw_prob, market_key=None):
        """
        [FIX 7] Apply per-market Platt scaling if available; fall back to global.
        Returns raw_prob unchanged if no calibration params exist yet.
        """
        # Try market-specific params first
        if market_key and market_key in self._params:
            A, B = self._params[market_key]
        elif "__global__" in self._params:
            A, B = self._params["__global__"]
        else:
            return raw_prob
        if A == 1.0 and B == 0.0:
            return raw_prob
        return round(self._sigmoid(A * raw_prob + B), 4)

    def calibration_stats(self):
        """Print Brier score + 10-bucket reliability diagram."""
        try:
            with sqlite3.connect(CALIB_DB) as conn:
                rows = conn.execute(
                    "SELECT raw_prob, result FROM calibration_log WHERE result IS NOT NULL"
                ).fetchall()
                total   = conn.execute("SELECT COUNT(*) FROM calibration_log").fetchone()[0]
                pending = conn.execute(
                    "SELECT COUNT(*) FROM calibration_log WHERE result IS NULL"
                ).fetchone()[0]
                params  = conn.execute(
                    "SELECT A, B, n FROM platt_params WHERE market_key='__global__'"
                ).fetchone()
                mkt_params = conn.execute(
                    "SELECT market_key, A, B, n FROM platt_params WHERE market_key != '__global__' ORDER BY n DESC"
                ).fetchall()
        except Exception as e:
            print(f"  Cannot load calibration data: {e}")
            return

        n_resolved = len(rows)
        print(f"\n{'='*70}")
        print(f"  CALIBRATION REPORT — v7.3")
        print(f"  Total logged picks : {total}")
        print(f"  Resolved           : {n_resolved}")
        print(f"  Pending            : {pending}")

        if params:
            print(f"  Global Platt  A={params[0]:.4f}  B={params[1]:.4f}  (fit on {params[2]} samples)")
        if mkt_params:
            print(f"\n  Per-Market Platt Params:")
            for mkey, A, B, n in mkt_params:
                print(f"    {mkey:<18}  A={A:.4f}  B={B:.4f}  (n={n})")
        print(f"{'='*70}")

        if n_resolved < 10:
            print(f"  Need at least 10 resolved picks for stats (have {n_resolved}).")
            return

        probs = [r[0] for r in rows]
        ys    = [r[1] for r in rows]

        # Brier score
        brier = sum((probs[i] - ys[i]) ** 2 for i in range(n_resolved)) / n_resolved
        print(f"\n  Brier Score (raw)  : {brier:.4f}  (lower = better; 0=perfect)")

        if self._A != 1.0 or self._B != 0.0:
            cal_probs = [self.calibrate(p) for p in probs]
            brier_cal = sum((cal_probs[i] - ys[i]) ** 2 for i in range(n_resolved)) / n_resolved
            print(f"  Brier Score (cal.) : {brier_cal:.4f}")

        # 10-bucket reliability diagram
        buckets = [[] for _ in range(10)]
        for p, y in zip(probs, ys):
            idx = min(int(p * 10), 9)
            buckets[idx].append((p, y))

        print(f"\n  Reliability Diagram (raw probability):")
        print(f"  {'Bucket':<12} {'Samples':>7} {'Avg Prob':>9} {'Actual %':>9} {'Diff':>7}")
        print(f"  {'-'*50}")
        for i, bucket in enumerate(buckets):
            if not bucket:
                continue
            lo = i * 0.10
            hi = lo + 0.10
            avg_p  = sum(p for p, _ in bucket) / len(bucket)
            avg_y  = sum(y for _, y in bucket) / len(bucket)
            diff   = avg_y - avg_p
            flag   = " *" if abs(diff) > 0.10 else ""
            print(f"  {lo:.0%}–{hi:.0%}      {len(bucket):>7}   {avg_p:>8.1%}   {avg_y:>8.1%}   {diff:>+6.1%}{flag}")
        print()



_calibration_db = CalibrationDB()


# ─────────────────────────────────────────────
#  FIXTURE PIPELINE
# ─────────────────────────────────────────────
def analyze_fixture(fx):
    fi  = fx["fixture"]
    lg  = fx["league"]
    ht  = fx["teams"]["home"]
    at  = fx["teams"]["away"]

    fid = fi["id"]
    hid, aid = ht["id"], at["id"]
    hn,  an  = ht["name"], at["name"]
    lid = lg["id"]
    kickoff = fi.get("date", "")

    # Fetch all data
    hs_raw  = fetch_stats(hid, lid)
    as_raw  = fetch_stats(aid, lid)
    h2h_r   = fetch_h2h(hid, aid)
    hfr     = fetch_form(hid, 10)
    afr     = fetch_form(aid, 10)
    inj_raw = fetch_injuries(fid)
    pred_raw = fetch_predictions(fid)

    # Parse stats
    ha, hc, _, _ = parse_goals(hs_raw, "home")
    aa, ac, _, _ = parse_goals(as_raw, "away")

    # Form — venue-specific (for fallback xG) and overall (for confidence/signals)
    hfh   = analyze_form(hfr, hid, "home")
    afa   = analyze_form(afr, aid, "away")
    hfall = analyze_form(hfr, hid)
    afall = analyze_form(afr, aid)

    # H2H
    h2h = analyze_h2h(h2h_r, hid, aid)

    # v7 fix: compute xG via LeagueRatings (league-normalised DC strengths)
    # [v7.2 Fix A] team_strengths now returns used_fallback flag
    home_xg, away_xg, used_fallback = _league_ratings.team_strengths(
        lid, CURRENT_SEASON, hid, aid, hfh, afa
    )

    # v7.1: apply injury adjustments to xG
    h_atk_f, h_def_f, h_inj_n = _injury_factors(inj_raw, hid)
    a_atk_f, a_def_f, a_inj_n = _injury_factors(inj_raw, aid)
    home_xg = round(max(0.20, min(home_xg * h_atk_f / a_def_f, 5.0)), 3)
    away_xg = round(max(0.20, min(away_xg * a_atk_f / h_def_f, 5.0)), 3)

    # v7.1: parse API-Football predictions (4th convergence signal)
    api_pred = parse_api_predictions(pred_raw)

    # Poisson markets (v7: new signature, DC tau applied internally)
    probs = poisson_markets(home_xg, away_xg)

    # [v7.3 Fix F] H2H blend: 80% Poisson / 20% historical (was 70/30).
    # 70/30 gave too much weight to H2H — when home_wr=9/10 it inflated
    # blended prob to 85%+ but actual hit rate was only 57.9% in that bucket.
    # Poisson xG (league-normalised DC) is more stable signal — trust it more.
    if h2h:
        for pk, hk in [("btts","btts_r"), ("over25","over25_r"),
                       ("home_win","home_wr"), ("away_win","away_wr"),
                       ("over15","over15_r")]:
            probs[pk] = round(0.80 * probs[pk] + 0.20 * h2h[hk], 4)
        probs["no_btts"] = round(1 - probs["btts"],   4)
        probs["under25"] = round(1 - probs["over25"], 4)
        probs["under15"] = round(1 - probs["over15"], 4)
        probs["draw"]    = round(max(0, 1 - probs["home_win"] - probs["away_win"]), 4)
        probs["dc_1x"]   = round(probs["home_win"] + probs["draw"], 4)
        probs["dc_x2"]   = round(probs["away_win"] + probs["draw"], 4)

    # [v7.2 Fix C] League tier — determines prob cap and DQ ceiling
    league_name = lg["name"]
    league_tier = get_league_tier(league_name)

    # [v7.2 Fix A+C] Apply probability caps before market selection
    # Cap 1: fallback xG (no standings data) → max prob = FALLBACK_PROB_CAP
    # Cap 2: league tier cap (Tier3 regional = 0.78, Tier2 = 0.88, Tier1 = no cap)
    prob_cap = TIER_PROB_CAPS[league_tier]
    if used_fallback:
        prob_cap = min(prob_cap, FALLBACK_PROB_CAP)

    if prob_cap < 1.0:
        probs = {k: round(min(v, prob_cap), 4) for k, v in probs.items()}

    # Data quality multiplier
    dq = 1.0
    if not h2h:                                               dq *= 0.82
    if not hfall or hfall["n"] < MIN_TEAM_FORM:               dq *= 0.87
    if not afall or afall["n"] < MIN_TEAM_FORM:               dq *= 0.87
    if not hs_raw:                                            dq *= 0.83
    if not as_raw:                                            dq *= 0.83
    if used_fallback:                                         dq *= 0.88   # [Fix A]
    # [Fix B] H2H sample size: large samples boost DQ, small samples penalise it
    if h2h:
        if h2h["n"] >= 10:    dq = min(dq + 0.05, 1.0)
        elif h2h["n"] >= 5:   dq = min(dq + 0.02, 1.0)
        elif h2h["n"] < 5:    dq *= 0.90   # small H2H — penalise confidence
    # [Fix D] Apply league tier DQ ceiling
    dq = apply_league_dq_ceiling(dq, league_name)


    # Real odds (v7: deterministic bookmaker priority)
    odds_raw    = fetch_odds(fid)
    parsed_odds = _parse_odds(odds_raw) if odds_raw else {}

    # Market candidates
    cands = select_markets(probs, parsed_odds, hn, an)
    if not cands:
        return None

    best_pick  = None
    best_score = -1

    for cand in cands[:3]:
        key = cand["key"]

        conv_count, conv_total = signal_convergence(
            key, probs[key], h2h, hfall, afall, api_pred
        )

        if conv_count == -1:
            continue

        h2hs  = h2h_support(h2h, key)
        forms = form_support(hfall, afall, key)
        cscore = confidence_score(
            cand["prob"], h2hs, forms, dq, cand["ev"],
            key, h2h, conv_count, conv_total
        )

        if cscore > best_score:
            best_score = cscore
            best_pick  = {**cand, "cscore": cscore, "conv": (conv_count, conv_total)}

    if best_pick is None:
        return None

    key    = best_pick["key"]
    cscore = best_pick["cscore"]

    if cscore < MIN_CONFIDENCE:
        return None

    if cscore >= CONF_HIGH:
        conf_label = "HIGH"
        # Estimated odds → demote to MED-HIGH
        if not best_pick["real"]:
            conf_label = "MED-HIGH"
        # [Fix C] Tier 3 leagues or fallback xG → cap at MED-HIGH
        if league_tier >= 3 or used_fallback:
            conf_label = "MED-HIGH"
    elif cscore >= CONF_MEDHIGH:
        conf_label = "MED-HIGH"
    else:
        return None

    if conf_label == "HIGH":
        h_form_n = hfall["n"] if hfall else 0
        a_form_n = afall["n"] if afall else 0
        if h_form_n < MIN_FORM_FOR_HIGH or a_form_n < MIN_FORM_FOR_HIGH:
            conf_label = "MED-HIGH"

    # v7: log pick to calibration DB
    _calibration_db.log_pick(fid, key, best_pick["prob"], best_pick["odds"], kickoff)

    # v7.1: apply per-market Platt calibration [FIX 7]
    prob_calibrated = _calibration_db.calibrate(best_pick["prob"], market_key=key)

    # Reason string
    reasons = []
    if h2h and h2h["n"] >= MIN_FIXTURES:
        n = h2h["n"]
        if key in ("btts", "home_ov15", "away_ov15"):
            reasons.append(f"BTTS {int(h2h['btts_r']*n)}/{n} H2H")
        elif "over25" in key:
            reasons.append(f"O2.5 {int(h2h['over25_r']*n)}/{n} H2H")
        elif "over15" in key:
            reasons.append(f"O1.5 {int(h2h['over15_r']*n)}/{n} H2H")
        elif key in ("home_win", "dc_1x", "dnb_home"):
            reasons.append(f"Home {int(h2h['home_wr']*n)}/{n} H2H")
        elif key in ("away_win", "dc_x2", "dnb_away"):
            reasons.append(f"Away {int(h2h['away_wr']*n)}/{n} H2H")
        elif "under" in key or "no_btts" in key:
            u = int((1 - h2h.get("over25_r" if "25" in key else "over15_r", 0.5)) * n)
            reasons.append(f"U{'2.5' if '25' in key else '1.5'} {u}/{n} H2H")

    if hfall:
        form_str = "".join(hfall["recent"][:5])
        reasons.append(f"{hn[:13]} {form_str}")

    inj_parts = []
    # [FIX 8] Flag when team has >= 3 key injuries with ⚠ warning marker
    if h_inj_n:
        warn = "⚠" if h_inj_n >= 3 else ""
        inj_parts.append(f"{hn[:10]} -{h_inj_n}inj{warn}")
    if a_inj_n:
        warn = "⚠" if a_inj_n >= 3 else ""
        inj_parts.append(f"{an[:10]} -{a_inj_n}inj{warn}")
    if inj_parts:
        reasons.append(" ".join(inj_parts))

    conv_str = f"Conv {best_pick['conv'][0]}/{best_pick['conv'][1]}"
    api_str  = " API✓" if api_pred else ""
    # [v7.2] Show tier and fallback status in reason for transparency
    tier_str = f" [T{league_tier}{'↓' if used_fallback else ''}]" if (league_tier >= 2 or used_fallback) else ""
    reasons.append(f"xG {probs['hxg']}-{probs['axg']} | {conv_str}{api_str}{tier_str}")

    return {
        "fixture_id":     fid,
        "home":           hn, "away":    an,
        "country":        lg["country"], "league": lg["name"],
        "kickoff":        kickoff,
        "market":         best_pick["market"],
        "odds":           best_pick["odds"],
        "odds_src":       "Real" if best_pick["real"] else "Est",
        "prob":           best_pick["prob"],
        "prob_calibrated": prob_calibrated,
        "ev":             best_pick["ev"],
        "conf_score":     cscore,
        "conf_label":     conf_label,
        "xg":             f"{probs['hxg']}-{probs['axg']}",
        "reason":         " | ".join(reasons[:4]),
        "all_markets":    cands[:3],
        "h2h_n":          h2h["n"] if h2h else 0,
        "dq":             round(dq, 2),
        "form_str":       "".join(hfall["recent"][:5]) if hfall else "?????",
        "convergence":    f"{best_pick['conv'][0]}/{best_pick['conv'][1]}",
        "market_key":     key,
        "h_injuries":     h_inj_n,
        "a_injuries":     a_inj_n,
        "api_pred":       bool(api_pred),
        "league_tier":    league_tier,       # v7.2
        "used_fallback":  used_fallback,     # v7.2
        "prob_capped":    prob_cap < 1.0,    # v7.2
    }


# ─────────────────────────────────────────────
#  CONCURRENT RUNNER
# ─────────────────────────────────────────────
def run_all(fixtures):
    total     = len(fixtures)
    qualified = []
    errors    = 0

    print(f"\n  Analyzing {total} fixtures ({MAX_WORKERS} threads)...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fmap = {ex.submit(analyze_fixture, fx): fx for fx in fixtures}
        done = 0
        for fut in as_completed(fmap):
            done += 1
            fx = fmap[fut]
            hn = fx["teams"]["home"]["name"]
            an = fx["teams"]["away"]["name"]
            try:
                r = fut.result()
                if r:
                    qualified.append(r)
                    ic = "[HIGH]" if r["conf_label"] == "HIGH" else "[MED-HI]"
                    print(f"  {ic} [{done:03d}/{total}] {hn} vs {an} — "
                          f"{r['conf_label']} | {r['market'][:40]} | Conv {r['convergence']}")
                else:
                    print(f"  .  [{done:03d}/{total}] {hn} vs {an}", end="\r")
            except Exception:
                errors += 1

    print(f"\n  Done. Picks: {len(qualified)}  Skipped/Errors: {errors}")
    return qualified


# ─────────────────────────────────────────────
#  TELEGRAM NOTIFICATIONS  (sends as .txt file)
# ─────────────────────────────────────────────
def _build_telegram_report(results, day):
    """
    Build a clean, well-structured plain-text report string.
    Designed to be readable as a .txt file attachment in Telegram.
    Sorted: HIGH first, then MED-HIGH, each group sorted by conf_score desc.
    """
    platt_active = (_calibration_db._A != 1.0 or _calibration_db._B != 0.0)
    high  = [r for r in results if r["conf_label"] == "HIGH"]
    medhi = [r for r in results if r["conf_label"] == "MED-HIGH"]
    ap    = sum(r["prob"] for r in results) / len(results)
    ae    = sum(r["ev"]   for r in results) / len(results)
    ar    = sum(r["dq"]   for r in results) / len(results)
    real_c = sum(1 for r in results if r["odds_src"] == "Real")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    W = 60   # report width

    sep  = "=" * W
    thin = "-" * W
    def center(text): return text.center(W)
    def field(label, value, width=W):
        gap = width - len(label) - len(str(value))
        return f"{label}{'.' * max(1, gap)}{value}"

    lines = []

    # ── Header ────────────────────────────────────────────────────────
    lines += [
        sep,
        center("VALUE BET REPORT  v7.3"),
        center(f"Date: {day}   |   Generated: {generated_at}"),
        sep,
        "",
        field("Total Picks",       len(results)),
        field("HIGH Confidence",   len(high)),
        field("MED-HIGH Confidence", len(medhi)),
        field("Avg Model Prob",    f"{ap:.1%}"),
        field("Avg Expected Value",f"+{ae:.1%}"),
        field("Avg Data Quality",  f"{ar:.0%}"),
        field("Real Odds Used",    f"{real_c}/{len(results)}"),
        field("Odds Window",       f"{MIN_ODDS} – {MAX_ODDS}"),
        field("Platt Calibration", "ACTIVE" if platt_active else f"PENDING (need {CALIB_MIN_SAMPLES} samples)"),
        field("Season",            CURRENT_SEASON),
        "",
    ]

    # ── Picks by tier ─────────────────────────────────────────────────
    pick_num = 0
    for tier_label, tier_emoji, tier_picks in [
        ("HIGH CONFIDENCE",    "★★★", high),
        ("MED-HIGH CONFIDENCE","★★☆", medhi),
    ]:
        if not tier_picks:
            continue

        lines += [
            sep,
            center(f"{tier_emoji}  {tier_label}  {tier_emoji}"),
            sep,
            "",
        ]

        for r in tier_picks:
            pick_num += 1
            try:
                ko = datetime.fromisoformat(r["kickoff"].replace("Z", "")).strftime("%H:%M UTC")
            except Exception:
                ko = "?:?? UTC"

            inj_flag = "  [INJURY WARNING]" if "⚠" in r.get("reason", "") else ""
            cal_line  = (f"  {'Calibrated Prob':<22}: {r['prob_calibrated']:.1%}"
                         if platt_active else "")

            lines += [
                thin,
                f"  PICK #{pick_num:02d}  |  {r['conf_label']}  |  Score: {r['conf_score']:.0f}/100{inj_flag}",
                thin,
                f"  {'Match':<22}: {r['home']} vs {r['away']}",
                f"  {'Kick-off':<22}: {ko}",
                f"  {'League':<22}: {r['league']}",
                f"  {'Country':<22}: {r['country']}",
                "",
                f"  {'BET MARKET':<22}: {r['market']}",
                f"  {'Odds':<22}: {r['odds']}  ({r['odds_src']} odds)",
                f"  {'Model Probability':<22}: {r['prob']:.1%}",
            ]
            if cal_line:
                lines.append(cal_line)
            lines += [
                f"  {'Expected Value':<22}: +{r['ev']:.1%}",
                f"  {'xG (Home-Away)':<22}: {r['xg']}",
                f"  {'Signal Convergence':<22}: {r['convergence']}",
                f"  {'H2H Matches Used':<22}: {r['h2h_n']}",
                f"  {'Data Quality':<22}: {r['dq']:.0%}",
                f"  {'Home Form':<22}: {r.get('form_str', '?????')}",
                "",
                f"  REASON  : {r['reason']}",
                "",
            ]

        lines.append("")

    # ── Footer ────────────────────────────────────────────────────────
    lines += [
        sep,
        center("END OF REPORT"),
        center("Value Bet Analyzer v7.3  |  For reference only"),
        center("Always bet responsibly."),
        sep,
    ]

    return "\n".join(lines)


def send_telegram(results, day):
    """
    Sends the value bet report to Telegram as a .txt file attachment.
    Also sends a short summary text message before the file so the
    key stats are visible without opening the attachment.

    Requires env vars:
        TELEGRAM_BOT_TOKEN   e.g. 123456:ABC-...
        TELEGRAM_CHAT_ID     e.g. -1001234567890  or your personal chat ID
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return   # silently skip if not configured

    if not results:
        # Still notify that no picks were found today
        _tg_send_text(f"📊 Value Bet Analyzer v7.3 — {day}\n\nNo qualifying picks found today.")
        return

    high  = [r for r in results if r["conf_label"] == "HIGH"]
    medhi = [r for r in results if r["conf_label"] == "MED-HIGH"]
    ap    = sum(r["prob"] for r in results) / len(results)
    ae    = sum(r["ev"]   for r in results) / len(results)

    # ── 1. Short summary text message (visible without opening file) ──
    summary_lines = [
        f"📊 VALUE BET REPORT — {day}",
        f"{'─' * 30}",
        f"🔴 HIGH confidence  : {len(high)} pick(s)",
        f"🟡 MED-HIGH         : {len(medhi)} pick(s)",
        f"📈 Avg Prob         : {ap:.1%}",
        f"💹 Avg EV           : +{ae:.1%}",
        f"{'─' * 30}",
    ]

    # List HIGH picks in the summary so you see them instantly
    if high:
        summary_lines.append("🔴 HIGH PICKS:")
        for r in high:
            try:
                ko = datetime.fromisoformat(r["kickoff"].replace("Z", "")).strftime("%H:%M")
            except Exception:
                ko = "?"
            inj = " ⚠️" if "⚠" in r.get("reason", "") else ""
            summary_lines.append(
                f"  ⚽ {r['home']} vs {r['away']} ({ko}){inj}\n"
                f"     {r['market']}\n"
                f"     Odds {r['odds']} | Prob {r['prob']:.0%} | EV +{r['ev']:.1%}"
            )
        summary_lines.append("")

    if medhi:
        summary_lines.append("🟡 MED-HIGH PICKS:")
        for r in medhi:
            try:
                ko = datetime.fromisoformat(r["kickoff"].replace("Z", "")).strftime("%H:%M")
            except Exception:
                ko = "?"
            inj = " ⚠️" if "⚠" in r.get("reason", "") else ""
            summary_lines.append(
                f"  ⚽ {r['home']} vs {r['away']} ({ko}){inj}\n"
                f"     {r['market']}\n"
                f"     Odds {r['odds']} | Prob {r['prob']:.0%} | EV +{r['ev']:.1%}"
            )

    summary_lines.append(f"\n📎 Full report attached below.")
    _tg_send_text("\n".join(summary_lines))

    # ── 2. Send full report as .txt file attachment ───────────────────
    report_text = _build_telegram_report(results, day)
    filename    = f"value_bets_{day}.txt"
    _tg_send_file(report_text.encode("utf-8"), filename)


def _tg_send_text(text):
    """Send a plain text message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text":    text,
        }, timeout=10)
        if resp.status_code != 200:
            print(f"  ⚠ Telegram text failed: {resp.status_code} — {resp.text[:120]}")
    except Exception as e:
        print(f"  ⚠ Telegram error: {e}")


def _tg_send_file(content_bytes, filename):
    """Send a file to Telegram using sendDocument."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID},
            files={"document": (filename, content_bytes, "text/plain")},
            timeout=20,
        )
        if resp.status_code == 200:
            print(f"  📨 Telegram: summary + '{filename}' sent to chat {TELEGRAM_CHAT_ID}")
        else:
            print(f"  ⚠ Telegram file failed: {resp.status_code} — {resp.text[:120]}")
    except Exception as e:
        print(f"  ⚠ Telegram file error: {e}")



def display(results, day):
    results.sort(key=lambda x: x["conf_score"], reverse=True)

    platt_active = (_calibration_db._A != 1.0 or _calibration_db._B != 0.0)

    print(f"\n{'='*120}")
    print(f"  VALUE BET REPORT v7.3 — {day}")
    print(f"  Odds {MIN_ODDS}–{MAX_ODDS} | Min Prob {MIN_PROBABILITY:.0%} | "
          f"Min EV +{MIN_EV:.1%} | Only HIGH & MED-HIGH | Picks: {len(results)}")
    if platt_active:
        print(f"  Platt calibration ACTIVE  (global A={_calibration_db._A:.4f}  B={_calibration_db._B:.4f})")
    else:
        print(f"  Platt calibration PENDING ({CALIB_MIN_SAMPLES} resolved samples needed)")
    print(f"{'='*120}\n")

    if not results:
        print("  No qualifying picks today.")
        return

    rows = []
    for i, r in enumerate(results, 1):
        try:
            ko = datetime.fromisoformat(r["kickoff"].replace("Z", "")).strftime("%H:%M")
        except Exception:
            ko = "?"
        ic = "* HIGH" if r["conf_label"] == "HIGH" else "+ MED-HI"

        cal_col = f"{r['prob_calibrated']:.0%}" if platt_active else "-"

        rows.append([
            i,
            r["country"][:14],
            r["league"][:22],
            f"{r['home']} vs {r['away']}"[:36],
            ko,
            r["market"][:38],
            f"{r['odds']} ({r['odds_src']})",
            f"{r['prob']:.0%}",
            cal_col,
            f"+{r['ev']:.1%}",
            f"{r['conf_score']:.0f}",
            ic,
            r.get("convergence", "?"),
            r["reason"][:50],
        ])

    headers = ["#","Country","League","Match","KO",
               "Market","Odds(Src)","Prob","Cal.P","EV","Score","Conf","Conv","Reason"]

    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline",
                       maxcolwidths=[3,14,22,36,5,38,13,5,5,6,5,9,5,50]))
    else:
        print("  " + " | ".join(headers))
        for row in rows:
            print("  " + " | ".join(str(x) for x in row))

    high   = [r for r in results if r["conf_label"] == "HIGH"]
    mh     = [r for r in results if r["conf_label"] == "MED-HIGH"]
    ap     = sum(r["prob"] for r in results) / len(results)
    ae     = sum(r["ev"]   for r in results) / len(results)
    ar     = sum(r["dq"]   for r in results) / len(results)
    real_c = sum(1 for r in results if r["odds_src"] == "Real")
    t1_picks = sum(1 for r in results if r.get("league_tier", 3) == 1)
    t2_picks = sum(1 for r in results if r.get("league_tier", 3) == 2)
    t3_picks = sum(1 for r in results if r.get("league_tier", 3) == 3)
    capped   = sum(1 for r in results if r.get("prob_capped", False))

    print(f"""
  SUMMARY
  ──────────────────────────────────────────
  HIGH confidence     : {len(high)} picks
  MED-HIGH confidence : {len(mh)} picks
  ──────────────────────────────────────────
  Avg model prob      : {ap:.1%}
  Avg expected value  : +{ae:.1%}
  Avg data quality    : {ar:.0%}
  Real odds used      : {real_c}/{len(results)} picks
  Odds range          : {MIN_ODDS}–{MAX_ODDS}
  ──────────────────────────────────────────
  League Tier 1       : {t1_picks} picks  (no prob cap)
  League Tier 2       : {t2_picks} picks  (cap {TIER_PROB_CAPS[2]:.0%})
  League Tier 3       : {t3_picks} picks  (cap {TIER_PROB_CAPS[3]:.0%})
  Prob-capped picks   : {capped}/{len(results)}
  ──────────────────────────────────────────
  Signal convergence  : required (Poisson must agree for HIGH)
  Platt calibration   : {'active (per-market)' if platt_active else 'pending (< 30 resolved)'}
  xG source           : League-normalised Dixon-Coles v7.3
  Telegram            : {'configured ✓' if TELEGRAM_BOT_TOKEN else 'not set'}
""")

    _save(results, day)
    send_telegram(results, day)   # [FIX 9] no-op if env vars not set


def _save(results, day):
    ts = datetime.now().strftime("%H%M%S")
    jf = f"value_bets_v7.3_{day}_{ts}.json"
    cf = f"value_bets_v7.3_{day}_{ts}.csv"

    platt_active = (_calibration_db._A != 1.0 or _calibration_db._B != 0.0)

    rows = [{
        "match":           f"{r['home']} vs {r['away']}",
        "country":         r["country"],
        "league":          r["league"],
        "league_tier":     r.get("league_tier", "?"),
        "kickoff":         r["kickoff"],
        "market":          r["market"],
        "odds":            r["odds"],
        "odds_src":        r["odds_src"],
        "prob":            f"{r['prob']:.1%}",
        "prob_calibrated": f"{r['prob_calibrated']:.1%}" if platt_active else "-",
        "prob_capped":     r.get("prob_capped", False),
        "ev":              f"+{r['ev']:.1%}",
        "conf_label":      r["conf_label"],
        "conf_score":      r["conf_score"],
        "convergence":     r.get("convergence", "?"),
        "xg":              r["xg"],
        "h2h_matches":     r["h2h_n"],
        "data_quality":    f"{r['dq']:.0%}",
        "used_fallback":   r.get("used_fallback", False),
        "reason":          r["reason"],
    } for r in results]

    with open(jf, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    with open(cf, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"  Saved: {jf}  +  {cf}")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
def run(day: str):
    _init_db()
    mode_str = "OFFLINE (cache only)" if OFFLINE_MODE else "LIVE (API + cache)"
    print(f"""
VALUE BET ANALYZER v7.3 — {mode_str}
Season: {CURRENT_SEASON} | Odds: {MIN_ODDS}–{MAX_ODDS} | Min Prob: {MIN_PROBABILITY:.0%} | Min EV: +{MIN_EV:.1%}
HIGH >= {CONF_HIGH} | MED-HIGH >= {CONF_MEDHIGH} | Min Score: {MIN_CONFIDENCE}
Prob caps — T1: none | T2: {TIER_PROB_CAPS[2]:.0%} | T3 regional: {TIER_PROB_CAPS[3]:.0%} | Fallback xG: {FALLBACK_PROB_CAP:.0%}
H2H blend: 80/20 (Poisson/H2H) | DC dampener: {DC_DAMPENER} | T3+fallback → MED-HIGH max
Per-market Platt calibration tracking enabled
""")

    t = time.time()
    print(f"\n{'='*62}\n  Fetching fixtures for {day}...\n{'='*62}")
    fixtures = fetch_fixtures(day)

    # [FIX 11] Optional league name filter
    if LEAGUES_FILTER:
        fixtures = [
            fx for fx in fixtures
            if any(lf.lower() in fx["league"]["name"].lower() for lf in LEAGUES_FILTER)
        ]
        print(f"  League filter applied: {LEAGUES_FILTER}")

    print(f"  Fixtures after filter: {len(fixtures)}")

    if not fixtures:
        print("  No fixtures found.")
        return []

    results = run_all(fixtures)
    print(f"\n  Completed in {time.time()-t:.0f}s  |  "
          f"Fixtures: {len(fixtures)}  |  Picks: {len(results)}")
    display(results, day)
    return results


# ─────────────────────────────────────────────
#  [FIX 11] CLI — argparse with extended flags
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="value_bet_analyzer_v7",
        description="Value Bet Analyzer v7.3 — Football value bet detection with signal convergence",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Positional: optional date
    parser.add_argument(
        "date", nargs="?", default=None,
        help="Date to analyse (YYYY-MM-DD). Defaults to today."
    )

    # Mode flags
    parser.add_argument("--offline",     action="store_true", help="Use cached data only (zero API calls)")
    parser.add_argument("--calibration", action="store_true", help="Show calibration stats and exit")
    parser.add_argument("--update",      metavar="DATE",      help="Resolve pick results for DATE (YYYY-MM-DD)")

    # Threshold overrides [FIX 11]
    parser.add_argument("--min-ev",      type=float, metavar="EV",
                        help=f"Minimum Expected Value (default: {MIN_EV}). E.g. --min-ev 0.03")
    parser.add_argument("--min-conf",    type=int,   metavar="SCORE",
                        help=f"Minimum confidence score (default: {MIN_CONFIDENCE}). E.g. --min-conf 70")
    parser.add_argument("--min-prob",    type=float, metavar="PROB",
                        help=f"Minimum model probability (default: {MIN_PROBABILITY}). E.g. --min-prob 0.60")
    parser.add_argument("--season",      type=int,   metavar="YEAR",
                        help=f"Override season year (default: auto={CURRENT_SEASON}). E.g. --season 2024")
    parser.add_argument("--leagues",     nargs="+",  metavar="NAME",
                        help="Filter to specific league names (partial match, case-insensitive).\n"
                             "E.g. --leagues 'Premier League' Ligue1")

    args = parser.parse_args()

    # Apply offline mode
    if args.offline:
        OFFLINE_MODE = True
        print("\n  OFFLINE MODE — using cached data only, zero API calls")

    # Apply threshold overrides
    if args.min_ev   is not None: MIN_EV          = args.min_ev
    if args.min_conf is not None: MIN_CONFIDENCE  = args.min_conf
    if args.min_prob is not None: MIN_PROBABILITY = args.min_prob
    if args.season   is not None: CURRENT_SEASON  = args.season

    # League filter
    LEAGUES_FILTER = args.leagues or []

    # Mode dispatch
    if args.calibration:
        _calibration_db.calibration_stats()

    elif args.update:
        target_day = args.update
        print(f"\n  Updating results for {target_day}...")
        resolved = _calibration_db.update_results(target_day)
        print(f"  Resolved {resolved} pick(s).")
        if resolved > 0:
            print("  Platt params recomputed (per-market where n >= 30).")
        _calibration_db.calibration_stats()

    else:
        target_day = args.date if args.date else date.today().isoformat()
        run(target_day)

