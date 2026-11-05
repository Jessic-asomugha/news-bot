from langchain.tools import tool
from transformers import pipeline
import requests
from bs4 import BeautifulSoup
import streamlit as st
from config import CATEGORIES

# ─────────────────────────────────────────────
# LOAD THE BART MODEL (happens once at startup)
# The first run will download the model (~1.6 GB)
# Subsequent runs load it from cache — much faster
# ─────────────────────────────────────────────
@st.cache_resource
def load_model():
    print("[MODEL] Loading BART summarisation model...")
    model = pipeline("summarization", model="facebook/bart-large-cnn")
    print("[MODEL] BART loaded and ready.")
    return model

summariser = load_model()

# ─────────────────────────────────────────────
# TOOL 1: FETCH TOOL
# Takes a URL, returns the full article text
# Used when RSS only gives a headline/snippet
# ─────────────────────────────────────────────
@tool
def fetch_article(url: str) -> str:
    """
    Fetches the full text of a news article from a given URL.
    Use this when you need the full content of an article
    and only have a link available.
    Input: a valid article URL string.
    Output: the cleaned article text as a string.
    """
    try:
        headers = {
            # Pretend to be a browser so sites don't block the request
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raises an error for 4xx/5xx responses

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove elements that aren't article content
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "advertisement", "figure"]):
            tag.decompose()

        # Try to find the main article body first
        # Most news sites use <article> or a div with class "content"
        article_body = (
            soup.find("article") or
            soup.find("div", class_=lambda c: c and "article" in c.lower()) or
            soup.find("div", class_=lambda c: c and "content" in c.lower()) or
            soup.find("main")
        )

        if article_body:
            text = article_body.get_text(separator=" ", strip=True)
        else:
            # Fall back to full page text if no article element found
            text = soup.get_text(separator=" ", strip=True)

        # Clean up excessive whitespace
        text = " ".join(text.split())

        # Return a maximum of 3000 characters — enough for BART to work with
        return text[:3000] if len(text) > 3000 else text

    except requests.exceptions.Timeout:
        return f"[ERROR] Request timed out for URL: {url}"
    except requests.exceptions.HTTPError as e:
        return f"[ERROR] HTTP error fetching article: {e}"
    except Exception as e:
        return f"[ERROR] Could not fetch article from {url}: {e}"


# ─────────────────────────────────────────────
# TOOL 2: SUMMARISE TOOL
# Takes article text, returns a short summary
# This is where BART does its work
# ─────────────────────────────────────────────
@tool
def summarise_article(text: str) -> str:
    """
    Summarises a news article into 2 to 4 clear sentences.
    Use this after fetching or receiving article text.
    Input: the full or partial text of a news article.
    Output: a concise summary string.
    """
    # Guard: don't summarise very short text — it's already brief enough
    if len(text.strip()) < 150:
        return text.strip()

    # Guard: flag empty or error inputs
    if not text or text.startswith("[ERROR]"):
        return "Could not summarise — article content was unavailable."

    try:
        # BART has a max input of ~1024 tokens (~800 words)
        # We truncate to 1000 characters to stay safely within that limit
        truncated = text[:1000]

        result = summariser(
            truncated,
            max_length=120,   # Maximum summary length in tokens
            min_length=40,    # Minimum summary length — avoids one-liners
            do_sample=False,  # Deterministic output — same input = same summary
        )

        summary = result[0]["summary_text"]
        return summary

    except Exception as e:
        return f"[ERROR] Summarisation failed: {e}"


# ─────────────────────────────────────────────
# TOOL 3: FILTER TOOL
# Takes a list of articles + a topic keyword
# Returns only the relevant ones
# ─────────────────────────────────────────────
@tool
def filter_articles(articles_and_topic: dict) -> list:
    """
    Filters a list of articles to only those relevant to a given topic.
    Use this to remove off-topic articles before summarising.
    Input: a dictionary with two keys:
        - 'articles': a list of article dictionaries
        - 'topic': a keyword string to filter by (e.g. 'climate change')
    Output: a filtered list of article dictionaries.
    """
    try:
        articles = articles_and_topic.get("articles", [])
        topic = articles_and_topic.get("topic", "").lower().strip()

        if not topic:
            # No filter applied — return everything
            return articles

        # Split topic into individual keywords so multi-word topics work better
        # e.g. 'artificial intelligence' becomes ['artificial', 'intelligence']
        keywords = topic.split()

        filtered = []
        for article in articles:
            # Check title and description for any of the keywords
            title = article.get("title", "").lower()
            description = article.get("description", "").lower()
            combined_text = title + " " + description

            # Include the article if all keyword matches
            if all(keyword in combined_text for keyword in keywords):
                filtered.append(article)

        print(f"[FILTER] {len(filtered)} of {len(articles)} articles matched topic: '{topic}'")
        return filtered

    except Exception as e:
        print(f"[ERROR] Filter tool failed: {e}")
        return articles  # Return unfiltered list as a safe fallback


# ─────────────────────────────────────────────
# QUICK TEST — run this file directly
# Tests all three tools independently
# Run: python agent/tools.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Testing tools.py ---\n")

    # Test 1: Fetch Tool
    print("=== TEST 1: Fetch Tool ===")
    test_url = "https://techcrunch.com"
    fetched_text = fetch_article.run(test_url)
    print(f"Fetched {len(fetched_text)} characters")
    print(f"Preview: {fetched_text[:200]}...")

    print()

    # Test 2: Summarise Tool
    print("=== TEST 2: Summarise Tool ===")
    sample_text = (
        "Artificial intelligence is transforming industries across the globe. "
        "From healthcare to finance, companies are deploying machine learning models "
        "to automate tasks, improve accuracy, and reduce costs. Researchers at leading "
        "universities are developing new architectures that could make AI systems more "
        "efficient and accessible. However, concerns about bias, transparency, and job "
        "displacement remain at the forefront of public debate. Regulators in Europe "
        "and the United States are working on frameworks to govern the use of AI in "
        "high-stakes environments such as criminal justice and medical diagnosis."
    )
    summary = summarise_article.run(sample_text)
    print(f"Summary: {summary}")

    print()

    # Test 3: Filter Tool
    print("=== TEST 3: Filter Tool ===")
    sample_articles = [
        {"title": "OpenAI releases new AI model", "description": "A powerful new language model.", "link": "https://example.com/1", "source": "TechCrunch", "published": "16 Mar 2026"},
        {"title": "Stock markets fall sharply", "description": "Global markets react to interest rate changes.", "link": "https://example.com/2", "source": "Reuters", "published": "16 Mar 2026"},
        {"title": "Machine learning breakthrough", "description": "Researchers achieve new benchmark in image recognition.", "link": "https://example.com/3", "source": "BBC", "published": "16 Mar 2026"},
    ]
    result = filter_articles.run({"articles_and_topic": {"articles": sample_articles, "topic": "AI"}})
    print(f"Filtered to {len(result)} articles:")
    for a in result:
        print(f"  - {a['title']}")


##validation category


def validate_subcategory(category: str, subcategory: str) -> dict:
    """
    Checks whether a custom subcategory name makes sense
    under a given parent category using keyword overlap scoring.

    Returns a dict with:
        - valid (bool)
        - reason (str) — shown to user if blocked
        - score (float) — overlap confidence 0.0 to 1.0
    """
    subcategory = subcategory.strip()

    # ── Basic input checks ──
    if not subcategory:
        return {"valid": False, "reason": "Subcategory name cannot be empty.", "score": 0.0}

    if len(subcategory) < 3:
        return {"valid": False, "reason": "Subcategory name is too short. Please be more descriptive.", "score": 0.0}

    if len(subcategory) > 40:
        return {"valid": False, "reason": "Subcategory name is too long. Keep it under 40 characters.", "score": 0.0}

    if category not in CATEGORIES:
        return {"valid": False, "reason": f"Category '{category}' does not exist.", "score": 0.0}

    # ── Duplicate check ──
    existing = CATEGORIES[category]["subcategories"]
    if subcategory.lower() in [s.lower() for s in existing.keys()]:
        return {"valid": False, "reason": f"'{subcategory}' already exists under {category}.", "score": 0.0}

    # ── Keyword overlap scoring ──
    # Split the subcategory into individual words and check how many
    # appear in or are related to the category's defining keywords
    category_keywords = CATEGORIES[category]["keywords"]
    subcategory_words = subcategory.lower().replace("-", " ").replace("&", " ").split()

    # Direct word overlap — subcategory words that appear in category keywords
    direct_matches = sum(
        1 for word in subcategory_words
        if any(word in kw or kw in word for kw in category_keywords)
    )

    # Partial stem overlap — catch cases like "tech" matching "technology"
    stem_matches = sum(
        1 for word in subcategory_words
        if any(
            word[:4] == kw[:4]  # first 4 characters match (basic stemming)
            for kw in category_keywords
            if len(word) >= 4 and len(kw) >= 4
        )
    )

    total_words = max(len(subcategory_words), 1)
    score = min((direct_matches + stem_matches * 0.5) / total_words, 1.0)

    # ── Threshold decision ──
    # Score >= 0.3 means at least some words meaningfully relate
    # to the category. Below that we block it.
    THRESHOLD = 0.3

    if score >= THRESHOLD:
        return {
            "valid": True,
            "reason": f"'{subcategory}' is a good fit for {category}.",
            "score": round(score, 2),
        }
    else:
        # Build a helpful rejection message
        examples = list(existing.keys())[:3]
        example_str = ", ".join(f'"{e}"' for e in examples)
        return {
            "valid": False,
            "reason": (
                f"'{subcategory}' doesn't appear to be related to {category}. "
                f"Try something more specific to this category — "
                f"for example: {example_str}."
            ),
            "score": round(score, 2),
        }