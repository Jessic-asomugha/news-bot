import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from agent.news_agent import run_news_agent
from config import CATEGORIES, MAX_ARTICLES
from agent.tools import validate_subcategory
from agent.waitlist_checker import (
    run_waitlist_check, add_to_waitlist, remove_from_waitlist,
    get_pending_items, get_matched_items,
)
from agent.nlp_utils import extract_keywords, find_best_matches
from agent.briefing import generate_briefing, fetch_briefing_articles
from sources.feeds import get_all_articles

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PULSE — AI News",
    page_icon="⚡",
    layout="centered",
)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "custom_subcategories" not in st.session_state:
    st.session_state.custom_subcategories = {cat: {} for cat in CATEGORIES}
if "validation_message" not in st.session_state:
    st.session_state.validation_message = None
if "article_cache" not in st.session_state:
    st.session_state.article_cache = {}
if "waitlist_checked" not in st.session_state:
    st.session_state.waitlist_checked = False
if "new_matches" not in st.session_state:
    st.session_state.new_matches = []
if "briefing_result" not in st.session_state:
    st.session_state.briefing_result = None

# ─────────────────────────────────────────────
# WAITLIST CHECK ON APP OPEN
# ─────────────────────────────────────────────
if not st.session_state.waitlist_checked:
    with st.spinner("Checking your news waitlist..."):
        st.session_state.new_matches = run_waitlist_check()
    st.session_state.waitlist_checked = True

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

    html, body, .stApp { background-color: #080E1A !important; color: #E8EDF5; }
    #MainMenu, footer, header, .stDeployButton { visibility: hidden; }
    .block-container { padding-top: 2.5rem !important; max-width: 800px !important; }

    .masthead { border-bottom: 1px solid rgba(0,220,255,0.2); padding-bottom: 1.4rem; margin-bottom: 1.8rem; }
    .masthead-label { font-family: 'Inter', sans-serif; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.18em; color: #00DCFF; text-transform: uppercase; margin-bottom: 0.4rem; }
    .masthead-title { font-family: 'Syne', sans-serif; font-size: 3.2rem; font-weight: 800; line-height: 1; color: #FFFFFF; letter-spacing: -0.02em; margin: 0 0 0.5rem 0; }
    .masthead-title span { color: #00DCFF; }
    .masthead-sub { font-family: 'Inter', sans-serif; font-size: 0.92rem; font-weight: 300; color: #7A8BA8; margin: 0; }

    .stTabs [data-baseweb="tab-list"] { background: transparent !important; border-bottom: 1px solid rgba(255,255,255,0.07) !important; gap: 0.2rem; }
    .stTabs [data-baseweb="tab"] { font-family: 'Syne', sans-serif !important; font-size: 0.82rem !important; font-weight: 600 !important; letter-spacing: 0.06em !important; color: #3D5068 !important; background: transparent !important; border: none !important; padding: 0.6rem 1.1rem !important; text-transform: uppercase; }
    .stTabs [aria-selected="true"] { color: #00DCFF !important; border-bottom: 2px solid #00DCFF !important; }

    .stSelectbox > div > div { background: #0D1626 !important; border: 1px solid rgba(0,220,255,0.25) !important; border-radius: 8px !important; color: #E8EDF5 !important; font-family: 'Inter', sans-serif !important; }
    .stTextInput input { background: #0D1626 !important; border: 1px solid rgba(0,220,255,0.25) !important; border-radius: 8px !important; color: #E8EDF5 !important; font-family: 'Inter', sans-serif !important; font-size: 0.95rem !important; padding: 0.65rem 1rem !important; }
    .stTextInput input:focus { border-color: #00DCFF !important; box-shadow: 0 0 0 3px rgba(0,220,255,0.1) !important; }
    .stTextInput input::placeholder { color: #3D5068 !important; }

    .stButton > button { background: transparent !important; color: #00DCFF !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; font-size: 0.82rem !important; letter-spacing: 0.08em !important; border: 1px solid rgba(0,220,255,0.4) !important; border-radius: 8px !important; padding: 0.5rem 1.2rem !important; transition: all 0.2s !important; }
    .stButton > button:hover { background: rgba(0,220,255,0.08) !important; border-color: #00DCFF !important; box-shadow: 0 0 12px rgba(0,220,255,0.15) !important; }

    .streamlit-expanderHeader { background: #0D1626 !important; border: 1px solid rgba(0,220,255,0.12) !important; border-radius: 8px !important; color: #3D5068 !important; font-family: 'Inter', sans-serif !important; font-size: 0.82rem !important; }
    .streamlit-expanderContent { background: #0D1626 !important; border: 1px solid rgba(0,220,255,0.12) !important; border-top: none !important; border-radius: 0 0 8px 8px !important; padding: 1rem !important; }

    .results-header { font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 500; letter-spacing: 0.16em; color: #3D5068; text-transform: uppercase; margin: 1.5rem 0 1rem; display: flex; align-items: center; gap: 0.8rem; }
    .results-header::after { content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.05); }

    .article-card { background: #0D1626; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.5rem 1.8rem; margin-bottom: 0.9rem; position: relative; transition: border-color 0.2s, transform 0.2s; }
    .article-card:hover { border-color: rgba(0,220,255,0.25); transform: translateY(-2px); }
    .article-card::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #00DCFF; border-radius: 12px 0 0 12px; opacity: 0.6; }
    .source-tag { display: inline-block; font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; color: #00DCFF; background: rgba(0,220,255,0.08); border: 1px solid rgba(0,220,255,0.2); border-radius: 4px; padding: 0.15rem 0.55rem; margin-right: 0.5rem; }
    .date-tag { font-family: 'Inter', sans-serif; font-size: 0.76rem; color: #3D5068; }
    .article-title { font-family: 'Syne', sans-serif; font-size: 1.08rem; font-weight: 700; color: #FFFFFF; line-height: 1.4; margin: 0.5rem 0 0.7rem; }
    .article-summary { font-family: 'Inter', sans-serif; font-size: 0.9rem; font-weight: 300; color: #8A9BB8; line-height: 1.75; margin-bottom: 1rem; }
    .read-link { font-family: 'Inter', sans-serif; font-size: 0.8rem; font-weight: 500; color: #00DCFF; text-decoration: none; border-bottom: 1px solid rgba(0,220,255,0.3); padding-bottom: 1px; }

    /* ── Briefing specific ── */
    .briefing-intro { font-family: 'Inter', sans-serif; font-size: 0.85rem; color: #3D5068; margin-bottom: 1.5rem; line-height: 1.6; }
    .briefing-timestamp { font-family: 'Inter', sans-serif; font-size: 0.72rem; letter-spacing: 0.1em; color: #3D5068; text-transform: uppercase; margin-bottom: 2rem; }
    .briefing-section { background: #0D1626; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.6rem 1.8rem; margin-bottom: 1rem; position: relative; }
    .briefing-section-label { font-family: 'Inter', sans-serif; font-size: 0.68rem; font-weight: 500; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 0.8rem; }
    .briefing-section-title { font-family: 'Syne', sans-serif; font-size: 1.1rem; font-weight: 700; color: #FFFFFF; margin-bottom: 0.8rem; }
    .briefing-section-body { font-family: 'Inter', sans-serif; font-size: 0.92rem; font-weight: 300; color: #8A9BB8; line-height: 1.8; }
    .briefing-section.happened::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #00DCFF; border-radius: 12px 0 0 12px; }
    .briefing-section.watch::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #FFB400; border-radius: 12px 0 0 12px; }
    .briefing-section.predictions::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #B060FF; border-radius: 12px 0 0 12px; }
    .briefing-section.mood::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #00DC78; border-radius: 12px 0 0 12px; }
    .label-happened { color: #00DCFF; }
    .label-watch    { color: #FFB400; }
    .label-predict  { color: #B060FF; }
    .label-mood     { color: #00DC78; }

    /* Waitlist styles */
    .waitlist-card { background: #0D1626; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 1.4rem 1.6rem; margin-bottom: 0.8rem; position: relative; }
    .waitlist-card.pending::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #FFB400; border-radius: 12px 0 0 12px; }
    .waitlist-card.matched::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: #00DC78; border-radius: 12px 0 0 12px; }
    .waitlist-desc { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 600; color: #FFFFFF; margin-bottom: 0.5rem; }
    .waitlist-meta { font-family: 'Inter', sans-serif; font-size: 0.76rem; color: #3D5068; margin-bottom: 0.8rem; }
    .status-badge { display: inline-block; font-family: 'Inter', sans-serif; font-size: 0.68rem; font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; border-radius: 4px; padding: 0.15rem 0.55rem; margin-right: 0.5rem; }
    .status-pending { color: #FFB400; background: rgba(255,180,0,0.08); border: 1px solid rgba(255,180,0,0.25); }
    .status-matched { color: #00DC78; background: rgba(0,220,120,0.08); border: 1px solid rgba(0,220,120,0.25); }
    .match-item { background: rgba(0,220,255,0.04); border: 1px solid rgba(0,220,255,0.1); border-radius: 8px; padding: 0.8rem 1rem; margin-top: 0.6rem; }
    .match-score { font-family: 'Inter', sans-serif; font-size: 0.72rem; color: #00DCFF; margin-bottom: 0.3rem; }
    .match-title { font-family: 'Syne', sans-serif; font-size: 0.92rem; font-weight: 600; color: #E8EDF5; margin-bottom: 0.4rem; }
    .notify-banner { background: rgba(0,220,120,0.07); border: 1px solid rgba(0,220,120,0.25); border-radius: 10px; padding: 1rem 1.4rem; margin-bottom: 1.5rem; font-family: 'Inter', sans-serif; font-size: 0.9rem; color: #4DCFA0; }
    .empty-waitlist { text-align: center; padding: 3rem 1rem; color: #3D5068; font-family: 'Inter', sans-serif; font-size: 0.9rem; line-height: 1.7; }
    .keyword-chip { display: inline-block; font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #00DCFF; background: rgba(0,220,255,0.06); border: 1px solid rgba(0,220,255,0.15); border-radius: 4px; padding: 0.1rem 0.5rem; margin: 0.1rem; }
    .custom-pill { display: inline-block; font-family: 'Inter', sans-serif; font-size: 0.68rem; font-weight: 500; color: #00DCFF; background: rgba(0,220,255,0.06); border: 1px dashed rgba(0,220,255,0.3); border-radius: 4px; padding: 0.12rem 0.5rem; margin-left: 0.4rem; vertical-align: middle; }
    .msg-error { background: rgba(220,60,60,0.08); border: 1px solid rgba(220,60,60,0.3); border-radius: 8px; padding: 0.8rem 1.1rem; color: #E07070; font-family: 'Inter', sans-serif; font-size: 0.88rem; margin-top: 0.6rem; }
    .msg-success { background: rgba(0,220,120,0.07); border: 1px solid rgba(0,220,120,0.25); border-radius: 8px; padding: 0.8rem 1.1rem; color: #4DCFA0; font-family: 'Inter', sans-serif; font-size: 0.88rem; margin-top: 0.6rem; }
    .no-results { background: rgba(255,180,0,0.05); border: 1px solid rgba(255,180,0,0.2); border-radius: 10px; padding: 1rem 1.4rem; color: #C8A84B; font-family: 'Inter', sans-serif; font-size: 0.9rem; }
    .loading-note { font-family: 'Inter', sans-serif; font-size: 0.82rem; color: #3D5068; margin-top: 0.5rem; text-align: center; }
    .site-footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid rgba(255,255,255,0.04); font-family: 'Inter', sans-serif; font-size: 0.76rem; color: #2A3A50; text-align: center; letter-spacing: 0.04em; }
    .site-footer span { color: #00DCFF; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def get_cache_key(category, subcategory):
    return f"{category}||{subcategory}"

def render_articles(articles, subcategory):
    if not articles:
        st.markdown(f'<div class="no-results">⚠️ No articles found for <strong>{subcategory}</strong>. Try refreshing.</div>', unsafe_allow_html=True)
        return
    count = len(articles)
    st.markdown(f'<div class="results-header">{count} RESULT{"S" if count != 1 else ""} — {subcategory.upper()}</div>', unsafe_allow_html=True)
    for article in articles:
        title     = article.get("title", "Untitled")
        source    = article.get("source", "Unknown")
        published = article.get("published", "")
        summary   = article.get("summary", "No summary available.")
        link      = article.get("link", "#")
        date_html = f'<span class="date-tag">{published}</span>' if published else ""
        st.markdown(f"""
        <div class="article-card">
            <div><span class="source-tag">{source}</span>{date_html}</div>
            <div class="article-title">{title}</div>
            <div class="article-summary">{summary}</div>
            <a class="read-link" href="{link}" target="_blank">Read full article →</a>
        </div>""", unsafe_allow_html=True)

def load_articles(category, subcategory, query, max_arts):
    cache_key = get_cache_key(category, subcategory)
    if cache_key in st.session_state.article_cache:
        return st.session_state.article_cache[cache_key]
    with st.spinner(f"Loading **{subcategory}** news..."):
        articles = run_news_agent(topic=query, max_articles=max_arts)
    st.session_state.article_cache[cache_key] = articles
    return articles


# ─────────────────────────────────────────────
# MASTHEAD
# ─────────────────────────────────────────────
st.markdown("""
<div class="masthead">
    <div class="masthead-label">⚡ AI-Powered News Intelligence</div>
    <div class="masthead-title">PUL<span>SE</span></div>
    <p class="masthead-sub">Browse by category — filtered, summarised, and delivered.</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.new_matches:
    count = len(st.session_state.new_matches)
    descs = ", ".join(f'"{m["description"][:40]}"' for m in st.session_state.new_matches[:2])
    st.markdown(f'<div class="notify-banner">✓ {count} waitlist match{"es" if count > 1 else ""} found — {descs}. Check the <strong>Waitlist</strong> tab.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
category_names = list(CATEGORIES.keys())
pending_count  = len(get_pending_items())
waitlist_label = f"Waitlist ({pending_count})" if pending_count > 0 else "Waitlist"
all_tab_names  = ["Briefing"] + category_names + [waitlist_label]
tabs           = st.tabs(all_tab_names)


# ── BRIEFING TAB ──
with tabs[0]:
    st.markdown("""
    <p class="briefing-intro">
        PULSE analyses recent headlines across politics, technology, business, and global affairs
        to produce a structured intelligence briefing — what happened, what's developing,
        what to expect, and the overall mood of the world right now.
    </p>
    """, unsafe_allow_html=True)

    generate_btn = st.button("⚡ Generate Today's Briefing", key="gen_briefing")

    if generate_btn:
        with st.spinner("Gathering headlines and generating your briefing..."):
            articles = fetch_briefing_articles()
            result   = generate_briefing(articles)
        st.session_state.briefing_result = result

    if st.session_state.briefing_result:
        result = st.session_state.briefing_result

        if not result["success"]:
            st.markdown(f'<div class="no-results">⚠️ {result["error"]}</div>', unsafe_allow_html=True)

        else:
            st.markdown(f'<div class="briefing-timestamp">Generated {result["generated_at"]}</div>', unsafe_allow_html=True)

            sections = result["sections"]

            # What Happened
            if sections.get("what_happened"):
                st.markdown(f"""
                <div class="briefing-section happened">
                    <div class="briefing-section-label label-happened">● What Happened</div>
                    <div class="briefing-section-title">Today's Key Events</div>
                    <div class="briefing-section-body">{sections["what_happened"].replace(chr(10), "<br>")}</div>
                </div>""", unsafe_allow_html=True)

            # What to Watch
            if sections.get("what_to_watch"):
                st.markdown(f"""
                <div class="briefing-section watch">
                    <div class="briefing-section-label label-watch">● What to Watch</div>
                    <div class="briefing-section-title">Developing in the Next 24–48hrs</div>
                    <div class="briefing-section-body">{sections["what_to_watch"].replace(chr(10), "<br>")}</div>
                </div>""", unsafe_allow_html=True)

            # Predictions
            if sections.get("predictions"):
                st.markdown(f"""
                <div class="briefing-section predictions">
                    <div class="briefing-section-label label-predict">● Predictions</div>
                    <div class="briefing-section-title">What's Likely Coming</div>
                    <div class="briefing-section-body">{sections["predictions"].replace(chr(10), "<br>")}</div>
                </div>""", unsafe_allow_html=True)

            # Global Mood
            if sections.get("global_mood"):
                st.markdown(f"""
                <div class="briefing-section mood">
                    <div class="briefing-section-label label-mood">● Global Mood</div>
                    <div class="briefing-section-title">The World Right Now</div>
                    <div class="briefing-section-body">{sections["global_mood"].replace(chr(10), "<br>")}</div>
                </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:3rem 1rem; color:#3D5068;
                    font-family:'Inter',sans-serif; font-size:0.9rem; line-height:1.7;">
            📋 Hit <strong style="color:#00DCFF">Generate Today's Briefing</strong> above
            to get your AI-powered intelligence report.
        </div>""", unsafe_allow_html=True)


# ── CATEGORY TABS ──
for tab, category in zip(tabs[1:-1], category_names):
    with tab:
        builtin_subs = CATEGORIES[category]["subcategories"]
        custom_subs  = st.session_state.custom_subcategories.get(category, {})
        all_subs     = {**builtin_subs, **custom_subs}
        sub_names    = list(all_subs.keys())

        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            selected_sub = st.selectbox("Subcategory", options=sub_names, key=f"sub_{category}", label_visibility="collapsed")
        with col2:
            max_arts = st.selectbox("Count", options=[3, 5, 10], index=1, key=f"count_{category}", label_visibility="collapsed")
        with col3:
            refresh = st.button("↻ Refresh", key=f"refresh_{category}")

        if selected_sub in custom_subs:
            st.markdown('<span class="custom-pill">✦ Custom</span>', unsafe_allow_html=True)

        with st.expander("＋ Add a custom subcategory"):
            new_sub_name  = st.text_input("Subcategory name", placeholder=f"e.g. a topic under {category}...", key=f"new_sub_name_{category}")
            new_sub_query = st.text_input("Search keyword", placeholder="e.g. blockchain...", key=f"new_sub_query_{category}")
            add_btn = st.button("Add subcategory", key=f"add_{category}")

            if st.session_state.validation_message and st.session_state.validation_message.get("category") == category:
                msg = st.session_state.validation_message
                css_class = "msg-success" if msg["valid"] else "msg-error"
                icon = "✓" if msg["valid"] else "✗"
                st.markdown(f'<div class="{css_class}">{icon} {msg["reason"]}</div>', unsafe_allow_html=True)

            if add_btn:
                if not new_sub_name.strip():
                    st.session_state.validation_message = {"category": category, "valid": False, "reason": "Please enter a subcategory name."}
                    st.rerun()
                elif not new_sub_query.strip():
                    st.session_state.validation_message = {"category": category, "valid": False, "reason": "Please enter a search keyword."}
                    st.rerun()
                else:
                    result = validate_subcategory(category, new_sub_name.strip())
                    if result["valid"]:
                        st.session_state.custom_subcategories[category][new_sub_name.strip()] = new_sub_query.strip()
                        st.session_state.validation_message = {"category": category, "valid": True, "reason": f"'{new_sub_name.strip()}' added to {category}."}
                    else:
                        st.session_state.validation_message = {"category": category, "valid": False, "reason": result["reason"]}
                    st.rerun()

        cache_key = get_cache_key(category, selected_sub)
        if refresh and cache_key in st.session_state.article_cache:
            del st.session_state.article_cache[cache_key]

        search_query = all_subs.get(selected_sub, selected_sub)
        articles = load_articles(category, selected_sub, search_query, max_arts)
        render_articles(articles, selected_sub)
        st.markdown('<div class="loading-note">Results cached per subcategory. Hit ↻ Refresh for the latest.</div>', unsafe_allow_html=True)


# ── WAITLIST TAB ──
with tabs[-1]:
    if st.session_state.new_matches:
        for matched in st.session_state.new_matches:
            st.markdown(f'<div class="notify-banner">✓ Match found for: <strong>"{matched["description"]}"</strong></div>', unsafe_allow_html=True)

    st.markdown('<div class="results-header">DESCRIBE THE NEWS YOU\'RE LOOKING FOR</div>', unsafe_allow_html=True)

    search_desc = st.text_input("Description", placeholder="e.g. UFC Fight Night Adesanya result, Trump Iran deal conclusion...", key="waitlist_search_desc", label_visibility="collapsed")
    search_btn  = st.button("🔍  Search Now", key="waitlist_search")

    if search_btn and search_desc.strip():
        keywords = extract_keywords(search_desc.strip())
        query    = " ".join(kw for kw, _ in keywords[:3])
        with st.spinner("Searching for matching articles..."):
            articles = get_all_articles(topic=query)
            matches  = find_best_matches(search_desc.strip(), articles, threshold=0.35)

        if matches:
            st.markdown(f'<div class="results-header">{len(matches)} MATCH{"ES" if len(matches) != 1 else ""} FOUND</div>', unsafe_allow_html=True)
            for article, score in matches[:5]:
                confidence = int(score * 100)
                st.markdown(f"""
                <div class="article-card">
                    <div><span class="source-tag">{article.get('source','Unknown')}</span><span class="date-tag">{article.get('published','')}</span></div>
                    <div class="article-title">{article.get('title','Untitled')}</div>
                    <div style="font-family:'Inter',sans-serif;font-size:0.82rem;color:#00DCFF;margin-bottom:0.8rem;">{confidence}% match confidence</div>
                    <a class="read-link" href="{article.get('link','#')}" target="_blank">Read full article →</a>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="no-results">⚠️ No matching articles found right now.</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Add to waitlist?** PULSE will check every 2 hours and notify you when this story breaks.")
            notify_email = st.text_input("Your email for notification", placeholder="you@gmail.com", key="waitlist_email")
            add_waitlist_btn = st.button("Add to Waitlist", key="add_waitlist_btn")

            if add_waitlist_btn:
                if not notify_email.strip() or "@" not in notify_email:
                    st.markdown('<div class="msg-error">✗ Please enter a valid email address.</div>', unsafe_allow_html=True)
                else:
                    result = add_to_waitlist(search_desc.strip(), notify_email.strip())
                    if result["success"]:
                        keywords = extract_keywords(search_desc.strip())
                        kw_html  = " ".join(f'<span class="keyword-chip">{kw}</span>' for kw, _ in keywords[:6])
                        st.markdown(f'<div class="msg-success">✓ Added to waitlist. We\'ll notify {notify_email} when a match is found.<br><div style="margin-top:8px;">Tracking: {kw_html}</div></div>', unsafe_allow_html=True)
                        st.rerun()
                    else:
                        st.markdown(f'<div class="msg-error">✗ {result["reason"]}</div>', unsafe_allow_html=True)

    pending = get_pending_items()
    matched = get_matched_items()

    if pending:
        st.markdown('<div class="results-header">MONITORING</div>', unsafe_allow_html=True)
        for item in pending:
            keywords    = extract_keywords(item["description"])
            kw_html     = " ".join(f'<span class="keyword-chip">{kw}</span>' for kw, _ in keywords[:5])
            last_checked = item.get("last_checked")
            checked_str  = f"Last checked: {last_checked[:16].replace('T',' ')}" if last_checked else "Not yet checked"
            st.markdown(f"""
            <div class="waitlist-card pending">
                <span class="status-badge status-pending">⏳ Monitoring</span>
                <div class="waitlist-desc">"{item['description']}"</div>
                <div class="waitlist-meta">Added {item['added_at'][:10]} &nbsp;·&nbsp; {checked_str} &nbsp;·&nbsp; Notify: {item['notify_email']}</div>
                <div>{kw_html}</div>
            </div>""", unsafe_allow_html=True)
            if st.button("Remove", key=f"remove_{item['id']}"):
                remove_from_waitlist(item["id"])
                st.rerun()

    if matched:
        st.markdown('<div class="results-header">MATCHED</div>', unsafe_allow_html=True)
        for item in matched:
            st.markdown(f"""
            <div class="waitlist-card matched">
                <span class="status-badge status-matched">✓ Matched</span>
                <div class="waitlist-desc">"{item['description']}"</div>
                <div class="waitlist-meta">Matched on {item.get('matched_at','')[:10]}</div>
            </div>""", unsafe_allow_html=True)
            for match in item.get("matches", []):
                confidence = int(match.get("score", 0) * 100)
                st.markdown(f"""
                <div class="match-item">
                    <div class="match-score">{confidence}% confidence &nbsp;·&nbsp; {match.get('source','')} &nbsp;·&nbsp; {match.get('published','')}</div>
                    <div class="match-title">{match.get('title','')}</div>
                    <a class="read-link" href="{match.get('link','#')}" target="_blank">Read article →</a>
                </div>""", unsafe_allow_html=True)
            if st.button("Dismiss", key=f"dismiss_{item['id']}"):
                remove_from_waitlist(item["id"])
                st.rerun()

    if not pending and not matched:
        st.markdown('<div class="empty-waitlist">📭 Your waitlist is empty.<br>Search for a story above — if no results are found<br>you can add it here and we\'ll monitor it for you.</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("""
<div class="site-footer">
    PULSE &nbsp;·&nbsp; LangChain &nbsp;·&nbsp; HuggingFace BART &nbsp;·&nbsp; Gemini &nbsp;·&nbsp; Streamlit
    &nbsp;·&nbsp; <span>Open Source</span>
</div>
""", unsafe_allow_html=True)