import os
import random
import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

AUTHOR_URL = "https://www.reuters.com/authors/field-level-media/"
BASE_URL = "https://www.reuters.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}

def _sleep(min_s=1.2, max_s=2.8):
    time.sleep(random.uniform(min_s, max_s))

def _fetch_author_page():
    _sleep()
    r = requests.get(AUTHOR_URL, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.text

def _is_baseball_url(href: str) -> bool:
    return "/sports/baseball/" in href

def fetch_flm_list(max_items=15):
    html = _fetch_author_page()
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.find_all("li", attrs={"data-testid": "StoryCard"}):
        link_tag = li.find("a", attrs={"data-testid": "TitleLink"})
        time_tag = li.find("time")
        if not link_tag:
            continue
        href = link_tag["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        if not _is_baseball_url(href):
            continue

        title = link_tag.get_text(strip=True)
        timestamp = time_tag["datetime"] if time_tag else None
        desc_tag = li.find("p", {"data-testid": "Description"})
        desc = desc_tag.get_text(strip=True) if desc_tag else ""
        items.append({"title": title, "url": href, "datetime": timestamp, "desc": desc})
        if len(items) >= max_items:
            break
    return items

def fetch_article_body(url: str) -> str:
    _sleep(0.8, 1.8)
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    content_div = soup.find("div", class_="article-body__content__17Yit")
    if not content_div:
        return ""
    paras = []
    for div in content_div.find_all("div", attrs={"data-testid": True}):
        dtid = div.get("data-testid", "")
        if dtid.startswith("paragraph-"):
            text = div.get_text(" ", strip=True)
            if text.strip().startswith("--Field Level Media"):
                continue
            paras.append(text)
    return "\n\n".join(paras)

def fetch_flm_previews(max_articles=15, hours_window: int | None = None):
    """
    Returns list[{title,url,datetime(body tz=Z),body_text}]
    Only recent items within `hours_window` if provided (default from env FLM_HOURS_WINDOW or 36).
    """
    if hours_window is None:
        hours_window = int(os.getenv("FLM_HOURS_WINDOW", "36"))
    items = fetch_flm_list(max_items=max_articles)
    now = datetime.now(timezone.utc)
    out = []
    for it in items:
        ts = it.get("datetime")
        keep = True
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                keep = (now - dt) <= timedelta(hours=hours_window)
            except Exception:
                keep = True
        if not keep:
            continue
        body = fetch_article_body(it["url"])
        it["body"] = body
        out.append(it)
    return out
