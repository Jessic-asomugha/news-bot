"""
World Temperature: a quick read on the mood of the world.
Only generated when the reader taps for it, then cached for 45 minutes.

The old briefing was US/tech-led because its inputs were. Here the input is
built with fixed quotas per region (home country first, US and tech capped),
and the prompt orders the output: home -> home in the world -> wider world.
"""
import time
from datetime import datetime, timezone

from . import feed
from .config import BIG_MODEL, BRIEFING_TTL
from .llm import LLMUnavailable, chat

# How many stories from each slice the model gets to read.
QUOTAS = [
    ("home", 8), ("home_world", 4), ("africa", 5), ("europe", 4), ("asia", 4),
    ("middle_east", 4), ("americas", 3), ("us", 2), ("oceania", 1), ("global", 4),
]
TECH_CAP = 3

_cache: dict[str, tuple[float, dict]] = {}


def _slice(v: dict, home: str) -> str:
    if feed.about_home(v, home):
        return "home"
    if feed.home_in_world(v, home):
        return "home_world"
    if feed.is_us(v):
        return "us"
    return v["region"]


def pick_stories(home: str) -> list[dict]:
    now = time.time()
    pool = [v for v in feed.all_views() if now - v["published"] < 30 * 3600 and v["category"] != "Sport"]
    pool = feed.ranked(pool)
    buckets: dict[str, list] = {}
    for v in pool:
        buckets.setdefault(_slice(v, home), []).append(v)
    chosen, tech = [], 0
    for name, n in QUOTAS:
        taken = 0
        for v in buckets.get(name, []):
            if taken == n:
                break
            if v["category"] == "Tech & Science":
                if tech >= TECH_CAP:
                    continue
                tech += 1
            chosen.append(v)
            taken += 1
    return chosen


SYSTEM = """You are PULSE, a calm, sharp news editor writing a short daily read on the mood of the world for a reader in {home}.
Rules:
- Give a genuinely global picture. Do NOT lead with US politics, US tech companies or AI unless they truly are the biggest story for the whole world today.
- Order: {home} first, then how {home} and its people show up in the world, then the wider world across several regions.
- Use only the stories provided. Be specific: names, places, numbers. No hype, no filler.
- Every bullet ends with refs: the story numbers it is based on.
Reply with JSON only."""

SHAPE = """Return:
{{
 "temperature": 0-100 (0 = very calm world, 50 = normal churn, 100 = boiling over),
 "mood": "1-3 word mood of the world, e.g. 'Tense but steady'",
 "headline": "one sentence: the state of the world today",
 "home": [{{"text": "...", "refs": [n]}}]   // 2-3 bullets: what's happening in {home} now
 "home_world": [{{"text": "...", "refs": [n]}}] // 1-2 bullets: {home} abroad (deals, diplomacy, its people doing remarkable things). Empty list if nothing.
 "world": [{{"text": "...", "refs": [n]}}]  // 3-4 bullets from different regions
 "expect": [{{"text": "...", "refs": [n]}}] // 2-3 bullets: what to watch in the next days
 "meaning": "2-3 sentences: what this all means for someone in {home}"
}}"""


async def get_briefing(home: str, force: bool = False) -> dict:
    hit = _cache.get(home)
    if hit and not force and time.time() - hit[0] < BRIEFING_TTL:
        return hit[1]

    stories = pick_stories(home)
    if len(stories) < 8:
        return {"error": "Still gathering today's news. Try again in a minute."}

    lines = []
    for i, v in enumerate(stories, 1):
        where = v["country"] or v["region"].replace("_", " ").title()
        lines.append(f"{i}. [{v['source']} · {where} · {v['category']}] {v['title']}: {v['desc'][:150]}")
    today = datetime.now().strftime("%A %d %B %Y")
    user = f"Today is {today}.\n\nStories:\n" + "\n".join(lines) + "\n\n" + SHAPE.format(home=home)

    try:
        data = await chat(BIG_MODEL, SYSTEM.format(home=home), user,
                          as_json=True, max_tokens=2500, priority=True)
    except LLMUnavailable as e:
        return {"error": f"The briefing couldn't be generated right now ({e}). Try again shortly."}

    def bullets(key):
        out = []
        for b in data.get(key) or []:
            if isinstance(b, str):
                b = {"text": b, "refs": []}
            refs = [r for r in b.get("refs", []) if isinstance(r, int) and 1 <= r <= len(stories)]
            sources, seen = [], set()
            for r in refs:
                s = stories[r - 1]
                if s["source"] not in seen:          # one chip per outlet
                    seen.add(s["source"])
                    sources.append({"source": s["source"], "link": s["link"]})
            out.append({"text": b.get("text", ""), "sources": sources[:3]})
        return out

    try:
        temp = max(0, min(100, int(data.get("temperature", 50))))
    except (TypeError, ValueError):
        temp = 50
    result = {
        "temperature": temp,
        "mood": data.get("mood", ""),
        "headline": data.get("headline", ""),
        "home": bullets("home"),
        "home_world": bullets("home_world"),
        "world": bullets("world"),
        "expect": bullets("expect"),
        "meaning": data.get("meaning", ""),
        "country": home,
        "story_count": len(stories),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _cache[home] = (time.time(), result)
    return result
