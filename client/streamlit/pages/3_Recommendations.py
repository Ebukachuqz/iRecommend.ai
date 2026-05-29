from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import parse_json_or_text_input, render_error, render_recommendation_card, safe_json_view


PERSONA_SAMPLE = {
    "likes": ["hydrating skincare", "gentle products"],
    "dislikes": ["strong fragrance", "greasy texture"],
    "budget": "medium",
    "tone": "casual",
    "average_rating": 4.2,
    "concerns": ["dry skin", "sensitivity"],
}


st.set_page_config(page_title="Recommendations", page_icon="iR", layout="wide")
st.title("Recommendations")

mode = st.radio("Mode", ["Existing user", "Custom persona"], horizontal=True)
category = st.selectbox(
    "Category",
    api_client.CATEGORIES,
    index=api_client.CATEGORIES.index(st.session_state.get("category", api_client.DEFAULT_CATEGORY))
    if st.session_state.get("category") in api_client.CATEGORIES
    else 0,
)
request_text = st.text_area("Request", value="I want something affordable and gentle")
limit = st.slider("Limit", min_value=1, max_value=10, value=5)

if mode == "Existing user":
    user_id = st.text_input("User ID", value=st.session_state.get("selected_user_id", ""))
    session_id = st.text_input("Session ID (optional)", value="")

    if st.button("Generate recommendations", type="primary"):
        if not user_id:
            st.warning("User ID is required for personalised recommendations. Switch to Custom persona or Cold Start for request-only demos.")
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
                st.session_state["latest_recommendations"] = api_client.generate_recommendations(payload)
            except Exception as exc:
                render_error(exc)
else:
    st.caption(
        "Custom persona input can be JSON or plain text. It will be validated by an LLM before use. "
        "Inputs like 'nothing', 'unknown', or 'hello world' will be rejected."
    )
    persona_text = st.text_area("Persona JSON or text", value=json.dumps(PERSONA_SAMPLE, indent=2), height=240)

    if st.button("Generate recommendations from persona", type="primary"):
        try:
            persona = parse_json_or_text_input("Persona input", persona_text)
            payload = {
                "category": category,
                "persona": persona,
                "request": request_text,
                "limit": limit,
                "context": {},
            }
            st.session_state["latest_recommendations"] = api_client.generate_recommendations(payload)
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
