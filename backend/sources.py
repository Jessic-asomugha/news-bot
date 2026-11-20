"""
Feeds: fetch every RSS feed at the same time (async), clean the entries,
and keep them in memory. A snapshot is written to disk so a cold start
shows news instantly while fresh feeds load in the background.
"""
import asyncio
import hashlib
import html
import json
import re
import time
from calendar import timegm

import feedparser
import httpx

from .config import DATA_DIR, FEED_TTL, FEEDS, ITEMS_PER_FEED, KEEP_HOURS

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/130 Safari/537.36 PULSE-news-reader"}
SNAPSHOT = DATA_DIR / "articles.json"

articles: dict[str, dict] = {}   # id -> article
last_refresh = 0.0
refreshing = False
_refresh_lock = asyncio.Lock()

# Words in an outlet's own tags / URL that tell us the section, used before
# the AI classifier has seen a story.
_HINT_WORDS = {
    "Business": ["business", "economy", "money", "finance", "markets", "naira", "banking", "energy", "oil"],
    "Sport": ["sport", "football", "soccer", "athletics", "basketball", "tennis", "super eagles", "afcon"],
    "Tech & Science": ["technology", "tech", "science", "ai", "innovation"],
    "Health": ["health", "medicine"],
    "Culture": ["entertainment", "culture", "music", "film", "nollywood", "arts", "lifestyle", "fashion"],
    "Nature & Environment": ["environment", "climate", "wildlife"],
    "World": ["politics", "news", "world", "metro", "security", "crime", "headlines", "africa", "national"],
}


def _clean(text: str, limit: int = 320) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    text = re.sub(r"The post .* appeared first on .*$", "", text).strip()
    text = re.sub(r"\[?(…|\.\.\.)\]?\s*(Read more|Continue reading).*$", "…", text, flags=re.I)
    return text[:limit].rsplit(" ", 1)[0] + "…" if len(text) > limit else text


def _image(entry) -> str:
    best, best_w = "", -1
    for m in entry.get("media_content", []) or []:
        if m.get("medium", "image") == "image" or "image" in m.get("type", ""):
            w = int(m.get("width") or 0)
            if w > best_w:
                best, best_w = m.get("url", ""), w
    if not best:
        thumbs = entry.get("media_thumbnail") or []
        if thumbs:
            best = thumbs[-1].get("url", "")
    if not best:
        for link in entry.get("links", []):
            if link.get("type", "").startswith("image"):
                best = link.get("href", "")
                break
    if not best:
        body = entry.get("summary", "") + "".join(c.get("value", "") for c in entry.get("content", []) or [])
        m = re.search(r'<img[^>]+src="([^"]+)"', body)
        if m:
            best = m.group(1)
    # BBC serves tiny 240px thumbnails by default; ask for a sharper one.
    return re.sub(r"ichef\.bbci\.co\.uk/(ace/standard|news)/\d+/", r"ichef.bbci.co.uk/\1/800/", best)


def _hint_category(entry, link: str, feed_hint):
    if feed_hint:
        return feed_hint
    tags = " ".join(t.get("term", "") for t in entry.get("tags", []) or []).lower()
    # only the section folders of the URL, not the slug (which is the headline)
    path_parts = set(re.sub(r"https?://[^/]+", "", link).lower().split("/")[:-2])
    for cat, words in _HINT_WORDS.items():
        if any(re.search(rf"\b{re.escape(w)}\b", tags) or w in path_parts for w in words):
            return cat
    return "World"


def _parse(raw: bytes, source: str, region: str, cat_hint) -> list[dict]:
    feed = feedparser.parse(raw)
    out = []
    for entry in feed.entries[:ITEMS_PER_FEED]:
        link = entry.get("link", "")
        title = _clean(entry.get("title", ""), 220)
        if not link or not title:
            continue
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = timegm(stamp) if stamp else time.time()
        out.append({
            "id": hashlib.sha1(link.encode()).hexdigest()[:12],
            "title": title,
            "desc": _clean(entry.get("summary", "")),
            "link": link,
            "source": source,
            "published": published,
            "image": _image(entry),
            "hint_region": region,
            "hint_category": _hint_category(entry, link, cat_hint),
        })
    return out


_validators: dict[str, dict] = {}   # url -> ETag / Last-Modified from the last fetch


async def _fetch(client: httpx.AsyncClient, feed) -> list[dict]:
    url, source, region, cat_hint = feed
    try:
        # "Has this changed since last time?" An unchanged feed answers 304
        # with no body, which makes repeat refreshes much lighter.
        r = await client.get(url, headers=_validators.get(url, {}))
        if r.status_code == 304:
            return []
        r.raise_for_status()
        v = {}
        if r.headers.get("etag"):
            v["If-None-Match"] = r.headers["etag"]
        if r.headers.get("last-modified"):
            v["If-Modified-Since"] = r.headers["last-modified"]
        _validators[url] = v
        # feedparser is CPU work; run it off the event loop so the server stays responsive
        return await asyncio.to_thread(_parse, r.content, source, region, cat_hint)
    except Exception as e:
        print(f"[FEEDS] {source} failed: {type(e).__name__} {url}", flush=True)
        return None


async def refresh(on_new=None) -> int:
    """Fetch all feeds in parallel. Returns the number of new stories.
    on_new() is called whenever a feed adds stories (wakes the classifier)."""
    global last_refresh, refreshing
    async with _refresh_lock:
        if time.time() - last_refresh < 60:      # someone else just refreshed
            return 0
        refreshing = True
        t = time.time()
        cutoff = time.time() - KEEP_HOURS * 3600
        seen_titles = {_title_key(a["title"]) for a in articles.values()}
        new = failed = 0
        # pool=None: a feed waiting for a free connection slot never times out.
        timeout = httpx.Timeout(15, connect=8, pool=None)
        # 10 downloads at a time: on a slow connection, 41 at once all time out.
        limits = httpx.Limits(max_connections=10)
        # Home-country feeds first so they get the first connection slots.
        ordered = sorted(FEEDS, key=lambda f: f[2] != "nigeria")
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=timeout, limits=limits,
                                         follow_redirects=True) as client:
                # as_completed: each feed's stories are added the moment it arrives,
                # so a slow outlet never holds up the fast ones.
                for next_done in asyncio.as_completed([_fetch(client, f) for f in ordered]):
                    added = 0
                    batch = await next_done
                    if batch is None:
                        failed += 1
                        continue
                    for a in batch:
                        if a["published"] < cutoff or a["id"] in articles:
                            continue
                        key = _title_key(a["title"])
                        if key in seen_titles:      # same story syndicated by two feeds
                            continue
                        seen_titles.add(key)
                        articles[a["id"]] = a
                        added += 1
                    new += added
                    if added and on_new:
                        on_new()
        finally:
            refreshing = False
        for aid in [k for k, a in articles.items() if a["published"] < cutoff]:
            del articles[aid]
        last_refresh = time.time()
        if failed > len(FEEDS) // 2:
            # Mostly failed (connection trouble): count as stale again in ~2 min.
            last_refresh -= FEED_TTL - 120
        print(f"[FEEDS] {new} new, {failed} failed, {len(articles)} total, {time.time() - t:.1f}s", flush=True)
        _save_snapshot()
        return new


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())[:60]


def is_stale() -> bool:
    return time.time() - last_refresh > FEED_TTL


def _save_snapshot():
    try:
        SNAPSHOT.write_text(json.dumps(list(articles.values()), ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        print(f"[FEEDS] snapshot not saved: {e}")


def load_snapshot():
    try:
        cutoff = time.time() - KEEP_HOURS * 3600
        for a in json.loads(SNAPSHOT.read_text(encoding="utf-8")):
            if a["published"] >= cutoff:
                articles[a["id"]] = a
        print(f"[FEEDS] {len(articles)} stories loaded from snapshot")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
