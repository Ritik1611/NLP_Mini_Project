import altair as alt
import streamlit as st

def plot_emotion_distribution(df):
    chart = alt.Chart(df).mark_bar().encode(
        x="emotion",
        y="count()",
        color="emotion"
    )
    st.altair_chart(chart, use_container_width=True)

def plot_brand_comparison(df):
    chart = alt.Chart(df).mark_bar().encode(
        x="brand",
        y="count()",
        color="emotion"
    )
    st.altair_chart(chart, use_container_width=True)
