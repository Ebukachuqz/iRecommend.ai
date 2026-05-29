from __future__ import annotations

import os

import streamlit as st

import api_client
from ui_helpers import render_error, render_status_badge, safe_json_view


st.set_page_config(page_title="iRecommend.ai", page_icon="iR", layout="wide")

# ---- Sidebar: API configuration ----
with st.sidebar:
    st.header("API")
    current_base_url = st.session_state.get("api_base_url", api_client.get_api_base_url())
    api_base_url = st.text_input("API base URL", value=current_base_url)
    if api_base_url:
        st.session_state["api_base_url"] = api_base_url.rstrip("/")
        os.environ["STREAMLIT_API_BASE_URL"] = st.session_state["api_base_url"]
    st.caption("Run the backend with `uvicorn app.api.main:app --reload`.")

# ---- Hero ----
st.title("iRecommend.ai")
st.caption("Behaviour-aware LLM agents for review simulation and personalised recommendation")

st.divider()

# ---- Task columns ----
task_a, task_b = st.columns(2)

with task_a:
    st.subheader(":memo: Task A: Review Simulation")
    st.write(
        "Predict a user's rating for an unseen product, generate a realistic review "
        "in their voice, and surface the calibration evidence behind the prediction."
    )

with task_b:
    st.subheader(":star: Task B: Recommendations")
    st.write(
        "Retrieve, score, rerank, and explain personalised product recommendations "
        "for returning users or cold-start visitors with no purchase history."
    )

st.divider()

# ---- API status ----
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
