import feedparser
import requests
from datetime import datetime
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv

# Load your API key from the .env file
load_dotenv()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

# ─────────────────────────────────────────────
# HELPER: Standardise article format
# Both functions below return articles in this
# exact same structure so the rest of the bot
# doesn't need to care where the data came from
# ─────────────────────────────────────────────
def _make_article(title, description, link, source, published):
    """Return a clean, consistent article dictionary."""
    return {
        "title": title or "No title",
        "description": description or "No description available.",
        "link": link or "",
        "source": source or "Unknown source",
        "published": published or "Unknown date",
    }


# ─────────────────────────────────────────────
# FUNCTION 1: Fetch articles from RSS feeds
# ─────────────────────────────────────────────
def fetch_rss_articles(feed_urls: list) -> list:
    """
    Accepts a list of RSS feed URLs.
    Returns a list of article dictionaries.
    Skips any feed that fails without crashing.
    """
    articles = []

    for url in feed_urls:
        try:
            feed = feedparser.parse(url)

            # feedparser doesn't raise exceptions on failure,
            # so we check the bozo flag (True = something went wrong)
            if feed.bozo:
                print(f"[WARNING] Could not parse feed: {url}")
                continue

            for entry in feed.entries:
                # Extract the source name from the feed title if available
                source_name = feed.feed.get("title", url)

                # Published date — feedparser stores it as a struct_time
                # We convert it to a readable string
                published = ""
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6]).strftime("%d %b %Y %H:%M")
                elif hasattr(entry, "published"):
                    published = entry.published

                article = _make_article(
                    title=entry.get("title"),
                    description=entry.get("summary"),
                    link=entry.get("link"),
                    source=source_name,
                    published=published,
                )
                articles.append(article)

        except Exception as e:
            # Log the error but keep going — one bad feed shouldn't stop the rest
            print(f"[ERROR] Failed to fetch RSS feed {url}: {e}")
            continue

    print(f"[RSS] Fetched {len(articles)} articles from {len(feed_urls)} feeds.")
    return articles


# ─────────────────────────────────────────────
# FUNCTION 2: Fetch articles from NewsAPI
# ─────────────────────────────────────────────
def fetch_newsapi_articles(topic: str, max_results: int = 20) -> list:
    """
    Accepts a topic keyword (e.g. 'artificial intelligence').
    Returns a list of article dictionaries.
    Defaults to the last 24 hours of articles.
    """
    articles = []

    # Check that the API key exists before making any requests
    if not NEWSAPI_KEY:
        print("[ERROR] NEWSAPI_KEY not found. Check your .env file.")
        return articles

    try:
        newsapi = NewsApiClient(api_key=NEWSAPI_KEY)

        response = newsapi.get_everything(
            q=topic,               # Search keyword
            language="en",         # English articles only
            sort_by="publishedAt", # Most recent first
            page_size=max_results, # How many to fetch (max 100 on free tier)
        )

        if response.get("status") != "ok":
            print(f"[ERROR] NewsAPI returned a non-OK status: {response.get('status')}")
            return articles

        for item in response.get("articles", []):
            # Skip articles that have been removed or are placeholders
            if item.get("title") == "[Removed]":
                continue

            # Format the published date to match RSS output
            published = ""
            raw_date = item.get("publishedAt", "")
            if raw_date:
                try:
                    dt = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%SZ")
                    published = dt.strftime("%d %b %Y %H:%M")
                except ValueError:
                    published = raw_date

            article = _make_article(
                title=item.get("title"),
                description=item.get("description"),
                link=item.get("url"),
                source=item.get("source", {}).get("name", "NewsAPI"),
                published=published,
            )
            articles.append(article)

    except Exception as e:
        print(f"[ERROR] NewsAPI request failed: {e}")

    print(f"[NewsAPI] Fetched {len(articles)} articles for topic: '{topic}'.")
    return articles


# ─────────────────────────────────────────────
# FUNCTION 3: Combine both sources
# Call this from the agent — it gets everything
# ─────────────────────────────────────────────
def get_all_articles(topic: str, rss_urls: list = None) -> list:
    """
    Fetches from both RSS and NewsAPI and returns
    a single combined list of articles.
    Removes duplicate articles based on URL.
    """
    # Default RSS feeds if none are provided
    if rss_urls is None:
        rss_urls = [
            "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "https://techcrunch.com/feed/",
            "https://www.theverge.com/rss/index.xml",
            "https://feeds.reuters.com/reuters/technologyNews",
        ]

    rss_articles = fetch_rss_articles(rss_urls)
    newsapi_articles = fetch_newsapi_articles(topic)

    combined = rss_articles + newsapi_articles

    # Remove duplicates by link (same URL = same article)
    seen_links = set()
    unique_articles = []
    for article in combined:
        if article["link"] not in seen_links:
            seen_links.add(article["link"])
            unique_articles.append(article)

    print(f"[COMBINED] {len(unique_articles)} unique articles after deduplication.")
    return unique_articles


# ─────────────────────────────────────────────
# QUICK TEST — run this file directly to check
# everything is working before using the agent
# Run: python sources/feeds.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Testing feeds.py ---\n")

    test_topic = "artificial intelligence"
    articles = get_all_articles(topic=test_topic)

    print(f"\nTotal articles retrieved: {len(articles)}\n")
    print("--- First 3 articles ---\n")
    for article in articles[:3]:
        print(f"Title:     {article['title']}")
        print(f"Source:    {article['source']}")
        print(f"Published: {article['published']}")
        print(f"Link:      {article['link']}")
        print(f"Summary:   {article['description'][:120]}...")
        print("-" * 60)