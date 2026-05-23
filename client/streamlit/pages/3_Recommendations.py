from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import render_error, render_recommendation_card, safe_json_view


st.set_page_config(page_title="Recommendations", page_icon="iR", layout="wide")
st.title("Recommendations")

user_id = st.text_input("User ID", value=st.session_state.get("selected_user_id", ""))
category = st.text_input("Category", value=st.session_state.get("category", "All_Beauty"))
request_text = st.text_area("Request", value="I want something affordable and gentle")
limit = st.slider("Limit", min_value=1, max_value=10, value=5)
session_id = st.text_input("Session ID (optional)", value="")

if st.button("Generate recommendations", type="primary"):
    if not user_id:
        st.warning("User ID is required for personalised recommendations. Use Cold Start for request-only demos.")
    else:
        payload = {
            "user_id": user_id,
            "category": category,
            "request": request_text,
            "limit": limit,
            "session_id": session_id or None,
            "context": {},
        }
        try:
            result = api_client.generate_recommendations(payload)
            st.session_state["latest_recommendations"] = result
        except Exception as exc:
            render_error(exc)

result = st.session_state.get("latest_recommendations")
if result:
    st.subheader("Intent")
    st.json(result.get("intent") or {})
    st.subheader("Recommendations")
    for item in result.get("recommendations") or []:
        render_recommendation_card(item)
    safe_json_view("Raw recommendation output", result)
