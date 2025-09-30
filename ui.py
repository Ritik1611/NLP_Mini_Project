import altair as alt
import streamlit as st

def show_comparison_charts(df):
    counts = df.groupby(["brand","emotion"]).size().reset_index(name="count")
    chart = alt.Chart(counts).mark_bar().encode(
        x="brand:N", y="count:Q", color="emotion:N", column="emotion:N"
    ).properties(width=120, height=200)
    st.altair_chart(chart)

def export_csv(df):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "review_emotions.csv", "text/csv")
