"""
Smart categorisation. The old bot matched keywords, so a finance story that
mentioned a festival landed in Culture. Here a small Groq model reads each
headline and decides what the story is *about*, plus where it happens and
how important it is.

Runs in the background in small batches (free tier = 8k tokens/minute).
Results are cached on disk by story id, so each story is classified once.
Until then a story uses its outlet's own section as a fallback.
"""
import asyncio
import json

from . import sources, store
from .config import REGIONS, SMALL_MODEL, TOPICS
from .llm import LLMUnavailable, chat

BATCH = 30
PAUSE = 25          # seconds between batches: ~3k tokens each keeps us under 8k/min

_topic_lines = "\n".join(f"- {c}: {', '.join(subs)}" for c, subs in TOPICS.items())
SYSTEM = f"""You sort news stories for a global news app read in Nigeria.
For each story return:
  c: category, exactly one of the names below
  s: subcategory, exactly one from that category's list
  r: region where the story happens: {"|".join(REGIONS)}
  k: main country (English short name, e.g. "Nigeria", "United States"), "" if none
  x: other countries centrally involved (list, often empty). Include a country when its people feature notably abroad (e.g. a Nigerian scientist honoured in Japan -> k "Japan", x ["Nigeria"])
  i: importance 1-5 for a reader anywhere in the world (5 = major world event; 1 = trivial, promotional or very local)

Categories:
{_topic_lines}

Judge what the story is ABOUT, not which words appear. A bank's profits story is Business even if it mentions a festival or a film. A football club's finances is Sport. Elections, governments, wars, protests, courts are World.
Crashes, fires, building collapses are World > Accidents & Disasters; storms, floods, earthquakes are Nature & Environment > Weather & Natural Disasters.
Religious festivals and ceremonies are Culture > Faith & Traditions. Social policy and everyday-life stories are World > Society.
If no subcategory fits well, pick the closest; never invent one.
Reply with JSON only: {{"items":[{{"id":"...","c":"...","s":"...","r":"...","k":"...","x":[],"i":3}}]}}"""

_wake = asyncio.Event()


def view(a: dict) -> dict:
    """The article as the frontend sees it: classification if we have it, else hints."""
    c = store.classifications.get(a["id"])
    hint_region = a["hint_region"]
    base = {k: a[k] for k in ("id", "title", "desc", "link", "source", "published", "image")}
    if c:
        base.update(c, classified=True)
    else:
        base.update(
            category=a["hint_category"],
            subcategory="",
            region="africa" if hint_region == "nigeria" else hint_region,
            country="Nigeria" if hint_region == "nigeria" else "",
            countries=[],
            importance=2,
            classified=False,
        )
    return base


def _valid(item: dict) -> dict | None:
    cat = item.get("c")
    if cat not in TOPICS:
        return None
    sub = item.get("s") if item.get("s") in TOPICS[cat] else ""
    region = item.get("r") if item.get("r") in REGIONS else "global"
    try:
        importance = max(1, min(5, int(item.get("i", 2))))
    except (TypeError, ValueError):
        importance = 2
    return {
        "category": cat,
        "subcategory": sub,
        "region": region,
        "country": str(item.get("k") or "")[:40],
        "countries": [str(x)[:40] for x in (item.get("x") or [])][:5],
        "importance": importance,
    }


def _pending() -> list[dict]:
    todo = [a for a in sources.articles.values() if a["id"] not in store.classifications]
    # Home-country and mixed feeds first (most likely to be mis-sorted), newest first.
    todo.sort(key=lambda a: (a["hint_region"] != "nigeria", -a["published"]))
    return todo


async def classify_batch(batch: list[dict]) -> int:
    lines = "\n".join(
        json.dumps({"id": a["id"], "outlet": a["source"], "title": a["title"], "about": a["desc"][:140]},
                   ensure_ascii=False)
        for a in batch)
    result = await chat(SMALL_MODEL, SYSTEM, lines, as_json=True, max_tokens=4000)
    done = 0
    wanted = {a["id"] for a in batch}
    for item in result.get("items", []):
        if item.get("id") in wanted and (v := _valid(item)):
            store.classifications.set(item["id"], v)
            done += 1
    # Anything the model skipped keeps its fallback; don't spend tokens retrying it.
    for a in batch:
        if a["id"] not in store.classifications:
            store.classifications.set(a["id"], None)
    store.classifications.save()
    return done


async def worker():
    """Forever: classify whatever is pending, then sleep until new stories arrive."""
    while True:
        todo = _pending()
        if not todo:
            _wake.clear()
            await _wake.wait()
            continue
        batch = todo[:BATCH]
        try:
            n = await classify_batch(batch)
            print(f"[CLASSIFY] {n}/{len(batch)} sorted, {len(todo) - len(batch)} left")
        except LLMUnavailable as e:
            print(f"[CLASSIFY] paused: {e}")
            await asyncio.sleep(60)
        await asyncio.sleep(PAUSE)


def wake():
    _wake.set()
