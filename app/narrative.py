# app/narrative.py
import os
import time
import random
from openai import OpenAI
import re
from app.teams import TEAMS, ALIAS_TO_FULL, FULL_TO_ALIASES


# --- Global OpenAI throttle ---
_LAST_OPENAI_CALL_TS = 0.0
_MIN_INTERVAL = float(os.getenv("OPENAI_MIN_INTERVAL_SEC", "8"))  # seconds


def _summarize_text(text: str, title: str | None = None,
                    matchup_hint: tuple[str|None, str|None] = (None, None)) -> str:
    """
    Summarize to 1–2 sentences with OpenAI if key present, else fallback to first 2 sentences.
    """
    api = os.getenv("OPENAI_API_KEY")
    if api:
        try:
            client = OpenAI(api_key=api)
            t1, t2 = matchup_hint
            hint = f"This article is about {t1} vs {t2}. Keep the preview focused on that matchup.\n\n" if t1 and t2 else ""
            prompt = (
                hint +
                "Write a crisp 1–2 sentence MLB matchup preview from the text below. "
                "Focus on the starting pitchers' recent form and any team trend stakes.\n\n"
                f"Title: {title or ''}\n\n"
                f"Text:\n{text[:1500]}"
            )
            resp = _safe_chat_completion(
                client,
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.2,
                timeout=60,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[WARN] Falling back due to {e}")

    # Fallback: take first ~2 sentences
    parts = [p.strip() for p in text.replace("\n", " ").split(". ") if p.strip()]
    return (". ".join(parts[:2]) + ".") if parts else ""


def _match_title_to_game(title: str, away: str, home: str) -> bool:
    """
    Check if article title matches the away vs home matchup.
    Loosened logic to catch abbreviations and 'vs' formats.
    """
    t = title.lower()
    away_key = away.split()[-1].lower()
    home_key = home.split()[-1].lower()
    return (
        (away.lower() in t and home.lower() in t)
        or (away_key in t and home_key in t)
        or (f"{away_key} vs {home_key}" in t)
        or (f"{home_key} vs {away_key}" in t)
    )

# ---------- NEW: always-on fallback commentary ----------
def _fallback_narrative(g: dict) -> str:
    """
    Build a short, deterministic 1–2 sentence preview from available fields,
    so even non-contender games (or games without FLM articles) get commentary.
    """
    away = g.get("away_name") or g.get("away") or "Away"
    home = g.get("home_name") or g.get("home") or "Home"
    ar = g.get("away_record") or "—"
    hr = g.get("home_record") or "—"

    ap = g.get("away_pitcher") or "TBD"
    hp = g.get("home_pitcher") or "TBD"
    aera = g.get("away_era") or "—"
    awhip = g.get("away_whip") or "—"
    hera = g.get("home_era") or "—"
    hwhip = g.get("home_whip") or "—"

    when = g.get("myt_time_str") or "TBD"
    tag = "division clash" if g.get("same_division") else ("league matchup" if g.get("same_league") else "interleague")

    # sentence 1: stakes/context
    s1 = f"{away} ({ar}) visit {home} ({hr}) in a {tag}; first pitch {when}."

    # sentence 2: probables
    s2 = f"Probables: {ap} (ERA {aera}, WHIP {awhip}) vs {hp} (ERA {hera}, WHIP {hwhip})."

    return f"{s1} {s2}"

def match_and_summarize(games: list[dict], flm_articles: list[dict]) -> int:
    """
    For each game, try to find an FLM article and attach 'narrative' + 'source'.
    Pass a matchup hint into OpenAI to reduce drift.
    Always attach a fallback narrative when no article is matched.
    Returns the number of games with an FLM match.
    """
    # Pre-index articles with detected teams from title + first 2 paragraphs
    indexed = []
    for art in flm_articles:
        title = art.get("title") or ""
        body = art.get("body") or ""
        first2 = _first_two_paras(body)
        t1, t2 = _top_two_teams(title, first2)
        indexed.append({
            "title": title,
            "url": art.get("url"),
            "body": body,
            "t1": t1,
            "t2": t2,
        })

    matched = 0

    for g in games:
        away = g.get("away_name", "") or g.get("away", "") or ""
        home = g.get("home_name", "") or g.get("home", "") or ""

        # 1) strict title match (keeps your current behavior)
        picked = None
        for art in indexed:
            if _match_title_to_game(art["title"], away, home):
                picked = art
                break

        # 2) canonical-name set match using detected top-2 teams
        if not picked:
            g_home_full = _guess_full_from_name(home)
            g_away_full = _guess_full_from_name(away)
            for art in indexed:
                a, b = art["t1"], art["t2"]
                if a and b and g_home_full and g_away_full and {a, b} == {g_home_full, g_away_full}:
                    picked = art
                    break

        # 3) loose single-team title fallback
        if not picked:
            for art in indexed:
                t = art["title"].lower()
                if away.lower() in t or home.lower() in t:
                    picked = art
                    break

        # Summarize (with hint if available) or fallback
        if picked:
            hint = (picked.get("t1"), picked.get("t2"))
            narrative = _summarize_text(picked.get("body", ""), picked.get("title"), hint)
            g["narrative"] = narrative or _fallback_narrative(g)
            g["source"] = picked.get("url")
            matched += 1
        else:
            g["narrative"] = _fallback_narrative(g)
            g["source"] = None

    return matched


def _throttle_openai():
    """
    Enforce a minimum interval between OpenAI calls.
    Process-wide (module-level) throttle; simple and effective for a single worker.
    """
    global _LAST_OPENAI_CALL_TS
    now = time.time()
    wait = _MIN_INTERVAL - (now - _LAST_OPENAI_CALL_TS)
    if wait > 0:
        time.sleep(wait)
    _LAST_OPENAI_CALL_TS = time.time()

def _safe_chat_completion(client, **kwargs):
    """
    Wraps client.chat.completions.create with:
      - pre-call throttle (1 call every _MIN_INTERVAL seconds)
      - light exponential backoff + jitter on HTTP 429
    """
    retries = 5
    backoff = 2.0  # seconds
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            _throttle_openai()
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e)
            last_err = e
            # Handle rate limits only; surface other errors
            if "429" in msg or "rate limit" in msg.lower():
                sleep_s = backoff + random.uniform(0, 1)
                print(f"[429] Rate limited, sleeping {sleep_s:.1f}s (attempt {attempt}/{retries})")
                time.sleep(sleep_s)
                backoff *= 2
                continue
            raise  # non-429, bubble up

    raise RuntimeError(f"OpenAI call failed after retries: {last_err}")

# --- Utilities for article team-detection ---

_WORD_RE_CACHE: dict[str, re.Pattern] = {}

def _first_two_paras(body: str) -> str:
    parts = [p.strip() for p in (body or "").split("\n\n") if p.strip()]
    return "\n\n".join(parts[:2])

def _count_mentions(text: str) -> dict[str, int]:
    """
    Count mentions of each team (by aliases + full name) in the given text.
    Uses word-ish boundaries; supports hyphenated aliases like 'd-backs'.
    """
    text = (text or "").lower()
    counts = {t["full"]: 0 for t in TEAMS}

    for full, aliases in FULL_TO_ALIASES.items():
        for alias in aliases:
            pat = _WORD_RE_CACHE.get(alias)
            if not pat:
                # allow flexible spacing in multi-word aliases
                escaped = re.escape(alias).replace(r"\ ", r"\s+")
                # negative/positive \w boundaries so 'mets' doesn't match 'armetsu'
                pat = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
                _WORD_RE_CACHE[alias] = pat
            hits = pat.findall(text)
            if hits:
                counts[full] += len(hits)
    return counts

def _top_two_teams(title: str, body_first_two_paras: str) -> tuple[str|None, str|None]:
    combined = " ".join([title or "", body_first_two_paras or ""])
    counts = _count_mentions(combined)
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [x for x in ranked if x[1] > 0]
    if len(ranked) >= 2:
        return ranked[0][0], ranked[1][0]
    if len(ranked) == 1:
        return ranked[0][0], None
    return None, None

def _guess_full_from_name(name: str) -> str | None:
    """
    Map schedule/team strings like 'LA Angels', 'St. Louis Cardinals' to canonical full name.
    """
    if not name:
        return None
    n = name.lower()
    # exact full-name hit
    for t in TEAMS:
        if t["full"].lower() == n:
            return t["full"]
    # alias present in string (covers 'Dodgers', 'Angels', 'St. Louis Cardinals', 'TB Rays')
    for alias, full in ALIAS_TO_FULL.items():
        if alias in n:
            # disambiguate 'st. louis' when 'cardinals' absent
            if alias == "st. louis" and "cardinals" not in n:
                continue
            return full
    return None
