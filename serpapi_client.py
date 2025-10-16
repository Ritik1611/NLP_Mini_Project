# serpapi_client.py
from serpapi import GoogleSearch
from typing import List, Dict
import os
import time
import random
import requests
from bs4 import BeautifulSoup
import streamlit as st

# ---- CONFIG ----
SERPAPI_KEY = os.environ.get("SERPAPI_API_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_API_KEY environment variable is not set. Get one at https://serpapi.com/")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def serpapi_search(query: str, engine: str = "google", num: int = 10, country: str = "in", retries: int = 3) -> Dict:
    """Run a SerpAPI search with retry and backoff."""
    params = {
        "engine": engine,
        "q": query,
        "hl": "en",
        "gl": country,
        "api_key": SERPAPI_KEY,
        "num": num
    }

    for attempt in range(1, retries + 1):
        try:
            st.info(f"🔍 Fetching search results for: {query} (Attempt {attempt})")
            search = GoogleSearch(params)
            result = search.get_dict()
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception as e:
            wait_time = random.uniform(4, 8) * attempt
            st.warning(f"⚠️ SerpAPI error ({e}). Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    st.error("❌ Failed to fetch results after retries.")
    return {}

def extract_snippets_from_results(results: Dict) -> List[Dict]:
    items = []
    for r in results.get("organic_results", []):
        title = r.get("title", "")
        snippet = r.get("snippet") or r.get("rich_snippet", {}).get("top", {}).get("query_preview", "")
        link = r.get("link")
        if title or snippet:
            items.append({"title": title, "snippet": snippet, "link": link})
    return items

def get_reviews_for_brand(product_name: str, brand: str, max_snippets: int = 30) -> List[Dict]:
    """Fetch product reviews from Amazon + Flipkart."""
    queries = [
        f"{product_name} {brand} reviews site:amazon.in",
        f"{product_name} {brand} reviews site:flipkart.com",
        f"{product_name} {brand} reviews"
    ]

    collected, seen_links = [], set()

    for q in queries:
        res = serpapi_search(q)
        items = extract_snippets_from_results(res)
        for it in items:
            link = it.get("link")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            collected.append({
                "brand": brand,
                "product": product_name,
                "source": "snippet",
                "snippet": it.get("snippet", ""),
                "title": it.get("title", ""),
                "link": link,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            if len(collected) >= max_snippets:
                break
        if len(collected) >= max_snippets:
            break
        time.sleep(random.uniform(3, 6))
    st.success(f"✅ Collected {len(collected)} snippets for {brand}.")
    return collected

def try_fetch_full_text_from_link(link: str) -> str:
    """Fetch full review text if available."""
    try:
        r = requests.get(link, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        if "amazon." in link:
            blocks = soup.select("div.review-text-content span")
            if blocks:
                return "\n".join([b.get_text(strip=True) for b in blocks])
        if "flipkart." in link:
            blocks = soup.select("div._27M-vq div.t-ZTKy > div")
            if blocks:
                return "\n".join([b.get_text(strip=True) for b in blocks])
        return soup.get_text(separator="\n", strip=True)[:2000]
    except Exception:
        return ""
