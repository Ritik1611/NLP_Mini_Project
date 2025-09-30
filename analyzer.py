# analyzer.py
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import pandas as pd
import streamlit as st

# Select model: emotion vs sentiment
# MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-emotion"
MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"  # faster/multilingual sentiment

@st.cache_resource
def load_pipeline(model_name=MODEL_NAME):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    device = 0 if torch.cuda.is_available() else -1
    pipe = pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=None, device=device)
    return pipe

def detect_and_return(df: pd.DataFrame, text_col: str = "snippet") -> pd.DataFrame:
    """
    df: DataFrame containing at least 'id' (if saved to DB) and 'snippet' column.
    Returns DataFrame with columns 'id' and 'emotion' (or sentiment label).
    """
    pipe = load_pipeline()
    results = []
    texts = df[text_col].astype(str).tolist()
    st.info(f"⚡ Running model on {len(texts)} snippets...")
    # pipeline returns list of dicts
    for i, text in enumerate(texts):
        if not text.strip():
            label = "unknown"
        else:
            out = pipe(text[:512])  # limit length
            # out might be list of dicts. We pick top scoring label:
            if isinstance(out, list) and isinstance(out[0], dict):
                label = out[0]['label']
            elif isinstance(out, list) and isinstance(out[0], list):
                label = out[0][0]['label']
            else:
                label = "unknown"
        results.append({"id": int(df.iloc[i]['id']), "emotion": label})
    return pd.DataFrame(results)
