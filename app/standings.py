# app/standings.py

import requests
import logging
import os

log = logging.getLogger("mlb.standings")

MLB_API = "https://statsapi.mlb.com/api/v1/standings"

# Defaults, overridable via env
WC_WINDOW   = float(os.getenv("CONTENDER_WC_CUTOFF_WINDOW", "3.0")) # games behind WC3
RUNAWAY_GAP = float(os.getenv("RUNAWAY_LEADER_GAP", "5.0"))        # games up = runaway


def fetch_team_meta(season: int | None = None) -> dict:
    """
    Convenience wrapper: fetch standings JSON and build team meta.
    """
    standings_json = fetch_standings_json(season)
    return build_team_meta(standings_json)


def fetch_standings_json(season: int | None = None) -> dict:
    params = {"leagueId": "103,104", "standingsTypes": "regularSeason"}
    if season:
        params["season"] = season
    r = requests.get(MLB_API, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def build_team_meta(standings_json: dict) -> dict:
    """
    Returns mapping team_id -> {name, div_id, league_id, is_div_leader,
                                gb_div, gb_wc, is_contender}
    Rules:
      1. Always include all current playoff teams (3 div leaders + WC1–WC3).
      2. Also include anyone within WC_WINDOW of WC3.
      3. Exclude runaway division leaders (> RUNAWAY_GAP up).
    """

    team_meta: dict[int, dict] = {}
    league_cutoffs: dict[int, float] = {}  # league_id -> WC3 GB

    # First pass: record division structure & teams
    for rec in standings_json.get("records", []):
        div_id = rec["division"]["id"]
        lg_id = rec["league"]["id"]

        for teamrec in rec["teamRecords"]:
            tid = teamrec["team"]["id"]
            team_meta[tid] = {
                    "name": teamrec["team"]["name"],
                    "abbrev": teamrec["team"].get("abbreviation")
                            or teamrec["team"].get("teamCode")
                            or str(teamrec["team"]["id"]),
                    "league_id": lg_id,
                    "div_id": div_id,
                    "w": teamrec["wins"],
                    "l": teamrec["losses"],
                    "record": f"{teamrec['wins']}-{teamrec['losses']}",  # ✅ add here
                    "gb_div": _parse_gb(teamrec.get("gamesBack", "0.0")),
                    "is_div_leader": False,
                    "gb_wc": None,
                    "is_contender": False,
                }
    # Mark division leaders
    for rec in standings_json.get("records", []):
        leader = rec["teamRecords"][0]
        leader_id = leader["team"]["id"]
        team_meta[leader_id]["is_div_leader"] = True

    # Compute WC cutoff (3rd WC in each league)
    for lg in (103, 104):
        wc_teams = [
            (tid, meta)
            for tid, meta in team_meta.items()
            if meta["league_id"] == lg and not meta["is_div_leader"]
        ]
        wc_sorted = sorted(wc_teams, key=lambda x: (-x[1]["w"], x[1]["l"]))
        if len(wc_sorted) >= 3:
            cutoff_id, _ = wc_sorted[2]
            league_cutoffs[lg] = _games_behind_wc(wc_sorted, cutoff_id)

    # Assign GB to WC cutoff
    for tid, meta in team_meta.items():
        lg = meta["league_id"]
        if lg not in league_cutoffs:
            continue
        cutoff_gb = league_cutoffs[lg]
        # Only non-division leaders matter for WC distance
        if not meta["is_div_leader"]:
            meta["gb_wc"] = cutoff_gb  # treat WC3 as reference point
        else:
            meta["gb_wc"] = 0.0  # div leaders are "in" already

    # Decide contenders
    for tid, meta in team_meta.items():
        is_div_leader = meta["is_div_leader"]

        # Rule 1: playoff lock
        in_playoff = is_div_leader or _is_top3_wc(tid, team_meta)

        # Rule 2: near WC cutoff (bubble)
        near_wc = meta["gb_wc"] is not None and meta["gb_wc"] <= WC_WINDOW

        # Rule 3: filter out runaway division leaders
        runaway = is_div_leader and _div_lead_margin(team_meta, meta) > RUNAWAY_GAP

        meta["is_contender"] = (in_playoff or near_wc) and not runaway

    return team_meta


def _parse_gb(gb_str: str) -> float:
    try:
        return 0.0 if gb_str in ("-", "0") else float(gb_str)
    except Exception:
        return None


def _is_top3_wc(team_id: int, team_meta: dict) -> bool:
    lg = team_meta[team_id]["league_id"]
    wc_teams = [
        (tid, meta)
        for tid, meta in team_meta.items()
        if meta["league_id"] == lg and not meta["is_div_leader"]
    ]
    wc_sorted = sorted(wc_teams, key=lambda x: (-x[1]["w"], x[1]["l"]))
    return any(tid == team_id for tid, _ in wc_sorted[:3])


def _div_lead_margin(team_meta: dict, leader_meta: dict) -> float:
    """Return games up of a division leader vs 2nd place in division."""
    div_id = leader_meta["div_id"]
    same_div = [m for m in team_meta.values() if m["div_id"] == div_id]
    sorted_div = sorted(same_div, key=lambda m: (-m["w"], m["l"]))
    if len(sorted_div) < 2:
        return 0.0
    second = sorted_div[1]
    return (leader_meta["w"] - second["w"]) + (second["l"] - leader_meta["l"]) / 2.0


def _games_behind_wc(wc_sorted: list, cutoff_id: int) -> float:
    """Helper to compute GB at WC3 — treat WC3 as reference (0)."""
    cutoff_meta = [m for tid, m in wc_sorted if tid == cutoff_id][0]
    return cutoff_meta.get("gb_div", 0.0)
