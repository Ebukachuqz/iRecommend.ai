from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import render_error, render_recommendation_card, safe_json_view


st.set_page_config(page_title="Cold Start", page_icon="iR", layout="wide")
st.title("Cold Start Recommendations")

request_text = st.text_area(
    "Request",
    value="I need affordable skincare for oily skin",
    height=100,
)
limit = st.slider("Limit", min_value=1, max_value=10, value=5)

if st.button("Run cold-start recommendation", type="primary"):
    if not request_text.strip():
        st.warning("Enter a request first.")
    else:
        try:
            result = api_client.cold_start_recommendations(
                {"request": request_text.strip(), "limit": limit, "context": {}}
            )
            st.session_state["latest_cold_start"] = result
        except Exception as exc:
            render_error(exc)

result = st.session_state.get("latest_cold_start")
if result:
    st.subheader("Intent")
    st.json(result.get("intent") or {})
    st.subheader("Recommendations")
    for item in result.get("recommendations") or []:
        render_recommendation_card(item)
    safe_json_view("Raw cold-start output", result)
