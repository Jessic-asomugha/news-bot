import sys
import os

# Make sure Python can find your other project files
# regardless of where you run this from
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.tools import fetch_article, summarise_article, filter_articles
from sources.feeds import get_all_articles
from config import (
    DEFAULT_TOPIC,
    MAX_ARTICLES,
    RSS_FEEDS,
    ARTICLE_MAX_CHARS,
)

# ─────────────────────────────────────────────
# WHY NO LLM HERE?
# BART is a summarisation model — it compresses
# text but cannot reason about which tool to use.
# Modern LangChain agents need an instruction-
# following LLM (like Mistral or GPT) for that.
#
# Instead we orchestrate the tools directly in
# Python — this is more reliable, faster, and
# perfectly suited to a news bot where the
# workflow is always the same:
#   fetch → filter → summarise → return
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# MAIN FUNCTION
# This is what app.py and the Streamlit UI call
# Returns a list of summarised article dicts
# ─────────────────────────────────────────────
def run_news_agent(topic: str = DEFAULT_TOPIC, max_articles: int = MAX_ARTICLES) -> list:
    """
    Orchestrates the three tools in sequence:
    fetch sources → filter by topic → summarise each article.
    Returns a list of article dicts ready for display in Streamlit.
    """
    print(f"\n[AGENT] Running news agent for topic: '{topic}'")

    # ── STEP 1: Fetch from all sources ──
    print("[AGENT] Step 1/3 — Fetching articles from all sources...")
    all_articles = get_all_articles(topic=topic, rss_urls=RSS_FEEDS)

    if not all_articles:
        print("[AGENT] No articles retrieved. Check your internet connection.")
        return []

    # ── STEP 2: Filter to relevant articles ──
    print("[AGENT] Step 2/3 — Filtering articles by topic...")
    filtered = filter_articles.invoke({"articles_and_topic": {"articles": all_articles, "topic": topic}})

    if not filtered:
        print(f"[AGENT] No articles matched topic: '{topic}'. Try a broader keyword.")
        return []

    # Limit to max_articles to keep runtime manageable
    top_articles = filtered[:max_articles]
    print(f"[AGENT] {len(top_articles)} articles selected for summarisation.")

    # ── STEP 3: Summarise each article ──
    print("[AGENT] Step 3/3 — Summarising articles...")
    results = []

    for i, article in enumerate(top_articles):
        print(f"[AGENT] Summarising {i + 1}/{len(top_articles)}: {article['title'][:60]}...")

        # Use the RSS/NewsAPI description as the source text
        # If it is too short, fetch the full article from its URL
        text = article.get("description", "")

        if len(text.strip()) < 150 and article.get("link"):
            print(f"[AGENT] Description too short — fetching full article text...")
            text = fetch_article.invoke(article["link"])

        # Truncate to BART's safe input length before summarising
        text = text[:ARTICLE_MAX_CHARS]

        # Summarise and attach to the article dict
        summary = summarise_article.invoke(text)
        article["summary"] = summary
        results.append(article)

    print(f"\n[AGENT] Done. {len(results)} articles ready.")
    return results


# ─────────────────────────────────────────────
# QUICK TEST — run this file directly
# Run: python agent/news_agent.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Testing news_agent.py ---\n")

    test_topic = "machine learning"
    articles = run_news_agent(topic=test_topic, max_articles=3)

    print(f"\n=== RESULTS: {len(articles)} articles on '{test_topic}' ===\n")
    for i, article in enumerate(articles, 1):
        print(f"[{i}] {article['title']}")
        print(f"     Source:    {article['source']}")
        print(f"     Published: {article['published']}")
        print(f"     Summary:   {article['summary']}")
        print(f"     Link:      {article['link']}")
        print()