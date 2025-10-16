# mistral_helper.py
import os
import time
import random
import streamlit as st
from mistralai import Mistral

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY")

if not MISTRAL_KEY:
    raise RuntimeError("MISTRAL_API_KEY environment variable not set.")

client = Mistral(api_key=MISTRAL_KEY)

def call_mistral_with_retry(prompt: str, retries: int = 5, base_wait: float = 5.0):
    """
    Calls Mistral API with retry + exponential backoff & jitter.
    Prevents 429 'capacity exceeded' errors.
    """
    for attempt in range(1, retries + 1):
        try:
            response = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if "429" in str(e) or "capacity" in str(e):
                wait = base_wait * attempt + random.uniform(0, 3)
                st.warning(f"⚠️ Mistral rate limit (attempt {attempt}/{retries}). Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            else:
                st.error(f"❌ Mistral API error: {e}")
                return ""
    st.error("🚫 Mistral failed after all retries.")
    return ""
