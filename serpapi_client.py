# serpapi_client.py
from serpapi import GoogleSearch
from typing import List, Dict
import os
import time
import random
import requests
from bs4 import BeautifulSoup

# Use the environment variable SERPAPI_API_KEY
SERPAPI_KEY = os.environ.get("SERPAPI_API_KEY")
if not SERPAPI_KEY:
    raise RuntimeError("SERPAPI_API_KEY environment variable is not set. Get one at https://serpapi.com/")

# basic headers (used only when optionally fetching page content)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def serpapi_search(query: str, engine: str = "google", num: int = 10, country: str = "in") -> Dict:
    """Run a SerpAPI search and return JSON results."""
    params = {
        "engine": engine,
        "q": query,
        "hl": "en",
        "gl": country,
        "api_key": SERPAPI_KEY,
        "num": num
    }
    search = GoogleSearch(params)
    return search.get_dict()


def extract_snippets_from_results(results: Dict) -> List[Dict]:
    """Collect (title, snippet, link) from organic_results."""
    items = []
    for r in results.get("organic_results", []):
        title = r.get("title")
        snippet = r.get("snippet") or r.get("rich_snippet", {}).get("top", {}).get("query_preview") or ""
        link = r.get("link")
        items.append({"title": title, "snippet": snippet, "link": link})
    return items


def get_reviews_for_brand(product_name: str, brand: str, max_snippets: int = 30) -> List[Dict]:
    """
    Query SerpAPI for product+brand reviews across Amazon/Flipkart (and generic sites).
    Returns list of dicts: {brand, product, source, snippet, title, link, fetched_at}
    """
    # Construct queries focusing on amazon.in / flipkart.com first but also general reviews
    queries = [
        f"{product_name} {brand} reviews site:amazon.in",
        f"{product_name} {brand} reviews site:flipkart.com",
        f"{product_name} {brand} reviews"
    ]
    collected = []
    seen_links = set()

    for q in queries:
        try:
            res = serpapi_search(q, num=10)
        except Exception as e:
            # don't fail the whole flow on transient SerpAPI errors
            print(f"[serpapi] error for query '{q}': {e}")
            continue

        items = extract_snippets_from_results(res)
        for it in items:
            link = it.get("link")
            if link in seen_links:
                continue
            seen_links.add(link)
            source = "snippet"
            snippet_text = it.get("snippet") or ""
            title = it.get("title") or ""
            collected.append({
                "brand": brand,
                "product": product_name,
                "source": source,
                "snippet": snippet_text,
                "title": title,
                "link": link,
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            if len(collected) >= max_snippets:
                break
        if len(collected) >= max_snippets:
            break
        time.sleep(random.uniform(0.5, 1.2))  # polite pacing

    return collected


def try_fetch_full_text_from_link(link: str) -> str:
    """
    Optional helper: attempt to download a page and extract a larger review text.
    Use with caution (sites may block). This is not required; snippets often suffice.
    """
    try:
        r = requests.get(link, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")

        # Try typical Amazon selectors
        if "amazon." in link:
            blocks = soup.select("div.review-text-content span")
            if blocks:
                return "\n".join([b.get_text(strip=True) for b in blocks])

        # Try typical Flipkart selectors
        if "flipkart." in link:
            blocks = soup.select("div._27M-vq div.t-ZTKy > div")
            if blocks:
                return "\n".join([b.get_text(strip=True) for b in blocks])

        # fallback: body text snippet
        body = soup.get_text(separator="\n", strip=True)
        return body[:2000]  # cropped
    except Exception:
        return ""
