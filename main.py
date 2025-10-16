# main.py
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import pandas as pd
import altair as alt
import os
import time
import random
from mistralai import Mistral

from serpapi_client import get_reviews_for_brand
from db import init_db, insert_reviews, fetch_reviews, update_emotions_for_rows, clear_cache
from analyzer import detect_and_return

st.set_page_config(page_title="SerpAPI-driven Review Comparator", layout="wide")
st.title("🔎 Product Review Comparison via SerpAPI (Amazon/Flipkart)")

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

if not SERPAPI_API_KEY:
    st.error("🚨 Missing SERPAPI_API_KEY")
if MISTRAL_API_KEY:
    mistral_client = Mistral(api_key=MISTRAL_API_KEY)

init_db()

# --- Sidebar ---
st.sidebar.header("Search options")
product_name = st.sidebar.text_input("Product name", "headphones")
brands_input = st.sidebar.text_input("Brands (comma separated)", "")
num_snippets = st.sidebar.slider("Max snippets per brand", 5, 100, 30)
use_fulltext = st.sidebar.checkbox("Fetch full review pages", False)

if st.sidebar.button("Clear DB cache"):
    clear_cache()
    st.success("✅ Database reset!")

# --- Helper: LLM check ---
def is_word_a_brand_llm(word: str, product_context: str) -> bool:
    if not MISTRAL_API_KEY:
        return False
    for attempt in range(3):
        try:
            resp = mistral_client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": f"In the context of {product_context}, is '{word}' a brand? yes or no"}],
            )
            ans = resp.choices[0].message.content.strip().lower()
            return "yes" in ans
        except Exception as e:
            if "429" in str(e) or "capacity" in str(e):
                wait = random.uniform(5, 10) * (attempt + 1)
                st.warning(f"LLM rate limit hit. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            st.error(f"LLM check error: {e}")
            return False
    return False

def infer_brands_from_serp(product, top_k=5):
    from serpapi_client import serpapi_search, extract_snippets_from_results
    st.info("🔎 Inferring brands from search results...")
    try:
        res = serpapi_search(f"{product} brands reviews", num=20)
        items = extract_snippets_from_results(res)
    except Exception as e:
        st.error(f"Error fetching search results: {e}")
        return []

    ignore = {"the","best","and","for","of","in","review","reviews","guide","headphones","earbuds"}
    tokens = {}
    for it in items:
        txt = (it.get("title") or "") + " " + (it.get("snippet") or "")
        for w in txt.split():
            w = w.strip('.,!?:;()[]{}')
            if w.istitle() and len(w) > 2 and w.lower() not in ignore:
                tokens[w] = tokens.get(w, 0) + 1

    candidates = [t for t, _ in sorted(tokens.items(), key=lambda x: x[1], reverse=True)[:15]]
    st.info(f"Candidates: {candidates}")

    confirmed = []
    for c in candidates:
        if is_word_a_brand_llm(c, product):
            confirmed.append(c)
            if len(confirmed) >= top_k:
                break
    return confirmed

# --- Main Action ---
if st.sidebar.button("Run Analysis"):
    if not product_name.strip():
        st.error("Enter a product name!")
        st.stop()

    if brands_input.strip():
        brands = [b.strip() for b in brands_input.split(",") if b.strip()]
    else:
        brands = infer_brands_from_serp(product_name)

    if not brands:
        st.warning("No brands detected.")
        st.stop()

    st.success(f"✅ Running analysis for brands: {brands}")

    for brand in brands:
        cached = fetch_reviews(brand, product_name)
        if not cached.empty:
            st.info(f"Using {len(cached)} cached reviews for {brand}")
            continue

        recs = get_reviews_for_brand(product_name, brand, max_snippets=num_snippets)
        if use_fulltext:
            from serpapi_client import try_fetch_full_text_from_link
            for r in recs:
                if r.get("link"):
                    full = try_fetch_full_text_from_link(r["link"])
                    if full:
                        r["snippet"] = full
        insert_reviews(recs)

    dfs = [fetch_reviews(b, product_name) for b in brands]
    df_all = pd.concat(dfs, ignore_index=True)
    st.dataframe(df_all.drop(columns=["emotion"], errors="ignore"))

    if df_all.empty:
        st.warning("No data to analyze.")
        st.stop()

    missing = df_all[df_all["emotion"].isnull()]
    if not missing.empty:
        updates = detect_and_return(missing)
        update_emotions_for_rows(updates)
        st.success("✅ Sentiment predictions updated!")

    df_all = pd.concat([fetch_reviews(b, product_name) for b in brands], ignore_index=True)
    st.subheader("Sentiment Distribution")
    counts = df_all.groupby(["brand", "emotion"]).size().reset_index(name="count")

    chart = alt.Chart(counts).mark_bar().encode(
        x="brand:N", y="count:Q", color="emotion:N", tooltip=["brand", "emotion", "count"]
    )
    st.altair_chart(chart, use_container_width=True)

    st.download_button(
        "📥 Download CSV",
        df_all.to_csv(index=False).encode("utf-8"),
        "analyzed_reviews.csv",
        "text/csv",
    )
    st.balloons()
