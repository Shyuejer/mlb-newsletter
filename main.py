# main.py

import os
from datetime import datetime
from dotenv import load_dotenv
import pytz

from app.logging_utils import get_logger
from app.standings import fetch_team_meta
from app.schedule import fetch_schedule_for_myt_date, filter_and_annotate_games
from app.pitchers import fetch_pitcher_stats
from app.reuters_flm import fetch_flm_previews
from app.narrative import match_and_summarize
from app.emailer import render_template, send_email


def get_target_dates():
    """
    Map MYT 'today' into the correct US slate date.
    Returns both (target_myt_date, target_us_date).
    """
    MYT = pytz.timezone("Asia/Kuala_Lumpur")
    US_EAST = pytz.timezone("US/Eastern")

    now_myt = datetime.now(MYT)
    target_myt_date = now_myt.date()                   # newsletter header
    target_us_date = now_myt.astimezone(US_EAST).date()  # MLB schedule date

    return target_myt_date, target_us_date


def _val(*candidates, default="—"):
    """Pick the first truthy value from candidates; otherwise default."""
    for c in candidates:
        if c:
            return c
    return default


def prepare_email_context(games, myt_date):
    """
    Pass the annotated game dicts straight to the template.
    Splits by contender flag but does not rename keys.
    """
    contender_games = [g for g in games if g.get("is_contender")]
    other_games = [g for g in games if not g.get("is_contender")]

    target_date_str = myt_date.strftime("%a %d %b %Y")

    return {
        "target_date": target_date_str,
        "contender_games": contender_games,
        "other_games": other_games,
    }


def main():
    load_dotenv()
    log = get_logger("mlb.main")

    # Target dates
    target_myt_date, target_us_date = get_target_dates()
    log.info(f"Newsletter target (MYT): {target_myt_date}, mapped US date: {target_us_date}")

    # 1) Standings / contenders
    team_meta = fetch_team_meta(int(os.getenv("MLB_SEASON", "2025")))
    contenders = sum(1 for v in team_meta.values() if v.get("is_contender"))
    log.info(f"Contenders flagged: {contenders}")

    # 2) Schedule + filter+annotate
    log.info("Fetching schedule (US slate mapped from MYT)…")
    sched = fetch_schedule_for_myt_date(target_us_date)
    games = filter_and_annotate_games(sched, team_meta, contender_only=False)
    log.info(f"Games after contender filter: {len(games)}")

    # 3) Pitcher stats
    ids = {pid for g in games for pid in [g.get("probable_home_id"), g.get("probable_away_id")] if pid}
    log.info(f"Fetching pitcher stats for {len(ids)} probable starters…")
    stat_map = fetch_pitcher_stats(ids)

    # Write stats into the exact keys the template expects
    for g in games:
        ph, pa = g.get("probable_home_id"), g.get("probable_away_id")
        if ph:
            g["home_era"]  = (stat_map.get(ph, {}) or {}).get("ERA")  or g.get("home_era")  or "—"
            g["home_whip"] = (stat_map.get(ph, {}) or {}).get("WHIP") or g.get("home_whip") or "—"
        if pa:
            g["away_era"]  = (stat_map.get(pa, {}) or {}).get("ERA")  or g.get("away_era")  or "—"
            g["away_whip"] = (stat_map.get(pa, {}) or {}).get("WHIP") or g.get("away_whip") or "—"


    # 4) Field Level Media scrape
    flm_articles = fetch_flm_previews(
        max_articles=int(os.getenv("FLM_MAX_LINKS", "25")),
        hours_window=int(os.getenv("FLM_HOURS_WINDOW", "36"))
    )
    log.info(f"Reuters FLM articles fetched: {len(flm_articles)}")

    # 5) Match & summarize (OpenAI optional)
    matched = match_and_summarize(games, flm_articles)
    log.info(f"Narratives matched: {matched}/{len(games)}")

    # 6) Prepare email context expected by email.html
    ctx = prepare_email_context(games, target_myt_date)

    # 7) Render email
    html = render_template("email.html", **ctx)

    # 8) Send (or write to file)
    to = os.getenv("NEWS_RECIPIENTS", "").strip()
    if not to:
        log.info("NEWS_RECIPIENTS not set – writing newsletter_preview.html")
        with open("newsletter_preview.html", "w", encoding="utf-8") as f:
            f.write(html)
    else:
        recipients = [e.strip() for e in to.split(",") if e.strip()]
        log.info(f"Sending email to {len(recipients)} recipient(s)…")
        send_email(
            subject=f"MLB Contender Matchups — {target_myt_date.strftime('%a %d %b %Y')} (MYT)",
            html=html,
            recipients=recipients
        )
        log.info("Email sent.")


if __name__ == "__main__":
    raise SystemExit(main())
