from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import format_score, get_persona_average_rating, render_error, render_persona_section, safe_json_view


st.set_page_config(page_title="Persona Explorer", page_icon="iR", layout="wide")
st.title("Persona Explorer")

category = st.text_input("Category", value=st.session_state.get("category", api_client.DEFAULT_CATEGORY))
limit = st.number_input("User limit", min_value=1, max_value=100, value=20)

if st.button("Load users", type="primary"):
    try:
        users = api_client.list_users(category=category, limit=int(limit))
        st.session_state["users"] = users
        st.session_state["category"] = category
    except Exception as exc:
        render_error(exc)

users = st.session_state.get("users", [])
if users:
    user_options = [row["user_id"] for row in users]
    default_user = st.session_state.get("selected_user_id")
    index = user_options.index(default_user) if default_user in user_options else 0
    selected_user = st.selectbox("User", user_options, index=index)
    st.session_state["selected_user_id"] = selected_user

    selected_summary = next((row for row in users if row["user_id"] == selected_user), {})
    summary_cols = st.columns(3)
    summary_cols[0].metric("Review count", selected_summary.get("review_count") or 0)
    summary_cols[1].metric("Average rating", format_score(get_persona_average_rating(selected_summary)))
    summary_cols[2].metric("Persona version", selected_summary.get("persona_version") or "n/a")

    if st.button("Load persona"):
        try:
            persona_row = api_client.get_persona(selected_user, category=category)
            st.session_state["persona_row"] = persona_row
        except Exception as exc:
            render_error(exc)

persona_row = st.session_state.get("persona_row")
if persona_row:
    persona = persona_row.get("persona") or {}
    st.subheader("Persona Summary")
    cols = st.columns(4)
    cols[0].metric("Review count", persona_row.get("review_count") or 0)
    cols[1].metric("Average rating", format_score(get_persona_average_rating(persona_row)))
    cols[2].metric("Source reviews", len(persona_row.get("source_review_ids") or []))
    cols[3].metric("Version", persona_row.get("persona_version") or "n/a")

    render_persona_section("Writing style", persona, "writing_style")
    render_persona_section("Preferences", persona, "preferences")
    render_persona_section("Rating behavior", persona, "rating_behavior")
    render_persona_section("Purchase behavior", persona, "purchase_behavior")
    render_persona_section("Cultural signals", persona, "cultural_signals")
    render_persona_section("Evidence", persona, "evidence")
    safe_json_view("Raw persona row", persona_row)
elif not users:
    st.info("Load users to begin.")
