from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import parse_json_or_text_input, render_error, render_rating_breakdown, safe_json_view


PERSONA_SAMPLE = {
    "likes": ["hydrating skincare", "gentle products"],
    "dislikes": ["strong fragrance", "greasy texture"],
    "budget": "medium",
    "tone": "casual",
    "average_rating": 4.2,
    "concerns": ["dry skin", "sensitivity"],
}

PRODUCT_SAMPLE = {
    "name": "Gentle Hydrating Face Cream",
    "category": "Skincare",
    "price": 18.99,
    "rating": 4.5,
    "reviews_count": 120,
    "features": ["fragrance-free", "hydrating", "for dry sensitive skin"],
    "description": "A lightweight moisturizing cream for dry and sensitive skin.",
}


st.set_page_config(page_title="Review Simulation", page_icon="iR", layout="wide")
st.title("Review Simulation")

mode = st.radio("Mode", ["Existing user", "Custom input"], horizontal=True)

if mode == "Existing user":
    user_id = st.text_input("User ID", value=st.session_state.get("selected_user_id", ""))
    category = st.selectbox(
        "Category",
        api_client.CATEGORIES,
        index=api_client.CATEGORIES.index(st.session_state.get("category", api_client.DEFAULT_CATEGORY))
        if st.session_state.get("category") in api_client.CATEGORIES
        else 0,
    )
    product_limit = st.number_input("Unseen product limit", min_value=1, max_value=100, value=20)

    if st.button("Load unseen products"):
        if not user_id:
            st.warning("Enter or select a user first.")
        else:
            try:
                products = api_client.get_unseen_products(user_id, limit=int(product_limit))
                st.session_state["unseen_products"] = products
            except Exception as exc:
                render_error(exc)

    products = st.session_state.get("unseen_products", [])
    product_map = {
        f"{product.get('title') or 'Untitled'} ({product.get('parent_asin')})": product
        for product in products
    }
    selected_label = st.selectbox("Product", list(product_map.keys())) if product_map else None

    if st.button("Run simulation", type="primary"):
        if not user_id:
            st.warning("User ID is required.")
        elif not selected_label:
            st.warning("Load and select an unseen product first.")
        else:
            product = product_map[selected_label]
            payload = {
                "user_id": user_id,
                "category": category,
                "parent_asin": product["parent_asin"],
                "context": {},
            }
            try:
                st.session_state["latest_simulation"] = api_client.simulate_review(payload)
            except Exception as exc:
                render_error(exc)
else:
    st.caption(
        "Custom persona/product input can be JSON or plain text. It will be validated by an LLM before use. "
        "Inputs like 'nothing', 'unknown', or 'hello world' will be rejected."
    )
    persona_text = st.text_area("Persona JSON or text", value=json.dumps(PERSONA_SAMPLE, indent=2), height=220)
    product_text = st.text_area("Product JSON or text", value=json.dumps(PRODUCT_SAMPLE, indent=2), height=240)

    if st.button("Run custom simulation", type="primary"):
        try:
            persona = parse_json_or_text_input("Persona input", persona_text)
            product = parse_json_or_text_input("Product input", product_text)
            parent_asin = product.get("parent_asin") if isinstance(product, dict) else None
            payload = {
                "user_id": None,
                "category": "Custom",
                "persona": persona,
                "product": product,
                "parent_asin": parent_asin or "custom_product",
                "context": {},
            }
            st.session_state["latest_simulation"] = api_client.simulate_review(payload)
        except Exception as exc:
            render_error(exc)

result = st.session_state.get("latest_simulation")
if result:
    st.subheader(result.get("product_title") or result.get("parent_asin"))
    cols = st.columns(3)
    cols[0].metric("Final rating", result.get("final_predicted_rating"))
    cols[1].metric("LLM rating", result.get("llm_predicted_rating"))
    cols[2].metric("Statistical rating", result.get("statistical_predicted_rating"))

    st.markdown(f"### {result.get('simulated_review_title') or 'Simulated review'}")
    st.write(result.get("simulated_review_text"))
    st.write("Reasoning:", result.get("reasoning_summary") or "n/a")
    evidence = result.get("evidence_used") or []
    if evidence:
        st.write("Evidence: " + ", ".join(str(item) for item in evidence))
    render_rating_breakdown(result.get("rating_breakdown"))
    safe_json_view("Raw simulation output", result)
