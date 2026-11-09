"""
On-demand story summaries: only made when the reader opens a story.
Groq first (fast, explains why it matters). If Groq fails, fall back to the
local BART model, which loads only the first time it's needed.
"""
import asyncio
import re

import httpx

from . import sources, store
from .config import SMALL_MODEL
from .llm import LLMUnavailable, chat
from .sources import HEADERS

_bart = None


async def _article_text(link: str, fallback: str) -> str:
    """Grab the story's paragraphs from its page; use the feed blurb if that fails."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=6, follow_redirects=True) as c:
            r = await c.get(link)
        paras = re.findall(r"<p[^>]*>(.*?)</p>", r.text, re.S | re.I)
        text = " ".join(re.sub(r"<[^>]+>", "", p).strip() for p in paras)
        text = re.sub(r"\s+", " ", text)
        if len(text) > 400:
            return text[:3500]      # first ~600 words is plenty, and keeps tokens down
    except Exception:
        pass
    return fallback


def _bart_summary(text: str) -> str:
    global _bart
    if _bart is None:
        from transformers import pipeline
        print("[SUMMARY] loading BART fallback (first time only)…")
        _bart = pipeline("summarization", model="facebook/bart-large-cnn")
    return _bart(text[:2500], max_length=110, min_length=40, do_sample=False)[0]["summary_text"]


async def summarize(article_id: str) -> dict:
    cached = store.summaries.get(article_id)
    if cached:
        return cached
    a = sources.articles.get(article_id)
    if not a:
        return {"error": "Story no longer available."}

    text = await _article_text(a["link"], f"{a['title']}. {a['desc']}")
    try:
        data = await chat(
            SMALL_MODEL,
            "You write crisp news summaries for a busy reader in Nigeria. Plain, neutral, no hype. Reply with JSON only.",
            f"Headline: {a['title']}\nOutlet: {a['source']}\n\nArticle:\n{text}\n\n"
            'Return {"summary": "3 short sentences: what happened, who, key numbers", '
            '"why": "one sentence on why it matters"}',
            as_json=True, max_tokens=700, priority=True)
        result = {"summary": data.get("summary", ""), "why": data.get("why", ""), "by": "groq"}
    except LLMUnavailable as e:
        print(f"[SUMMARY] Groq unavailable ({e}); using BART")
        if len(text) < 200:
            return {"summary": a["desc"], "why": "", "by": "feed"}
        summary = await asyncio.to_thread(_bart_summary, text)
        result = {"summary": summary, "why": "", "by": "bart"}

    store.summaries.set(article_id, result)
    store.summaries.save()
    return result
