from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import streamlit as st

STREAMLIT_ROOT = Path(__file__).resolve().parents[1]
if str(STREAMLIT_ROOT) not in sys.path:
    sys.path.insert(0, str(STREAMLIT_ROOT))

import api_client
from ui_helpers import (
    ensure_backend_ready,
    parse_json_or_text_input,
    render_error,
    render_recommendation_results,
    render_user_selector,
    safe_json_view,
)


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
ensure_backend_ready()

# ── Mode selector ──────────────────────────────────────────────────────────
mode = st.radio(
    "Input mode",
    ["Select from Database", "Custom Persona", "No Persona (Cold Start)"],
    horizontal=True,
)

# ── Shared state defaults ──────────────────────────────────────────────────
if "rec_messages" not in st.session_state:
    st.session_state["rec_messages"] = []
if "rec_session_id" not in st.session_state:
    st.session_state["rec_session_id"] = str(uuid.uuid4())

limit = st.slider("Max recommendations", min_value=1, max_value=10, value=5)


def reset_chat() -> None:
    st.session_state["rec_messages"] = []
    st.session_state["rec_session_id"] = str(uuid.uuid4())
    st.session_state.pop("rec_persona_row", None)
    st.session_state.pop("rec_custom_persona", None)


def add_message(role: str, content: str | dict) -> None:
    st.session_state["rec_messages"].append({"role": role, "content": content})


def display_chat_history() -> None:
    for msg in st.session_state["rec_messages"]:
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if isinstance(content, dict):
                render_recommendation_results(content)
            else:
                st.write(content)


# ── Mode 1: Select from Database ──────────────────────────────────────────
if mode == "Select from Database":
    with st.expander("Select a user", expanded=True):
        user_id, category, persona_row = render_user_selector("rec")

    if user_id and persona_row:
        st.success(f"Persona loaded for **{user_id}** in {category}.")

        col_new, col_just = st.columns([1, 1])
        with col_new:
            if st.button("New conversation", key="rec_new_conv"):
                reset_chat()
                st.rerun()
        with col_just:
            if st.button("Just Recommend", type="primary", key="rec_just_recommend"):
                add_message("user", "Recommend products based on my preferences.")
                try:
                    with st.spinner("Generating recommendations..."):
                        result = api_client.generate_recommendations({
                            "user_id": user_id,
                            "category": category,
                            "request": None,
                            "limit": limit,
                            "session_id": st.session_state["rec_session_id"],
                            "context": {},
                        })
                    add_message("assistant", result)
                except Exception as exc:
                    add_message("assistant", f"Error: {exc}")
                st.rerun()

        display_chat_history()

        if prompt := st.chat_input("Ask for recommendations or refine..."):
            add_message("user", prompt)
            try:
                with st.spinner("Generating recommendations..."):
                    result = api_client.session_message(
                        st.session_state["rec_session_id"],
                        {
                            "user_id": user_id,
                            "category": category,
                            "message": prompt,
                            "limit": limit,
                        },
                    )
                add_message("assistant", result)
            except Exception as exc:
                add_message("assistant", f"Error: {exc}")
            st.rerun()

    elif user_id:
        st.info("Click **Load persona** to activate recommendations.")
    # else: render_user_selector already shows the prompt to load users


# ── Mode 2: Custom Persona ────────────────────────────────────────────────
elif mode == "Custom Persona":
    st.caption(
        "Paste any persona in JSON or text format. The backend normalises it into a usable persona."
    )
    category = st.selectbox(
        "Category",
        api_client.CATEGORIES,
        index=0,
        key="rec_custom_category",
    )
    persona_text = st.text_area(
        "Persona (JSON or text)",
        value=json.dumps(PERSONA_SAMPLE, indent=2),
        height=200,
        key="rec_custom_persona_text",
    )

    if st.button("Load Persona", key="rec_load_custom_persona"):
        try:
            parsed = parse_json_or_text_input("Persona", persona_text)
            st.session_state["rec_custom_persona"] = parsed
            reset_chat()
            st.success("Custom persona loaded.")
        except Exception as exc:
            render_error(exc)

    custom_persona = st.session_state.get("rec_custom_persona")
    if custom_persona:
        col_new, col_just = st.columns([1, 1])
        with col_new:
            if st.button("New conversation", key="rec_custom_new_conv"):
                reset_chat()
                st.session_state["rec_custom_persona"] = custom_persona
                st.rerun()
        with col_just:
            if st.button("Just Recommend", type="primary", key="rec_custom_just_recommend"):
                add_message("user", "Recommend products based on my preferences.")
                try:
                    with st.spinner("Generating recommendations..."):
                        result = api_client.generate_with_session({
                            "persona": custom_persona,
                            "category": category,
                            "request": None,
                            "limit": limit,
                            "session_id": st.session_state["rec_session_id"],
                            "context": {},
                        })
                    add_message("assistant", result)
                except Exception as exc:
                    add_message("assistant", f"Error: {exc}")
                st.rerun()

        display_chat_history()

        if prompt := st.chat_input("Ask for recommendations or refine..."):
            add_message("user", prompt)
            try:
                with st.spinner("Generating recommendations..."):
                    result = api_client.generate_with_session({
                        "persona": custom_persona,
                        "category": category,
                        "request": prompt,
                        "limit": limit,
                        "session_id": st.session_state["rec_session_id"],
                        "context": {},
                    })
                add_message("assistant", result)
            except Exception as exc:
                add_message("assistant", f"Error: {exc}")
            st.rerun()


# ── Mode 3: Cold Start ────────────────────────────────────────────────────
elif mode == "No Persona (Cold Start)":
    st.caption("No persona required. Describe what you are looking for to get started.")

    with st.expander("Optional onboarding answers", expanded=False):
        st.caption("These answers help create a low-confidence starter persona.")
        interests_text = st.text_input(
            "Product interests or categories",
            placeholder="skincare, electronics, books",
            key="rec_cs_interests",
        )
        priorities_text = st.text_input(
            "Shopping priorities",
            placeholder="affordable, durable, simple, reliable",
            key="rec_cs_priorities",
        )
        dislikes_text = st.text_input(
            "Dislikes or things to avoid",
            placeholder="strong fragrance, flimsy build",
            key="rec_cs_dislikes",
        )
        strictness = st.selectbox(
            "Rating strictness",
            ["", "strict", "moderate", "generous"],
            index=0,
            key="rec_cs_strictness",
        )

    def _comma_terms(value: str) -> list[str]:
        return [t.strip() for t in value.split(",") if t.strip()]

    def _onboarding_payload() -> dict | None:
        payload: dict = {}
        if _comma_terms(interests_text):
            payload["interests"] = _comma_terms(interests_text)
        if _comma_terms(priorities_text):
            payload["priorities"] = _comma_terms(priorities_text)
        if _comma_terms(dislikes_text):
            payload["dislikes"] = _comma_terms(dislikes_text)
        if strictness:
            payload["rating_strictness"] = strictness
        return payload or None

    col_new_cs = st.columns([1, 3])
    with col_new_cs[0]:
        if st.button("New conversation", key="rec_cs_new_conv"):
            reset_chat()
            st.rerun()

    display_chat_history()

    if prompt := st.chat_input("Describe what you are looking for..."):
        add_message("user", prompt)
        try:
            with st.spinner("Generating recommendations..."):
                if not st.session_state["rec_messages"] or len([
                    m for m in st.session_state["rec_messages"] if m["role"] == "user"
                ]) <= 1:
                    result = api_client.cold_start_recommendations({
                        "request": prompt,
                        "limit": limit,
                        "onboarding_answers": _onboarding_payload(),
                        "context": {},
                    })
                    if result.get("session_id"):
                        st.session_state["rec_session_id"] = result["session_id"]
                else:
                    result = api_client.session_message(
                        st.session_state["rec_session_id"],
                        {
                            "message": prompt,
                            "limit": limit,
                        },
                    )
            add_message("assistant", result)
        except Exception as exc:
            add_message("assistant", f"Error: {exc}")
        st.rerun()
