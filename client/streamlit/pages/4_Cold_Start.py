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
with st.expander("Optional onboarding answers", expanded=False):
    st.caption("These answers help create a low-confidence starter persona for cold-start recommendations.")
    interests_text = st.text_input("Product interests or categories", placeholder="skincare, electronics, books")
    priorities_text = st.text_input("Shopping priorities", placeholder="affordable, durable, simple, reliable")
    dislikes_text = st.text_input("Dislikes or things to avoid", placeholder="strong fragrance, flimsy build")
    strictness = st.selectbox("Rating strictness", ["", "strict", "moderate", "generous"], index=0)
    loved_examples_text = st.text_input("Products you loved and why", placeholder="optional")
    disliked_examples_text = st.text_input("Products you disliked and why", placeholder="optional")
limit = st.slider("Limit", min_value=1, max_value=10, value=5)


def comma_terms(value: str) -> list[str]:
    return [term.strip() for term in value.split(",") if term.strip()]


def onboarding_payload() -> dict:
    payload: dict = {}
    if comma_terms(interests_text):
        payload["interests"] = comma_terms(interests_text)
    if comma_terms(priorities_text):
        payload["priorities"] = comma_terms(priorities_text)
    if comma_terms(dislikes_text):
        payload["dislikes"] = comma_terms(dislikes_text)
    if strictness:
        payload["rating_strictness"] = strictness
    if loved_examples_text.strip():
        payload["loved_product_examples"] = [loved_examples_text.strip()]
    if disliked_examples_text.strip():
        payload["disliked_product_examples"] = [disliked_examples_text.strip()]
    return payload


if st.button("Run cold-start recommendation", type="primary"):
    if not request_text.strip():
        st.warning("Enter a request first.")
    else:
        try:
            answers = onboarding_payload()
            result = api_client.cold_start_recommendations(
                {
                    "request": request_text.strip(),
                    "limit": limit,
                    "onboarding_answers": answers or None,
                    "context": {},
                }
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
