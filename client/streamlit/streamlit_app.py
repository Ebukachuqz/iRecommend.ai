from __future__ import annotations

import os

import streamlit as st

import api_client
from ui_helpers import render_error, render_status_badge, safe_json_view


st.set_page_config(page_title="iRecommend", page_icon="iR", layout="wide")

st.title("iRecommend")
st.caption("Behaviour-aware LLM agents for review simulation and personalised recommendation")

with st.sidebar:
    st.header("API")
    current_base_url = st.session_state.get("api_base_url", api_client.get_api_base_url())
    api_base_url = st.text_input("API base URL", value=current_base_url)
    if api_base_url:
        st.session_state["api_base_url"] = api_base_url.rstrip("/")
        os.environ["STREAMLIT_API_BASE_URL"] = st.session_state["api_base_url"]
    st.caption("Run the backend with `uvicorn app.api.main:app --reload`.")

st.write(
    "iRecommend learns structured personas from review history, uses them to simulate future reviews, "
    "and generates personalised product recommendations with transparent evidence."
)

task_a, task_b = st.columns(2)
with task_a:
    st.subheader("Task A: Review Simulation")
    st.write("Predict a user's rating, generate a likely review, and show the calibration evidence.")

with task_b:
    st.subheader("Task B: Recommendations")
    st.write("Retrieve, score, rerank, and explain personalised recommendations for known or cold-start users.")

st.divider()
st.subheader("API Status")

health_col, ready_col = st.columns(2)
try:
    health = api_client.get_health()
    with health_col:
        render_status_badge("Health", health.get("status") == "ok")
        safe_json_view("Health response", health)
except Exception as exc:
    with health_col:
        render_error(exc)

try:
    ready = api_client.get_ready()
    with ready_col:
        render_status_badge("Readiness", ready.get("status") == "ready")
        safe_json_view("Readiness checks", ready)
except Exception as exc:
    with ready_col:
        render_error(exc)

st.divider()
st.subheader("Demo Flow")
st.write("1. Load a persona in **Persona Explorer**.")
st.write("2. Simulate a review in **Review Simulation**.")
st.write("3. Generate personalised recommendations in **Recommendations**.")
st.write("4. Try a request-only scenario in **Cold Start**.")
st.info("Use the sidebar page navigation to move through the demo.")
