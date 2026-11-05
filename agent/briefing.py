# ─────────────────────────────────────────────
# agent/briefing.py
# Comprehensive news briefing generator
# Powered by Google Gemini API
# ─────────────────────────────────────────────

import os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Use Gemini 2.0 Flash — fast, free, strong at structured writing
# Falls back to 1.5 Flash if 2.0 is unavailable
try:
    model = genai.GenerativeModel("gemini-2.0-flash")
except Exception:
    model = genai.GenerativeModel("gemini-1.5-flash")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _format_articles_for_prompt(articles: list) -> str:
    """
    Formats a list of article dicts into a clean numbered
    list for the Gemini prompt. Includes title, source,
    and description only — keeps token count manageable.
    """
    lines = []
    for i, article in enumerate(articles, 1):
        title  = article.get("title", "No title")
        source = article.get("source", "Unknown")
        desc   = article.get("description", "")[:200]
        lines.append(f"{i}. [{source}] {title}\n   {desc}")
    return "\n\n".join(lines)


def _build_prompt(articles: list, today: str) -> str:
    """
    Builds the structured prompt sent to Gemini.
    Instructs it to produce four distinct sections
    based on the supplied headlines.
    """
    formatted = _format_articles_for_prompt(articles)

    return f"""You are PULSE, an AI news intelligence analyst. Today is {today}.

Below are recent news headlines and summaries gathered from multiple sources:

{formatted}

Based on these stories, produce a structured intelligence briefing with exactly these four sections. Be analytical, specific, and concise. Write in a confident editorial tone — not overly casual, not stiff. Each section should be 3 to 5 sentences.

---

## What Happened
Summarise the most significant events and developments from the headlines above. Focus on the stories with the broadest impact. Mention specific names, places, and numbers where relevant.

## What to Watch
Identify 2 to 3 stories that are still developing and will likely have major updates in the next 24 to 48 hours. Explain why each one is worth monitoring and what outcome to look for.

## Predictions
Based on the patterns visible in today's news, make 2 to 3 informed predictions about what is likely to happen in the coming days. Be specific — name the actors, events, or decisions you expect. Acknowledge uncertainty where appropriate.

## Global Mood
Assess the overall tone and sentiment of today's news landscape. Which regions or sectors are experiencing tension, optimism, uncertainty, or momentum? Give a brief read of the global atmosphere based on the headlines.

---

Return only the four sections above with their headers. Do not add introductions, sign-offs, or any other text outside the four sections."""


# ─────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────
def generate_briefing(articles: list) -> dict:
    """
    Generates a comprehensive news briefing from a list of articles.

    Returns a dict with:
        - success (bool)
        - sections (dict) — four keyed sections if successful
        - raw (str) — full raw response
        - generated_at (str) — timestamp
        - error (str) — message if failed
    """
    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY not found in .env file.",
            "sections": {},
            "raw": "",
            "generated_at": "",
        }

    if not articles:
        return {
            "success": False,
            "error": "No articles provided to generate briefing from.",
            "sections": {},
            "raw": "",
            "generated_at": "",
        }

    today = datetime.now().strftime("%A, %d %B %Y")

    try:
        prompt   = _build_prompt(articles[:30], today)  # Cap at 30 articles
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Parse the four sections from the response
        sections = _parse_sections(raw_text)

        return {
            "success": True,
            "sections": sections,
            "raw": raw_text,
            "generated_at": datetime.now().strftime("%d %b %Y at %H:%M"),
            "error": "",
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Gemini API error: {str(e)}",
            "sections": {},
            "raw": "",
            "generated_at": "",
        }


def _parse_sections(raw: str) -> dict:
    """
    Parses Gemini's response into four named sections.
    Looks for the section headers and splits accordingly.
    Falls back gracefully if parsing fails.
    """
    section_keys = {
        "What Happened":  "what_happened",
        "What to Watch":  "what_to_watch",
        "Predictions":    "predictions",
        "Global Mood":    "global_mood",
    }

    sections = {v: "" for v in section_keys.values()}

    # Split on markdown headers
    current_key  = None
    current_text = []

    for line in raw.split("\n"):
        stripped = line.strip()

        # Check if this line is a section header
        matched_header = False
        for header, key in section_keys.items():
            if header.lower() in stripped.lower() and (
                stripped.startswith("#") or stripped.startswith("**")
            ):
                # Save previous section
                if current_key:
                    sections[current_key] = "\n".join(current_text).strip()
                current_key  = key
                current_text = []
                matched_header = True
                break

        if not matched_header and current_key:
            # Skip horizontal rules
            if stripped not in ("---", "***", "___"):
                current_text.append(line)

    # Save the last section
    if current_key and current_text:
        sections[current_key] = "\n".join(current_text).strip()

    # If parsing produced empty sections, put everything in what_happened
    if all(v == "" for v in sections.values()):
        sections["what_happened"] = raw

    return sections


# ─────────────────────────────────────────────
# FETCH BROAD ARTICLES FOR THE BRIEFING
# Pulls from multiple topics to give Gemini
# a wide view of current events
# ─────────────────────────────────────────────
def fetch_briefing_articles() -> list:
    """
    Fetches articles across a broad set of topics
    to give the briefing comprehensive global coverage.
    Returns a deduplicated combined list.
    """
    from sources.feeds import get_all_articles

    briefing_topics = [
        "world news",
        "politics",
        "economy",
        "technology",
        "conflict",
    ]

    all_articles = []
    seen_links   = set()

    for topic in briefing_topics:
        try:
            articles = get_all_articles(topic=topic)
            for article in articles:
                link = article.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_articles.append(article)
        except Exception as e:
            print(f"[BRIEFING] Failed to fetch topic '{topic}': {e}")
            continue

    print(f"[BRIEFING] {len(all_articles)} unique articles gathered for briefing.")
    return all_articles


# ─────────────────────────────────────────────
# QUICK TEST
# Run: python agent/briefing.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n--- Testing briefing.py ---\n")
    print("[TEST] Fetching articles...")
    articles = fetch_briefing_articles()
    print(f"[TEST] {len(articles)} articles fetched. Generating briefing...\n")

    result = generate_briefing(articles)

    if result["success"]:
        print(f"Generated at: {result['generated_at']}\n")
        for key, text in result["sections"].items():
            print(f"=== {key.upper().replace('_', ' ')} ===")
            print(text)
            print()
    else:
        print(f"[ERROR] {result['error']}")