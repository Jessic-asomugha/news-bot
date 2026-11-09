"""
The one place that talks to Groq. Two jobs besides the call itself:
- respect the free tier's tokens-per-minute limit (wait and retry on 429)
- let the briefing jump the queue ahead of background classification
"""
import asyncio
import json
import re

from groq import AsyncGroq, RateLimitError

from .config import GROQ_API_KEY

client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Background jobs wait while a user-facing request (briefing, summary) is running.
_priority_users = 0
_priority_idle = asyncio.Event()
_priority_idle.set()


class LLMUnavailable(Exception):
    pass


async def chat(model: str, system: str, user: str, *, as_json: bool = False,
               max_tokens: int = 1500, priority: bool = False, retries: int = 3):
    """Send one chat request. Returns text, or a dict when as_json=True."""
    global _priority_users
    if client is None:
        raise LLMUnavailable("GROQ_API_KEY missing from .env")

    if priority:
        _priority_users += 1
        _priority_idle.clear()
    else:
        await _priority_idle.wait()

    try:
        for attempt in range(retries + 1):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    response_format={"type": "json_object"} if as_json else None,
                    reasoning_effort="low",      # gpt-oss "thinks" first; low keeps token use down
                    max_completion_tokens=max_tokens,
                    temperature=0.3,
                )
                text = (resp.choices[0].message.content or "").strip()
                return _parse_json(text) if as_json else text
            except RateLimitError as e:
                if attempt == retries:
                    raise LLMUnavailable("Groq rate limit") from e
                wait = _retry_after(e)
                print(f"[LLM] rate limited, waiting {wait:.0f}s")
                await asyncio.sleep(wait)
            except Exception as e:
                raise LLMUnavailable(str(e)) from e
    finally:
        if priority:
            _priority_users -= 1
            if _priority_users == 0:
                _priority_idle.set()


def _retry_after(e: RateLimitError) -> float:
    try:
        return min(float(e.response.headers.get("retry-after", 10)) + 1, 60)
    except Exception:
        return 15


def _parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise LLMUnavailable("Model did not return JSON")
