# PULSE

AI news reader: you choose what you follow, PULSE finds it across ~40 outlets
(Nigeria, Africa and the world), sorts it properly, and gives you a one-tap
read on the mood of the world.

## Run it

```
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000

`.env` needs:

```
GROQ_API_KEY=...     # sorting stories, summaries, World Temperature
TAVILY_API_KEY=...   # "Explore" search
```

## How it fits together

| File | Job |
|---|---|
| `backend/config.py` | Feeds, categories, models, cache times. Start here to tweak things. |
| `backend/sources.py` | Fetches all feeds in parallel, cached; a disk snapshot makes restarts instant. |
| `backend/classify.py` | Groq reads each headline and decides category, place and importance (background, once per story). |
| `backend/feed.py` | Ranking: global headlines, home-country tab, interest ordering. |
| `backend/briefing.py` | World Temperature, region-balanced, generated only on tap. |
| `backend/summarize.py` | "Quick read" summaries on demand: Groq, BART fallback. |
| `backend/search.py` | Tavily: main outlets first, "explore more" goes wider. |
| `backend/main.py` | The FastAPI routes (`/api/...`) and serving the frontend. |
| `frontend/` | Plain HTML + Tailwind + one JS file. |

Groq is used sparingly (free tier): every result is cached in `data/`, and
nothing calls Groq on a normal page load. The old Streamlit version is in `legacy/`.
