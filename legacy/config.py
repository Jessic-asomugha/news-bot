# ─────────────────────────────────────────────
# config.py
# Central settings for the AI News Bot
# Edit this file to change topics, sources,
# and model behaviour — no need to touch
# any other file for basic customisation
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# config.py
# Central settings for the AI News Bot
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# config.py
# Central settings for the AI News Bot
# ─────────────────────────────────────────────

DEFAULT_TOPIC = "artificial intelligence"
MAX_ARTICLES  = 5

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.nbcnews.com/nbcnews/public/tech",
]

SUMMARY_MAX_LENGTH = 120
SUMMARY_MIN_LENGTH = 40
ARTICLE_MAX_CHARS  = 1000

# ─────────────────────────────────────────────
# CATEGORIES & SUBCATEGORIES
#
# IMPORTANT: Keep search queries SHORT (1-2 words)
# The filter tool requires ALL words to appear in
# the article — long queries almost always fail
# ─────────────────────────────────────────────
CATEGORIES = {
    "Technology": {
        "keywords": [
            "technology", "software", "hardware", "internet", "digital",
            "computing", "programming", "engineering", "devices", "tech",
            "gadgets", "networks", "code", "systems", "platforms", "data",
            "cloud", "servers", "chips", "semiconductors", "robotics",
        ],
        "subcategories": {
            "Artificial Intelligence": "AI",
            "Cybersecurity":           "cybersecurity",
            "Startups & Funding":      "startup",
            "Consumer Gadgets":        "gadgets",
            "Cloud & Infrastructure":  "cloud",
        },
    },

    "Business & Finance": {
        "keywords": [
            "business", "finance", "economy", "market", "investment",
            "stock", "trade", "revenue", "profit", "corporate", "banking",
            "startup", "entrepreneur", "fiscal", "monetary", "inflation",
            "interest rate", "gdp", "commerce", "industry", "economic",
        ],
        "subcategories": {
            "Markets & Stocks":   "stocks",
            "Global Economy":     "economy",
            "Entrepreneurship":   "entrepreneur",
            "Banking & Crypto":   "cryptocurrency",
            "Corporate News":     "corporate",
        },
    },

    "Food & Culture": {
        "keywords": [
            "food", "cuisine", "recipe", "cooking", "restaurant", "chef",
            "culture", "art", "music", "film", "travel", "lifestyle",
            "dining", "ingredient", "dish", "meal", "beverage", "drink",
            "festival", "entertainment", "fashion", "design", "creative",
        ],
        "subcategories": {
            "Recipes & Cooking":     "recipes",
            "Restaurant & Dining":   "restaurant",
            "World Cuisine":         "cuisine",
            "Food & Nutrition":      "nutrition",
            "Arts & Entertainment":  "entertainment",
        },
    },
}