import requests

MLB_API = "https://statsapi.mlb.com/api/v1"

def fetch_pitcher_stats(ids: set[int] | list[int]):
    """
    Returns { personId: {"ERA": str|None, "WHIP": str|None} } for season totals
    """
    ids = [str(i) for i in ids if i]
    if not ids:
        return {}

    url = f"{MLB_API}/people"
    params = {
        "personIds": ",".join(ids),
        "hydrate": "stats(group=[pitching],type=[season])"
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()

    out = {}
    for p in data.get("people", []):
        pid = p.get("id")
        era = whip = None
        for st in p.get("stats", []):
            if st.get("type", {}).get("displayName") == "season":
                splits = st.get("splits", [])
                if splits:
                    stat = splits[0].get("stat", {})
                    era = stat.get("era")
                    whip = stat.get("whip")
        out[pid] = {"ERA": era, "WHIP": whip}
    return out
