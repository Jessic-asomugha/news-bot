# PULSE: Project Brief

## What PULSE is
An AI-powered news app where the user decides exactly what she wants to see, even niche topics (nature, marine life), and the model finds relevant results from across the internet. We are moving off Streamlit. The approach changes, not the project.

## Owner notes
- Owner is new to FastAPI. Explain choices briefly as you go.
- Comfortable with HTML/CSS. Can read React but is not fluent, so keep the frontend plain.
- Speed must not be lost.

## Stack
- Backend: FastAPI
- Frontend: plain HTML + Tailwind
- World temperature briefing: Groq free API (key already working)
- Article summaries: HuggingFace BART (swap only if speed demands it)
- Search API (Tavily, Brave or Serper): decide at build time

## V1 scope
Three features: **world temperature**, **categories**, **subcategories**.
- World temperature = quick read on the mood of the world: what's happening globally, what to expect, what it means.
- The briefing generates only when the user taps it, to keep the app fast.

## Layout
- Top nav bar of categories.
- Default landing section is World Temperature with a greeting ("what's going on in the world today?").
- Below it: a few recent headlines (about three highlighted), then a "this might interest you today" section driven by chosen interests.
- Must feel like a news interface (pictures, alignment, colour, arrangement) but NOT the stereotypical hero image + photo grid look.
- Clean and beautiful. Design is not the owner's strongest area, so make strong design decisions.
- Home is optional and would only be an About page.

## Interests
- First-time users pick interests from category boxes (e.g. AI, robotics) plus a text box for custom topics.
- A topic filter reorders the feed (AI first, robotics second, startups third). It does not hide other stories.
- If little is found for a topic, say so and suggest trying something else.
- No behaviour tracking in V1.

## Search flow
1. First search hits primary outlets (BBC, CNN, Al Jazeera) for speed.
2. If results aren't useful, an "explore more" option goes deeper across the web.

## Known problems to fix
- **US-centric briefing.** Tech and US stories (Elon Musk, ChatGPT) lead. It needs a real global range, with tech and US news not leading.
- **Wrong categorisation.** Example: a finance story landing under Food & Culture > Arts & Entertainment. The agent does its job but isn't smart. Add real intelligence to fetching, categorising and summarising.
- **Slow feeds.** They load, but slowly.

## Region awareness
Based on the user's location (Nigeria), cover: what's happening in the country now, how Nigeria shows up globally (deals with other countries, Nigerians doing extraordinary things), then the wider world.

## Out of scope for V1 (V2)
- "News in waiting" feature
- Behaviour tracking

## Build plan
One batched build covering everything above: balanced global and country sources, smarter categorisation, faster loading, FastAPI backend, UI, interest picker, tap-to-generate briefing. Plan first, then build, so work isn't cut off midway.