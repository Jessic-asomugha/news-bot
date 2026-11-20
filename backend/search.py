"""
Tavily search for the "explore" flow.
Step 1 (fast): only the primary outlets (BBC, CNN, Al Jazeera + Nigerian outlets).
Step 2 ("explore more"): the whole web, deeper search.
Results are cached for 30 min so repeat searches cost no credits.
"""
import time
from datetime import datetime

import httpx

from .config import PRIMARY_DOMAINS, SEARCH_TTL, TAVILY_API_KEY

_cache: dict[tuple, tuple[float, dict]] = {}


async def search(query: str, deep: bool = False) -> dict:
    query = query.strip()[:200]
    if not query:
        return {"results": [], "note": "Type something to search for."}
    if not TAVILY_API_KEY:
        return {"results": [], "note": "Search needs a TAVILY_API_KEY in your .env file."}

    key = (query.lower(), deep)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < SEARCH_TTL:
        return hit[1]

    body = {
        "query": query,
        "topic": "news",
        "days": 7 if not deep else 30,
        "max_results": 8 if not deep else 15,
        "search_depth": "basic" if not deep else "advanced",
    }
    if not deep:
        body["include_domains"] = PRIMARY_DOMAINS

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.tavily.com/search", json=body,
                             headers={"Authorization": f"Bearer {TAVILY_API_KEY}"})
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        return {"results": [], "note": f"Search failed ({e.response.status_code}). Check your Tavily key or credits."}
    except httpx.HTTPError:
        return {"results": [], "note": "Search is unreachable right now. Try again in a moment."}

    results = []
    for item in data.get("results", []):
        url = item.get("url", "")
        results.append({
            "title": item.get("title", ""),
            "desc": (item.get("content") or "")[:300],
            "link": url,
            "source": url.split("/")[2].removeprefix("www.") if url.count("/") >= 2 else "",
            "published": _ts(item.get("published_date")),
        })
    note = ""
    if len(results) < 3:
        note = ("Not much on this from the main outlets. Try Explore more to search the wider web."
                if not deep else
                "Very little news on this right now. Try a broader or related topic.")
    out = {"results": results, "note": note, "deep": deep}
    _cache[key] = (time.time(), out)
    return out


def _ts(value) -> float | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).timestamp()
        except ValueError:
            continue
    return None
