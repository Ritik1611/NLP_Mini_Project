import requests
from bs4 import BeautifulSoup
import pandas as pd
import random, time
import streamlit as st
from db import fetch_reviews, insert_reviews

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/129.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def fetch_amazon_reviews(url, brand, product, max_reviews=30):
    st.info(f"🔎 Scraping Amazon reviews for {brand} {product}...")
    reviews = []
    page = 1
    while len(reviews) < max_reviews:
        r = requests.get(f"{url}?pageNumber={page}", headers=HEADERS)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        blocks = soup.select("div.review")
        if not blocks: break
        for b in blocks:
            txt = b.select_one("span.review-text-content")
            if txt: reviews.append(txt.get_text(strip=True))
        page += 1
        time.sleep(random.uniform(1,2))
    return pd.DataFrame({"platform":["amazon"]*len(reviews),"brand":[brand]*len(reviews),
                         "product":[product]*len(reviews),"review":reviews})

def fetch_flipkart_reviews(url, brand, product, max_reviews=30):
    st.info(f"🔎 Scraping Flipkart reviews for {brand} {product}...")
    reviews = []
    page = 1
    while len(reviews) < max_reviews:
        r = requests.get(f"{url}&page={page}", headers=HEADERS)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        blocks = soup.select("div._27M-vq")
        if not blocks: break
        for b in blocks:
            txt = b.select_one("div.t-ZTKy > div")
            if txt: reviews.append(txt.get_text(strip=True))
        page += 1
        time.sleep(random.uniform(1,2))
    return pd.DataFrame({"platform":["flipkart"]*len(reviews),"brand":[brand]*len(reviews),
                         "product":[product]*len(reviews),"review":reviews})

def scrape_reviews(sources, max_reviews=30):
    all_data = []
    for s in sources:
        # First check DB cache
        cached = fetch_reviews(s["brand"], s["product"])
        if not cached.empty:
            st.success(f"✅ Loaded cached reviews for {s['brand']} {s['product']}")
            all_data.append(cached)
            continue

        if s["platform"].lower()=="amazon":
            df = fetch_amazon_reviews(s["url"], s["brand"], s["product"], max_reviews)
        elif s["platform"].lower()=="flipkart":
            df = fetch_flipkart_reviews(s["url"], s["brand"], s["product"], max_reviews)
        else:
            raise ValueError(f"Unsupported platform: {s['platform']}")

        if not df.empty:
            insert_reviews(df)
            st.success(f"💾 Stored {len(df)} reviews for {s['brand']} in DB")
            all_data.append(df)
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
