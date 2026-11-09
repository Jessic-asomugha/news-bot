"""
Ranking: which stories go where.
- headline picks with a real global spread (US and tech can't lead)
- the home-country tab and "how your country shows up in the world"
- interest ordering: matching stories rise to the top, nothing is hidden
"""
import re
import time

from . import classify, sources, store
from .config import REGION_CHIPS, SMALL_MODEL, TOPICS
from .llm import LLMUnavailable, chat

US = {"United States", "USA", "US", "United States of America"}

# Interest boxes on the picker. (category, subcategory or None, extra keywords)
PRESETS = {
    "AI": ("Tech & Science", "AI", ["artificial intelligence", "ai", "chatgpt", "openai", "machine learning", "chatbot"]),
    "Robotics": ("Tech & Science", "Robotics", ["robot", "robots", "robotics", "drone", "drones", "automation"]),
    "Startups": ("Business", "Startups & Funding", ["startup", "start-up", "funding", "venture", "fintech", "raises"]),
    "Space": ("Tech & Science", "Space", ["nasa", "rocket", "satellite", "moon", "mars", "astronaut", "spacex"]),
    "Gadgets": ("Tech & Science", "Gadgets & Internet", ["iphone", "smartphone", "app", "gadget", "android"]),
    "Cybersecurity": ("Tech & Science", "Cybersecurity", ["hack", "hackers", "cyber", "ransomware", "data breach"]),
    "Science": ("Tech & Science", "Science & Research", ["scientists", "study", "research", "discovery"]),
    "Climate": ("Nature & Environment", "Climate", ["climate", "emissions", "warming", "cop"]),
    "Wildlife": ("Nature & Environment", "Wildlife", ["wildlife", "species", "elephant", "bird", "animals"]),
    "Marine life": ("Nature & Environment", "Marine Life", ["ocean", "marine", "whale", "coral", "shark", "sea", "fish"]),
    "Conservation": ("Nature & Environment", "Conservation", ["conservation", "forest", "deforestation", "protected"]),
    "Markets": ("Business", "Markets", ["stocks", "shares", "markets", "naira", "currency", "bonds"]),
    "Crypto": ("Business", None, ["crypto", "bitcoin", "blockchain", "stablecoin"]),
    "Oil & energy": ("Business", "Energy & Commodities", ["oil", "gas", "fuel", "petrol", "energy", "opec", "dangote"]),
    "Politics": ("World", "Politics & Diplomacy", ["president", "government", "senate", "minister"]),
    "Elections": ("World", "Elections", ["election", "vote", "polls", "campaign"]),
    "Conflict": ("World", "Conflict & Security", ["war", "attack", "military", "ceasefire"]),
    "Public health": ("Health", "Public Health", ["health", "vaccine", "hospital"]),
    "Medical research": ("Health", "Medicine & Research", ["drug", "treatment", "trial", "cancer"]),
    "Football": ("Sport", "Football", ["football", "super eagles", "premier league", "afcon", "goal"]),
    "Music": ("Culture", "Music", ["music", "album", "afrobeats", "singer", "concert"]),
    "Film & TV": ("Culture", "Film & TV", ["film", "movie", "nollywood", "series", "netflix"]),
    "Books & Art": ("Culture", "Books & Art", ["book", "novel", "author", "art", "exhibition"]),
    "Food": ("Culture", "Food", ["food", "recipe", "restaurant", "chef"]),
    "Fashion": ("Culture", "Fashion & Lifestyle", ["fashion", "designer", "style"]),
}


# ─────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────
def all_views() -> list[dict]:
    return [classify.view(a) for a in sources.articles.values()]


def base_score(v: dict, now: float | None = None) -> float:
    age_h = ((now or time.time()) - v["published"]) / 3600
    fresh = 3 if age_h < 3 else 2 if age_h < 8 else 1 if age_h < 24 else 0
    return v["importance"] * 2 + fresh


def is_us(v: dict) -> bool:
    return v["country"] in US


def diversify(items: list[dict], us_share: float = 0.2, tech_share: float | None = 0.2) -> list[dict]:
    """Re-order so no region runs more than twice in a row and the US (and,
    optionally, tech) can't take more than a small share of the top of the list."""
    pool, out = list(items), []
    while pool:
        n = len(out) + 1
        us_used = sum(is_us(v) for v in out)
        tech_used = sum(v["category"] == "Tech & Science" for v in out)
        last_two = [v["region"] for v in out[-2:]]
        pick = None
        for v in pool:
            if is_us(v) and us_used + 1 > max(1, us_share * n):
                continue
            if tech_share is not None and v["category"] == "Tech & Science" and tech_used + 1 > max(1, tech_share * n):
                continue
            if len(last_two) == 2 and last_two[0] == last_two[1] == v["region"]:
                continue
            pick = v
            break
        pick = pick or pool[0]          # nothing fits the rules: take the best remaining
        pool.remove(pick)
        out.append(pick)
    return out


def ranked(items: list[dict]) -> list[dict]:
    now = time.time()
    return sorted(items, key=lambda v: base_score(v, now), reverse=True)


def card(v: dict, because: str = "") -> dict:
    out = {k: v[k] for k in ("id", "title", "desc", "link", "source", "published", "image",
                             "category", "subcategory", "region", "country", "importance", "classified")}
    if because:
        out["because"] = because
    return out


# ─────────────────────────────────────────────
# Home-country helpers
# ─────────────────────────────────────────────
def about_home(v: dict, home: str) -> bool:
    return v["country"] == home

def home_in_world(v: dict, home: str) -> bool:
    return v["country"] != home and home in v.get("countries", [])


# ─────────────────────────────────────────────
# Interests
# ─────────────────────────────────────────────
def _singular(w: str) -> str:
    # "turtles" -> "turtle", so the regex below (which allows an optional s) matches both
    return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w


def _words_re(words: list[str]):
    words = [_singular(w) for w in {w.lower().strip() for w in words} if len(w) >= 2]
    if not words:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")s?\b", re.I)


async def expand_topic(topic: str) -> dict:
    """Turn a custom topic ("sea turtles") into match words and related
    suggestions with one small, cached Groq call.
    core: specific terms; one is enough to say a story is about the topic.
    context: supporting terms; a story needs two, in the right category."""
    key = topic.lower().strip()
    cached = store.topic_expansions.get(key)
    if cached and "core" in cached:
        return cached
    try:
        data = await chat(
            SMALL_MODEL,
            "You help a news app match headlines to a reader's interest. Precision matters more than recall. Reply with JSON only.",
            f'Interest: "{topic}"\nReturn {{'
            f'"core": [4-10 lowercase words or names so specific that a headline containing one is almost surely about this interest. '
            f'Prefer single words and names (brands, people, events). Do not glue a place onto every term: for "fintech in Africa" give fintech, mobile money, opay, m-pesa, flutterwave, paystack. '
            f'Include the core noun itself. e.g. "sea turtles" -> turtle, leatherback, hawksbill, loggerhead; "Nollywood" -> nollywood, nigerian film, nigerian actor, amvca], '
            f'"context": [4-8 broader supporting words, e.g. "sea turtles" -> nesting, hatchlings, marine, poaching], '
            f'"category": one of {list(TOPICS)}, '
            f'"related": [3 related, slightly broader interests to suggest if little news is found]}}',
            as_json=True, max_tokens=700, priority=True)
        result = {
            "core": [str(k).lower() for k in data.get("core", [])][:10],
            "context": [str(k).lower() for k in data.get("context", [])][:8],
            "category": data.get("category") if data.get("category") in TOPICS else None,
            "related": [str(r) for r in data.get("related", [])][:3],
        }
    except LLMUnavailable:
        # Don't cache a failure; try again next time.
        return {"core": [key], "context": [], "category": None, "related": []}
    # Always include the topic phrase itself (not its separate words: in
    # "fintech in Africa", "africa" alone would match every African story).
    result["core"] = list(dict.fromkeys([key] + result["core"]))
    store.topic_expansions.set(key, result)
    store.topic_expansions.save()
    return result


async def interest_matchers(interests: list[str]) -> list[tuple[str, callable, list[str]]]:
    """Build one match function per interest, in the user's priority order."""
    out = []
    for name in interests:
        if name in PRESETS:
            cat, sub, words = PRESETS[name]
            rx = _words_re(words)
            related = [p for p, (c, _, _) in PRESETS.items() if c == cat and p != name][:3]

            def match(v, cat=cat, sub=sub, rx=rx):
                if sub and v["subcategory"] == sub:
                    return True
                if v["category"] == cat and not sub:
                    return bool(rx.search(v["title"] + " " + v["desc"]))
                return v["category"] == cat and bool(rx.search(v["title"]))
        else:
            exp = await expand_topic(name)
            core = _words_re(exp["core"])
            context = _words_re(exp["context"])
            related = exp["related"]

            def match(v, core=core, context=context, cat=exp["category"]):
                text = v["title"] + " " + v["desc"]
                if core and core.search(text):
                    return True
                if context and (cat is None or v["category"] == cat):
                    return len({m.lower() for m in context.findall(text)}) >= 2
                return False
        out.append((name, match, related))
    return out


async def for_you(interests: list[str], pool: list[dict], limit: int = 24):
    """Stories ordered by interest (first interest weighs most), then the
    rest of today's news. Also reports interests with almost nothing found."""
    matchers = await interest_matchers(interests)
    now = time.time()
    counts = {name: 0 for name, _, _ in matchers}
    by_interest: dict[str, list] = {name: [] for name, _, _ in matchers}
    unmatched = []
    for v in pool:
        for name, match, _ in matchers:
            if match(v):
                counts[name] += 1
                by_interest[name].append(v)
                break
        else:
            unmatched.append(v)
    # Priority order first: the best 4 stories of interest #1, then of #2, ...
    # then everything else that matched, by score. Nothing is hidden.
    lead, rest = [], []
    for name, _, _ in matchers:
        best = ranked(by_interest[name])
        lead += [(v, name) for v in best[:4]]
        rest += [(v, name) for v in best[4:]]
    rest.sort(key=lambda t: base_score(t[0], now), reverse=True)
    matched = [card(v, name) for v, name in lead + rest][:limit]
    more = diversify(ranked(unmatched))[: max(8, limit - len(matched))]
    thin = [{"interest": name, "found": counts[name], "suggest": related}
            for name, _, related in matchers if counts[name] < 2]
    return {"matched": matched, "more": [card(v) for v in more], "thin": thin}


# ─────────────────────────────────────────────
# Page data
# ─────────────────────────────────────────────
def top_headlines(pool: list[dict], n: int = 3) -> list[dict]:
    """Three big stories from different parts of the world. At most one US
    story, at most one tech story, preferring hard news from the last day."""
    now = time.time()
    fresh = [v for v in pool if now - v["published"] < 24 * 3600 and v["image"]]
    fresh = ranked([v for v in fresh if v["category"] in ("World", "Business", "Health", "Nature & Environment")]) or ranked(fresh)
    picks, regions = [], set()
    for v in fresh:
        if v["region"] in regions or (is_us(v) and any(is_us(p) for p in picks)):
            continue
        picks.append(v)
        regions.add(v["region"])
        if len(picks) == n:
            break
    return picks


async def home_page(country: str, interests: list[str]) -> dict:
    pool = all_views()
    top = top_headlines(pool)
    top_ids = {v["id"] for v in top}
    rest = [v for v in pool if v["id"] not in top_ids]
    home_now = ranked([v for v in rest if about_home(v, country)])[:6]
    shown = top_ids | {v["id"] for v in home_now}
    fy = await for_you(interests, [v for v in rest if v["id"] not in shown]) if interests else None
    return {
        "top": [card(v) for v in top],
        "home_now": [card(v) for v in home_now],
        "for_you": fy,
        "classified_share": round(sum(v["classified"] for v in pool) / max(1, len(pool)), 2),
    }


def section(name: str, chip: str | None, country: str) -> dict:
    pool = all_views()
    if name == "HOME":
        items = [v for v in pool if about_home(v, country) or home_in_world(v, country)]
        chips = list(REGION_CHIPS) + ["In the world"]
        if chip == "In the world":
            items = [v for v in items if home_in_world(v, country)]
        elif chip in REGION_CHIPS:
            items = [v for v in items if about_home(v, country) and REGION_CHIPS[chip](v)]
        items = ranked(items)
    elif name == "Africa":
        items = [v for v in pool if v["region"] == "africa" and v["country"] != country]
        chips = list(REGION_CHIPS)
        if chip in REGION_CHIPS:
            items = [v for v in items if REGION_CHIPS[chip](v)]
        items = diversify(ranked(items), us_share=0, tech_share=None)
    elif name in TOPICS:
        items = [v for v in pool if v["category"] == name]
        chips = TOPICS[name]
        if chip in chips:
            items = [v for v in items if v["subcategory"] == chip]
        # tech can lead in the Tech tab; everywhere the US is kept in proportion
        items = diversify(ranked(items), tech_share=None)
    else:
        return {"items": [], "chips": []}
    return {"items": [card(v) for v in items[:40]], "chips": chips}
