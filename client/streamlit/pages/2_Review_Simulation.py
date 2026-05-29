from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import (
    parse_json_or_text_input,
    render_error,
    render_simulation_result,
    render_user_selector,
)

st.set_page_config(page_title="Review Simulation", page_icon="📝", layout="wide")

st.title("Review Simulation")
st.caption("Task A: Simulate a realistic review and rating for a user-product pair.")

SAMPLE_PERSONA = json.dumps(
    {
        "likes": ["hydrating skincare", "gentle products"],
        "dislikes": ["strong fragrance", "greasy texture"],
        "budget": "medium",
        "tone": "casual",
        "average_rating": 4.2,
        "concerns": ["dry skin", "sensitivity"],
    },
    indent=4,
)

SAMPLE_PRODUCT = json.dumps(
    {
        "name": "Gentle Hydrating Face Cream",
        "category": "Skincare",
        "price": 18.99,
        "rating": 4.5,
        "reviews_count": 120,
        "features": ["fragrance-free", "hydrating", "for dry sensitive skin"],
        "description": "A lightweight moisturizing cream for dry and sensitive skin.",
    },
    indent=4,
)

# ---------------------------------------------------------------------------
# Mode selector
# ---------------------------------------------------------------------------
mode = st.radio(
    "Input mode",
    ["Select from Database", "Custom Input"],
    horizontal=True,
)

# ---------------------------------------------------------------------------
# Mode 1 -- Select from Database
# ---------------------------------------------------------------------------
if mode == "Select from Database":
    user_id, category, persona_row = render_user_selector(page_key="sim")

    st.subheader("Product")
    limit = st.number_input(
        "Max products to load",
        min_value=1,
        max_value=200,
        value=20,
        step=5,
        key="sim_product_limit",
    )

    if st.button("Load unseen products", key="sim_load_products"):
        if not user_id:
            render_error("Please select a user first.")
        else:
            with st.spinner("Fetching unseen products..."):
                try:
                    products = api_client.get_unseen_products(user_id, limit)
                    st.session_state["sim_products"] = products
                except Exception as exc:
                    render_error(f"Failed to load products: {exc}")

    products = st.session_state.get("sim_products", [])
    selected_product = None

    if products:
        product_options = {
            f"{p.get('title', 'Untitled')} ({p.get('parent_asin', 'N/A')})": p
            for p in products
        }
        chosen_label = st.selectbox(
            "Choose a product",
            list(product_options.keys()),
            key="sim_product_select",
        )
        selected_product = product_options.get(chosen_label)
    else:
        st.info("Click 'Load unseen products' to populate the product list.")

    if st.button("Run Simulation", type="primary", key="sim_run_db"):
        if not user_id:
            render_error("Please select a user first.")
        elif not selected_product:
            render_error("Please load and select a product first.")
        else:
            payload = {
                "user_id": user_id,
                "category": category,
                "parent_asin": selected_product.get("parent_asin", ""),
                "context": {},
            }
            with st.spinner("Running simulation..."):
                try:
                    result = api_client.simulate_review(payload)
                    st.session_state["sim_result"] = result
                except Exception as exc:
                    render_error(f"Simulation failed: {exc}")

# ---------------------------------------------------------------------------
# Mode 2 -- Custom Input
# ---------------------------------------------------------------------------
else:
    st.caption(
        "Paste any persona and product in JSON or text format. "
        "The backend normalises it."
    )

    persona_text = st.text_area(
        "Persona JSON",
        value=SAMPLE_PERSONA,
        height=220,
        key="sim_persona_text",
    )

    product_text = st.text_area(
        "Product JSON",
        value=SAMPLE_PRODUCT,
        height=220,
        key="sim_product_text",
    )

    if st.button("Run Simulation", type="primary", key="sim_run_custom"):
        try:
            persona = parse_json_or_text_input("Persona", persona_text)
            product = parse_json_or_text_input("Product", product_text)
            payload = {
                "persona": persona,
                "product": product,
                "parent_asin": "custom_product",
                "category": "Custom",
                "context": {},
            }
            with st.spinner("Running simulation..."):
                result = api_client.simulate_review(payload)
                st.session_state["sim_result"] = result
        except Exception as exc:
            render_error(exc)

# ---------------------------------------------------------------------------
# Display result (shared by both modes)
# ---------------------------------------------------------------------------
sim_result = st.session_state.get("sim_result")
if sim_result:
    st.divider()
    render_simulation_result(sim_result)
