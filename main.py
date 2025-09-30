# main.py
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import altair as alt
import os

from mistralai import Mistral  # use new client

# --- Local Imports ---
from serpapi_client import get_reviews_for_brand
from db import init_db, insert_reviews, fetch_reviews, update_emotions_for_rows, clear_cache
from analyzer import detect_and_return

# --- PAGE CONFIG ---
st.set_page_config(page_title="SerpAPI-driven Review Comparator", layout="wide")
st.title("🔎 Product Review Comparison via SerpAPI (Amazon/Flipkart)")

# --- API KEY SETUP ---
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

MISTRAL_API_CONFIGURED = bool(MISTRAL_API_KEY)
SERPAPI_API_CONFIGURED = bool(SERPAPI_API_KEY)

if MISTRAL_API_CONFIGURED:
    mistral_client = Mistral(api_key=MISTRAL_API_KEY)

# --- DATABASE ---
init_db()

# --- SIDEBAR INPUTS ---
st.sidebar.header("Search options")
product_name = st.sidebar.text_input("Product name (required)", value="headphones")
brands_input = st.sidebar.text_input("Optional: comma-separated brands (leave empty to infer)", value="")
num_snippets = st.sidebar.slider("Max snippets per brand", 5, 100, 30)
use_fulltext = st.sidebar.checkbox("Attempt to fetch full review pages (slower)", value=False)

st.sidebar.markdown("""
### Required Environment Variables
- `SERPAPI_API_KEY` (for fetching reviews)
- `MISTRAL_API_KEY` (for brand inference & sentiment LLM)
""")

if st.sidebar.button("Clear DB cache"):
    clear_cache()
    st.success("DB cache cleared and schema reset.")


# --- CORE LOGIC ---

@st.cache_data(show_spinner=False)
def is_word_a_brand_llm(word: str, product_context: str) -> bool:
    """Use Mistral LLM (new client) to check if a token is a brand name."""
    if not MISTRAL_API_CONFIGURED:
        st.error("Mistral API is not configured. Please set MISTRAL_API_KEY.")
        return False

    try:
        model_name = "mistral-large-latest"  # or whichever model you prefer
        prompt = f"In the context of {product_context}, is the word '{word}' a brand name? Answer with only 'yes' or 'no'."

        messages = [{"role": "user", "content": prompt}]

        # Use the new API: .chat.complete(...)
        resp = mistral_client.chat.complete(model=model_name, messages=messages)
        # The response format: resp.choices[0].message.content
        answer = resp.choices[0].message.content.strip().lower()
        return 'yes' in answer

    except Exception as e:
        st.error(f"Error during Mistral LLM verification for '{word}': {e}")
        return False


def infer_brands_from_serp(product, top_k=5):
    """Try to infer brand names automatically using SerpAPI + LLM filtering."""
    if not SERPAPI_API_CONFIGURED:
        st.error("SerpAPI is not configured. Please set SERPAPI_API_KEY.")
        return []

    st.info("🔎 Inferring brands from search results...")
    from serpapi_client import serpapi_search, extract_snippets_from_results

    try:
        res = serpapi_search(f"{product} reviews", num=20)
        items = extract_snippets_from_results(res)
    except Exception as e:
        st.error(f"Error fetching initial SerpAPI results: {e}")
        return []

    stop_words = {
        'the', 'best', 'review', 'reviews', 'for', 'and', 'with', 'top', 'new', 'guide', 'bluetooth',
        'wireless', 'wired', 'headphone', 'headphones', 'earbuds', 'earphone', 'earphones', 'audio',
        'sound', 'bass', 'noise', 'cancelling', 'tested', 'pro', 'plus', 'ultra', 'max', 'edition'
    }
    product_words = set(product.lower().split())
    ignore_words = product_words.union(stop_words)

    tokens = {}
    for it in items:
        txt = (it.get("title") or "") + " " + (it.get("snippet") or "")
        for w in txt.split():
            cleaned = w.strip('.,!?:;()[]{}')
            if cleaned.istitle() and len(cleaned) > 2 and cleaned.lower() not in ignore_words:
                tokens[cleaned] = tokens.get(cleaned, 0) + 1

    candidate_tokens = [t for t, _ in sorted(tokens.items(), key=lambda x: x[1], reverse=True)[:15]]
    st.info(f"Generated candidates: {candidate_tokens}. Now verifying with LLM...")

    confirmed_brands = []
    for candidate in candidate_tokens:
        with st.spinner(f"🤖 Verifying '{candidate}'..."):
            if is_word_a_brand_llm(candidate, product):
                confirmed_brands.append(candidate)
                if len(confirmed_brands) >= top_k:
                    break

    return confirmed_brands


# --- MAIN APP FLOW ---
if st.sidebar.button("Run Analysis"):
    if not SERPAPI_API_CONFIGURED:
        st.error("🚨 Missing SERPAPI_API_KEY. Please set it in your environment.")
        st.stop()

    if not product_name.strip():
        st.error("Please enter a product name.")
        st.stop()

    with st.spinner("Inferring brands... This may take a moment."):
        if brands_input.strip():
            brands = [b.strip() for b in brands_input.split(",") if b.strip()]
        else:
            if not MISTRAL_API_CONFIGURED:
                st.error("Cannot infer brands. MISTRAL_API_KEY is not set.", icon="🚨")
                st.stop()
            brands = infer_brands_from_serp(product_name, top_k=5)

    if not brands:
        st.warning("⚠️ Could not determine any brands. Please provide brands manually in the sidebar.")
        st.stop()

    st.success(f"✅ Analysis will run for brands: **{brands}**")

    for brand in brands:
        cached = fetch_reviews(brand, product_name)
        if not cached.empty:
            st.success(f"Found {len(cached)} cached reviews for **{brand}**.")
            continue

        st.info(f"Fetching snippets for **{brand}**...")
        try:
            recs = get_reviews_for_brand(product_name, brand, max_snippets=num_snippets)
        except Exception as e:
            st.error(f"Error fetching reviews for {brand}: {e}")
            continue

        if use_fulltext:
            from serpapi_client import try_fetch_full_text_from_link
            for r in recs:
                full = try_fetch_full_text_from_link(r.get('link', "")) if r.get('link') else ""
                if full:
                    r['snippet'] = full

        if recs:
            insert_reviews(recs)
            st.success(f"Stored {len(recs)} new reviews for **{brand}**.")
        else:
            st.warning(f"No new snippets found for **{brand}**.")

    dfs = [fetch_reviews(b, product_name) for b in brands]
    df_all = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    if df_all.empty:
        st.warning("⚠️ No reviews available for analysis.")
        st.stop()

    st.subheader("Collected Review Snippets")
    st.dataframe(df_all.drop(columns=['emotion'], errors='ignore'))

    if 'emotion' not in df_all.columns or df_all['emotion'].isnull().any():
        rows_to_analyze = df_all[df_all['emotion'].isnull()]
        updates_df = detect_and_return(rows_to_analyze)
        update_emotions_for_rows(updates_df)
        st.success("✅ Updated DB with sentiment predictions.")
        dfs = [fetch_reviews(b, product_name) for b in brands]
        df_all = pd.concat(dfs, ignore_index=True)
    else:
        st.success("Sentiment analysis already complete for this dataset.")

    st.subheader("Sentiment Distribution by Brand")
    counts = df_all.groupby(["brand", "emotion"]).size().reset_index(name="count")
    if not counts.empty:
        chart = alt.Chart(counts).mark_bar().encode(
            x=alt.X("brand:N", title="Brand"),
            y=alt.Y("count:Q", title="Review Count"),
            color="emotion:N",
            tooltip=["brand", "emotion", "count"]
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No sentiment data available to plot.")

    csv = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Analyzed CSV", data=csv, file_name="analyzed_reviews.csv", mime="text/csv")

    st.balloons()
    st.success("🎉 Done!")
