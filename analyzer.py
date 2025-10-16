# analyzer.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import pandas as pd
import streamlit as st
import time
import random

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

@st.cache_resource
def load_pipeline(model_name=MODEL_NAME):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    device = 0 if torch.cuda.is_available() else -1
    pipe = pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=None, device=device)
    return pipe


def detect_and_return(df: pd.DataFrame, text_col: str = "snippet") -> pd.DataFrame:
    """Run sentiment model with retry and rate-limit handling."""
    pipe = load_pipeline()
    results = []
    texts = df[text_col].astype(str).tolist()
    st.info(f"⚡ Running model on {len(texts)} snippets...")

    for i, text in enumerate(texts):
        if not text.strip():
            label = "unknown"
        else:
            for attempt in range(3):
                try:
                    out = pipe(text[:512])
                    if isinstance(out, list) and isinstance(out[0], dict):
                        label = out[0]['label']
                    elif isinstance(out, list) and isinstance(out[0], list):
                        label = out[0][0]['label']
                    else:
                        label = "unknown"
                    break
                except Exception as e:
                    if "429" in str(e) or "capacity" in str(e):
                        wait = random.uniform(5, 10) * (attempt + 1)
                        st.warning(f"⏳ Rate limit hit (attempt {attempt+1}). Waiting {wait:.1f}s...")
                        time.sleep(wait)
                        continue
                    else:
                        st.error(f"Error during model run: {e}")
                        label = "error"
                        break
        results.append({"id": int(df.iloc[i].get('id', i)), "emotion": label})

    return pd.DataFrame(results)
