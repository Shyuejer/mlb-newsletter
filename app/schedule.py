# app/schedule.py
import requests
from datetime import datetime
import pytz
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

MLB_API = "https://statsapi.mlb.com/api/v1"
TZ_MYT = pytz.timezone("Asia/Kuala_Lumpur")

def fetch_schedule_for_myt_date(myt_date):
    """
    Fetch schedule for the US slate that corresponds to the given MYT date.
    We query a single date window; StatsAPI interprets internally.
    """
    url = f"{MLB_API}/schedule"
    params = {
        "sportId": 1,
        "startDate": myt_date.isoformat(),
        "endDate": myt_date.isoformat(),
        "hydrate": "probablePitcher,team",
        "language": "en",
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def _to_myt_str(game_iso: str) -> str:
    """
    Convert MLB API 'gameDate' string (e.g. '2025-08-19T04:30:00Z')
    into a plain formatted string in MYT.
    """
    if not game_iso:
        return "TBD"
    if game_iso.endswith("Z"):
        game_iso = game_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(game_iso)  # parse with UTC offset
    dt_myt = dt.astimezone(TZ_MYT)
    return dt_myt.strftime("%a %d %b, %I:%M %p MYT")

def filter_and_annotate_games(schedule_json: dict, team_meta: dict, contender_only: bool = False):
    """
    Keep the raw MLB API game dict intact and annotate it with:
      - home_name, away_name, records
      - contender flags, same_division, same_league
      - probable starters (home_pitcher/away_pitcher) + basic ERA/WHIP placeholders
      - game_iso (raw UTC) and myt_time_str (formatted)
    """
    games = []
    for date in schedule_json.get("dates", []):
        for g in date.get("games", []):
            home_t = g["teams"]["home"]
            away_t = g["teams"]["away"]
            home_id = home_t["team"]["id"]
            away_id = away_t["team"]["id"]

            home_meta = team_meta.get(home_id, {})
            away_meta = team_meta.get(away_id, {})

            # team names (fallback to ID label)
            g["home_name"] = home_t["team"].get("name") or f"Team {home_id}"
            g["away_name"] = away_t["team"].get("name") or f"Team {away_id}"

            # contender flags
            home_is_contender = bool(home_meta.get("is_contender"))
            away_is_contender = bool(away_meta.get("is_contender"))
            is_contender_game = home_is_contender or away_is_contender

            if contender_only and not is_contender_game:
                # if you want ZERO filtering, call with contender_only=False
                continue

            g["home_is_contender"] = home_is_contender
            g["away_is_contender"] = away_is_contender
            g["is_contender"] = is_contender_game
            g["both_contenders"] = home_is_contender and away_is_contender

            # division / league flags
            same_div = (
                home_meta.get("div_id") == away_meta.get("div_id")
                and home_meta.get("div_id") is not None
            )
            same_lg = (
                not same_div
                and home_meta.get("league_id") == away_meta.get("league_id")
                and home_meta.get("league_id") is not None
            )
            g["same_division"] = same_div
            g["same_league"] = same_lg

            # records (string if available)
            home_rec = home_meta.get("record")
            if not home_rec and home_meta.get("w") is not None and home_meta.get("l") is not None:
                home_rec = f"{home_meta['w']}-{home_meta['l']}"
            away_rec = away_meta.get("record")
            if not away_rec and away_meta.get("w") is not None and away_meta.get("l") is not None:
                away_rec = f"{away_meta['w']}-{away_meta['l']}"
            g["home_record"] = home_rec
            g["away_record"] = away_rec

            # probable pitchers (names + IDs); ERA/WHIP placeholders (main.py will fill real stats)
            ph = home_t.get("probablePitcher") or {}
            pa = away_t.get("probablePitcher") or {}
            g["probable_home_id"] = ph.get("id")
            g["probable_away_id"] = pa.get("id")
            g["home_pitcher"] = ph.get("fullName") or "TBD"
            g["away_pitcher"] = pa.get("fullName") or "TBD"
            g["home_era"] = ph.get("era") or "—"
            g["away_era"] = pa.get("era") or "—"
            g["home_whip"] = ph.get("whip") or "—"
            g["away_whip"] = pa.get("whip") or "—"

            # kickoff time (raw + formatted)
            raw_iso = g.get("gameDate")
            g["game_iso"] = raw_iso
            try:
                g["myt_time_str"] = _to_myt_str(raw_iso)
            except Exception as e:
                logging.error(f"Failed to parse gameDate for game {g.get('gamePk')}: {raw_iso} ({e})")
                g["myt_time_str"] = "TBD"

            games.append(g)

    return games
