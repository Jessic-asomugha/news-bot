"""
PULSE web server (FastAPI).

Run:  venv\\Scripts\\python -m uvicorn backend.main:app --reload
Open: http://127.0.0.1:8000

FastAPI in one paragraph: each function decorated with @app.get(...) is a URL.
Its arguments become query parameters (?country=Nigeria), it returns a dict,
and FastAPI turns that into JSON. `async def` lets one server handle many
requests at once while it waits on the network (feeds, Groq, Tavily).
"""
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from . import briefing, classify, feed, search, sources, store, summarize
from .config import DEFAULT_COUNTRY, NAV, ROOT, TOPICS

_background: set[asyncio.Task] = set()


def _spawn(coro):
    """Run something in the background without the request waiting for it."""
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _refresh_then_classify():
    try:
        await sources.refresh(on_new=classify.wake)
    except Exception as e:
        print(f"[FEEDS] refresh error: {e}", flush=True)


async def ensure_fresh():
    """Stale-while-revalidate: answer from what we have, refresh behind the scenes.
    Only a completely empty cache (very first run) makes the reader wait, and
    even then only until the first ~100 stories are in (max ~8s)."""
    if sources.is_stale() and not sources.refreshing:
        _spawn(_refresh_then_classify())
    waited = 0.0
    while len(sources.articles) < 100 and waited < 8:
        if not sources.refreshing and sources.last_refresh:
            break
        await asyncio.sleep(0.25)
        waited += 0.25


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: show last session's stories instantly, start the classifier,
    # and fetch fresh feeds in the background.
    sources.load_snapshot()
    _spawn(classify.worker())
    _spawn(_refresh_then_classify())
    yield
    store.save_all()


app = FastAPI(title="PULSE", lifespan=lifespan)


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """Tell the browser to re-check HTML/JS on each load, so edits show up
    immediately instead of an old cached copy."""
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/meta")
async def meta():
    """Everything the frontend needs to draw the nav and interest picker."""
    return {
        "nav": NAV,
        "topics": TOPICS,
        "presets": list(feed.PRESETS),
        "default_country": DEFAULT_COUNTRY,
    }


@app.get("/api/home")
async def home(country: str = DEFAULT_COUNTRY, i: list[str] = Query(default=[])):
    """Landing page: three headlines, home-country now, and 'for you'."""
    await ensure_fresh()
    interests = [x.strip() for x in i if x.strip()][:12]
    return await feed.home_page(country, interests)


@app.get("/api/section/{name}")
async def section(name: str, chip: str | None = None, country: str = DEFAULT_COUNTRY):
    await ensure_fresh()
    return feed.section(name, chip, country)


@app.get("/api/briefing")
async def get_briefing(country: str = DEFAULT_COUNTRY, refresh: bool = False):
    """World Temperature. Only called when the reader taps the button."""
    await ensure_fresh()
    return await briefing.get_briefing(country, force=refresh)


@app.get("/api/summary/{article_id}")
async def get_summary(article_id: str):
    result = await summarize.summarize(article_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/search")
async def do_search(q: str, deep: bool = False):
    return await search.search(q, deep)


@app.get("/api/status")
async def status():
    views = feed.all_views()
    return {
        "stories": len(views),
        "classified": sum(v["classified"] for v in views),
        "last_refresh_seconds_ago": round(time.time() - sources.last_refresh) if sources.last_refresh else None,
    }


# The frontend (plain HTML/JS) is served from the same server, so there's
# one thing to run. Mounted last so /api routes win.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
