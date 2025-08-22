# MLB Contender Matchups Newsletter (Local-first)

This repo generates a nightly email (11 PM MYT target when you later use GitHub Actions) with **only meaningful MLB matchups**:
- Contender-focused filtering via MLB Stats API
- Probable starters with **ERA & WHIP**
- 1–2 sentence **Field Level Media** (Reuters) summary per game
- Badges for **Same division / Same league / Interleague**
- Runs locally first, then can be scheduled in the cloud later

## Quick start (Laptop)

1) Python 3.11 recommended. Create venv and install:
```bash
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2) Create your `.env` from the example:
```bash
cp .env.example .env
# edit and set OPENAI_API_KEY at minimum
```

3) Run it:
```bash
python main.py
```
You should see console output of selected games. If NEWS_RECIPIENTS is set and GMAIL_USER/PASS are in .env, it will send an email using the template.

## Files

- `main.py` — orchestrates standings → schedule → pitchers → narratives → email
- `app/standings.py` — fetches standings and labels contenders (±CONTENDER_GB games)
- `app/schedule.py` — fixes MYT→US slate (MYT date - 1), fetches schedule, adds relationship badges
- `app/pitchers.py` — batches ERA/WHIP via `people?hydrate=stats(group=[pitching],type=[season])`
- `app/narrative.py` — scrapes Reuters Field Level Media author page, keeps ≤8h articles, summarizes w/ OpenAI
- `app/emailer.py` — Jinja2 renderer + optional Gmail SMTP sender
- `templates/email.html` — HTML template with badges + source link

## What you still need

- **OPENAI_API_KEY** in `.env`
- Optional: Gmail **App Password** for `GMAIL_PASS` (or switch to SendGrid/Postmark in `emailer.py`)
- If MLB Stats API changes field names mid-season, tweak `standings.py` mappings (log payload if needed).

## Next (optional)
- Add `.github/workflows/send.yml` to schedule at 23:00 MYT daily
- Swap SMTP to a transactional provider for better deliverability
