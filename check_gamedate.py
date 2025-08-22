import requests
from datetime import datetime
import pytz

MLB_API = "https://statsapi.mlb.com/api/v1"
TZ_MYT = pytz.timezone("Asia/Kuala_Lumpur")

def to_myt_str(game_iso: str) -> str:
    """Convert MLB API ISO string into MYT string."""
    if not game_iso:
        return "TBD"
    if game_iso.endswith("Z"):
        game_iso = game_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(game_iso)
    dt_myt = dt.astimezone(TZ_MYT)
    return dt_myt.strftime("%a %d %b, %I:%M %p MYT")

# pick a date — adjust if needed
date = datetime.utcnow().date().isoformat()

url = f"{MLB_API}/schedule"
params = {"sportId": 1, "date": date, "hydrate": "probablePitcher,team"}
r = requests.get(url, params=params, timeout=20)
r.raise_for_status()
data = r.json()

for date_block in data.get("dates", []):
    for g in date_block.get("games", []):
        game_pk = g.get("gamePk")
        game_iso = g.get("gameDate")
        try:
            myt = to_myt_str(game_iso)
        except Exception as e:
            myt = f"ERROR: {e}"
        print(f"Game {game_pk} raw={game_iso} -> MYT={myt}")
