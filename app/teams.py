# app/teams.py
# Canonical MLB team names + common aliases for text matching

TEAMS = [
    {"full": "Baltimore Orioles",        "aliases": ["orioles", "bal"]},
    {"full": "Boston Red Sox",           "aliases": ["red sox", "bos"]},
    {"full": "New York Yankees",         "aliases": ["yankees", "nyy"]},
    {"full": "Tampa Bay Rays",           "aliases": ["rays", "tbr", "tb rays"]},
    {"full": "Toronto Blue Jays",        "aliases": ["blue jays", "jays", "tor"]},

    {"full": "Chicago White Sox",        "aliases": ["white sox", "cws"]},
    {"full": "Cleveland Guardians",      "aliases": ["guardians", "cle"]},
    {"full": "Detroit Tigers",           "aliases": ["tigers", "det"]},
    {"full": "Kansas City Royals",       "aliases": ["royals", "kc", "kcr"]},
    {"full": "Minnesota Twins",          "aliases": ["twins", "min"]},

    {"full": "Houston Astros",           "aliases": ["astros", "hou"]},
    {"full": "Los Angeles Angels",       "aliases": ["angels", "laa"]},
    {"full": "Oakland Athletics",        "aliases": ["athletics", "a's", "as", "oak"]},
    {"full": "Seattle Mariners",         "aliases": ["mariners", "sea"]},
    {"full": "Texas Rangers",            "aliases": ["rangers", "tex"]},

    {"full": "Atlanta Braves",           "aliases": ["braves", "atl"]},
    {"full": "Miami Marlins",            "aliases": ["marlins", "mia"]},
    {"full": "New York Mets",            "aliases": ["mets", "nym"]},
    {"full": "Philadelphia Phillies",    "aliases": ["phillies", "phi"]},
    {"full": "Washington Nationals",     "aliases": ["nationals", "nats", "wsh", "was"]},

    {"full": "Chicago Cubs",             "aliases": ["cubs", "chc"]},
    {"full": "Cincinnati Reds",          "aliases": ["reds", "cin"]},
    {"full": "Milwaukee Brewers",        "aliases": ["brewers", "mil"]},
    {"full": "Pittsburgh Pirates",       "aliases": ["pirates", "pit"]},
    {"full": "St. Louis Cardinals",      "aliases": ["cardinals", "cards", "st. louis"]},

    {"full": "Arizona Diamondbacks",     "aliases": ["diamondbacks", "d-backs", "dbacks", "ari"]},
    {"full": "Colorado Rockies",         "aliases": ["rockies", "col"]},
    {"full": "Los Angeles Dodgers",      "aliases": ["dodgers", "lad"]},
    {"full": "San Diego Padres",         "aliases": ["padres", "sd", "sdp"]},
    {"full": "San Francisco Giants",     "aliases": ["giants", "sf", "sfg"]},
]

# Helper dicts
ALIAS_TO_FULL = {}
FULL_TO_ALIASES = {}
for t in TEAMS:
    FULL_TO_ALIASES[t["full"]] = set([t["full"].lower(), *t["aliases"]])
    for a in t["aliases"]:
        ALIAS_TO_FULL[a.lower()] = t["full"]
# Also allow exact full names as aliases
for t in TEAMS:
    ALIAS_TO_FULL[t["full"].lower()] = t["full"]
