# ─────────────────────────────────────────────
# agent/nlp_utils.py
# Keyword extraction and article match scoring
# No extra models needed — pure Python NLP
# ─────────────────────────────────────────────

import re
import math
from collections import Counter

# ─────────────────────────────────────────────
# STOP WORDS
# Common words that carry no search value
# We strip these before extracting keywords
# ─────────────────────────────────────────────
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "it", "they", "them", "this", "that",
    "these", "those", "what", "which", "who", "when", "where", "how",
    "about", "after", "before", "between", "into", "through", "during",
    "about", "news", "report", "latest", "update", "new", "just", "says",
    "said", "tell", "told", "according", "also", "more", "than", "any",
    "all", "some", "there", "their", "then", "than", "so", "if", "as",
}


def extract_keywords(description: str) -> list:
    """
    Extracts meaningful keywords from a natural language description.
    Returns a list of (keyword, weight) tuples sorted by importance.

    Weighting rules:
    - Longer words get higher weight (more specific = more valuable)
    - Words that appear multiple times get boosted
    - Stop words are removed entirely
    - Named entities (capitalised words) get a bonus weight

    Example:
        "Trump Iran nuclear deal conclusion"
        → [("conclusion", 1.8), ("nuclear", 1.6), ("trump", 1.5), ("iran", 1.5), ("deal", 1.2)]
    """
    if not description or not description.strip():
        return []

    # Preserve original for named entity detection before lowercasing
    original_words = description.strip().split()

    # Identify capitalised words (likely named entities — people, places, orgs)
    named_entities = {
        w.lower() for w in original_words
        if w[0].isupper() and len(w) > 1 and w.lower() not in STOP_WORDS
    }

    # Clean and tokenise
    cleaned = re.sub(r"[^a-zA-Z0-9\s\-]", "", description.lower())
    words = cleaned.split()

    # Remove stop words and very short words
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    if not meaningful:
        return []

    # Count frequency
    freq = Counter(meaningful)

    # Score each unique word
    scored = []
    for word, count in freq.items():
        # Base weight from word length — longer = more specific
        length_weight = min(len(word) / 5.0, 2.0)

        # Frequency boost
        freq_boost = 1.0 + (count - 1) * 0.3

        # Named entity bonus
        entity_bonus = 0.5 if word in named_entities else 0.0

        score = round((length_weight * freq_boost) + entity_bonus, 2)
        scored.append((word, score))

    # Sort by score descending, return top 10
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:10]


def score_article_match(description: str, article: dict) -> float:
    """
    Scores how closely an article matches a waitlist description.
    Returns a float between 0.0 (no match) and 1.0 (perfect match).

    Scoring strategy:
    - Extract keywords from the description with weights
    - Check each keyword against article title + description
    - Title matches score higher than description matches
    - Final score is normalised to 0.0–1.0

    Match threshold: 0.35 — above this we consider it a match.
    """
    if not description or not article:
        return 0.0

    keywords = extract_keywords(description)
    if not keywords:
        return 0.0

    # Build searchable text from article — title weighted 2x
    title       = article.get("title", "").lower()
    description_text = article.get("description", "").lower()
    summary     = article.get("summary", "").lower()

    title_text  = f"{title} {title}"  # doubled for weighting
    full_text   = f"{title_text} {description_text} {summary}"

    # Clean the article text
    full_text = re.sub(r"[^a-zA-Z0-9\s]", " ", full_text)

    total_possible = sum(weight for _, weight in keywords)
    total_matched  = 0.0

    for keyword, weight in keywords:
        if keyword in full_text:
            # Full word match
            total_matched += weight
        elif len(keyword) > 5 and keyword[:5] in full_text:
            # Partial stem match (e.g. "nuclear" matches "nucle")
            total_matched += weight * 0.4

    if total_possible == 0:
        return 0.0

    raw_score = total_matched / total_possible

    # Apply a sigmoid-like curve so mid-range scores feel more decisive
    # Scores near 0 stay low, scores near 1 get pulled higher
    curved = raw_score ** 0.7

    return round(min(curved, 1.0), 3)


def find_best_matches(description: str, articles: list, threshold: float = 0.35) -> list:
    """
    Scores all articles against a description and returns
    those that exceed the match threshold, sorted by score.

    Returns a list of (article, score) tuples.
    """
    scored = []
    for article in articles:
        score = score_article_match(description, article)
        if score >= threshold:
            scored.append((article, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ─────────────────────────────────────────────
# QUICK TEST
# Run: python agent/nlp_utils.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Testing nlp_utils.py ---\n")

    desc = "Trump Iran nuclear deal conclusion"
    keywords = extract_keywords(desc)
    print(f"Description: '{desc}'")
    print(f"Keywords extracted: {keywords}")

    print()

    test_articles = [
        {
            "title": "Trump and Iran reach historic nuclear agreement",
            "description": "US and Iranian officials conclude negotiations on nuclear deal.",
            "summary": ""
        },
        {
            "title": "Stock markets rise on positive economic data",
            "description": "Wall Street sees gains as inflation cools.",
            "summary": ""
        },
        {
            "title": "Iran nuclear talks stall amid diplomatic tensions",
            "description": "Negotiations between world powers and Iran face setbacks.",
            "summary": ""
        },
    ]

    print("Match scores:")
    for article in test_articles:
        score = score_article_match(desc, article)
        print(f"  [{score:.3f}] {article['title']}")