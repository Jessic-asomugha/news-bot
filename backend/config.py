"""
PULSE settings. Everything you might want to tweak lives here:
models, cache times, categories and the feed list.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Groq models. The small one handles cheap, frequent jobs (sorting stories,
# summaries); the big one only writes the World Temperature briefing.
# Groq retires models often. If one errors, check console.groq.com/docs/models
SMALL_MODEL = "openai/gpt-oss-20b"
BIG_MODEL = "openai/gpt-oss-120b"

DEFAULT_COUNTRY = "Nigeria"

# Cache timings (seconds)
FEED_TTL = 20 * 60         # re-check feeds at most every 20 min, and only when the app is used
BRIEFING_TTL = 45 * 60     # a briefing is reused for 45 min
SEARCH_TTL = 30 * 60       # Tavily results reused for 30 min (saves credits)
KEEP_HOURS = 48            # stories older than this are dropped

ITEMS_PER_FEED = 12        # newest N stories per feed: keeps Groq usage low

DATA_DIR = ROOT / "data"   # disk cache so restarts don't re-spend Groq tokens
DATA_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# CATEGORIES
# Topic categories each have subcategories. The classifier must pick from
# these exact names. "World" means world affairs (politics, conflict, etc).
# ─────────────────────────────────────────────
TOPICS = {
    "World": ["Politics & Diplomacy", "Conflict & Security", "Elections", "Rights & Migration", "Crime & Justice",
              "Accidents & Disasters", "Society"],
    "Business": ["Economy", "Markets", "Companies", "Energy & Commodities", "Startups & Funding"],
    "Tech & Science": ["AI", "Robotics", "Gadgets & Internet", "Cybersecurity", "Space", "Science & Research"],
    "Nature & Environment": ["Climate", "Wildlife", "Marine Life", "Conservation", "Weather & Natural Disasters"],
    "Health": ["Public Health", "Medicine & Research", "Mental Health", "Outbreaks"],
    "Culture": ["Film & TV", "Music", "Books & Art", "Food", "Fashion & Lifestyle", "Faith & Traditions"],
    "Sport": ["Football", "Athletics", "Basketball", "Tennis", "Other Sport"],
}

# Top nav order. The home country tab is labelled with the user's country.
NAV = ["World", "HOME", "Africa", "Business", "Tech & Science", "Nature & Environment", "Health", "Culture", "Sport"]

# Region tabs (home country, Africa) filter by place, then offer topic chips.
REGION_CHIPS = {
    "Politics": lambda a: a["category"] == "World" and a["subcategory"] != "Conflict & Security",
    "Security": lambda a: a["subcategory"] == "Conflict & Security" or a["subcategory"] == "Crime & Justice",
    "Business": lambda a: a["category"] in ("Business",),
    "Society": lambda a: a["category"] in ("Health", "Culture", "Nature & Environment", "Tech & Science"),
    "Sport": lambda a: a["category"] == "Sport",
}

REGIONS = ["africa", "europe", "asia", "middle_east", "americas", "oceania", "global"]

# ─────────────────────────────────────────────
# FEEDS
# (url, outlet name, region hint, category hint or None for mixed feeds)
# Hints are only used until the AI classifier has looked at a story.
# "primary" outlets are the fast first-search tier from the brief.
# ─────────────────────────────────────────────
FEEDS = [
    # World: deliberately spread across regions, not US-led
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC", "global", "World"),
    ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", "global", None),
    ("http://rss.cnn.com/rss/edition_world.rss", "CNN", "global", "World"),
    ("https://rss.dw.com/rdf/rss-en-world", "DW", "europe", "World"),
    ("https://www.france24.com/en/rss", "France 24", "global", "World"),
    ("https://www.theguardian.com/world/rss", "The Guardian", "global", "World"),
    ("https://feeds.bbci.co.uk/news/world/asia/rss.xml", "BBC", "asia", "World"),
    ("https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", "BBC", "americas", "World"),
    ("https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "BBC", "middle_east", "World"),
    ("https://feeds.bbci.co.uk/news/world/europe/rss.xml", "BBC", "europe", "World"),
    # Africa
    ("https://feeds.bbci.co.uk/news/world/africa/rss.xml", "BBC", "africa", "World"),
    ("https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "AllAfrica", "africa", None),
    ("https://www.theguardian.com/world/africa/rss", "The Guardian", "africa", "World"),
    # Nigeria
    ("https://www.premiumtimesng.com/feed", "Premium Times", "nigeria", None),
    ("https://punchng.com/feed/", "Punch", "nigeria", None),
    ("https://www.channelstv.com/feed/", "Channels TV", "nigeria", None),
    ("https://businessday.ng/feed/", "BusinessDay", "nigeria", "Business"),
    ("https://www.vanguardngr.com/feed/", "Vanguard", "nigeria", None),
    # Business
    ("https://feeds.bbci.co.uk/news/business/rss.xml", "BBC", "global", "Business"),
    ("https://www.theguardian.com/business/rss", "The Guardian", "global", "Business"),
    ("https://www.cnbc.com/id/100727362/device/rss/rss.html", "CNBC", "global", "Business"),
    # Tech & Science
    ("https://feeds.bbci.co.uk/news/technology/rss.xml", "BBC", "global", "Tech & Science"),
    ("https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "BBC", "global", "Tech & Science"),
    ("https://www.theguardian.com/science/rss", "The Guardian", "global", "Tech & Science"),
    ("https://techcrunch.com/feed/", "TechCrunch", "americas", "Tech & Science"),
    ("https://feeds.arstechnica.com/arstechnica/index", "Ars Technica", "americas", "Tech & Science"),
    ("https://restofworld.org/feed/latest", "Rest of World", "global", "Tech & Science"),
    ("https://techcabal.com/feed/", "TechCabal", "africa", "Tech & Science"),
    # Nature & Environment
    ("https://news.mongabay.com/feed/", "Mongabay", "global", "Nature & Environment"),
    ("https://www.theguardian.com/environment/rss", "The Guardian", "global", "Nature & Environment"),
    ("https://hakaimagazine.com/feed/", "Hakai Magazine", "global", "Nature & Environment"),
    ("https://www.sciencedaily.com/rss/plants_animals.xml", "ScienceDaily", "global", "Nature & Environment"),
    # Health
    ("https://feeds.bbci.co.uk/news/health/rss.xml", "BBC", "global", "Health"),
    ("https://www.who.int/rss-feeds/news-english.xml", "WHO", "global", "Health"),
    ("https://www.statnews.com/feed/", "STAT", "americas", "Health"),
    # Culture
    ("https://www.theguardian.com/culture/rss", "The Guardian", "global", "Culture"),
    ("https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "BBC", "global", "Culture"),
    # Sport
    ("https://feeds.bbci.co.uk/sport/rss.xml", "BBC Sport", "global", "Sport"),
    ("https://www.theguardian.com/sport/rss", "The Guardian", "global", "Sport"),
    ("https://www.completesports.com/feed/", "Complete Sports", "nigeria", "Sport"),
]

# Fast first-search tier for Tavily (brief: BBC, CNN, Al Jazeera), plus the
# Nigerian outlets so home-country searches aren't starved.
PRIMARY_DOMAINS = [
    "bbc.com", "bbc.co.uk", "cnn.com", "aljazeera.com",
    "premiumtimesng.com", "punchng.com", "channelstv.com",
]
