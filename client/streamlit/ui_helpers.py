from __future__ import annotations

import json
from typing import Any

try:
    import streamlit as st
except ModuleNotFoundError:  # Allows lightweight unit tests before Streamlit is installed.
    st = None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_score(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def get_persona_average_rating(persona_row: dict[str, Any] | None) -> float | str:
    if not persona_row:
        return "n/a"
    db_average = persona_row.get("average_rating")
    if db_average is not None:
        return db_average
    persona = persona_row.get("persona") or {}
    rating_behavior = persona.get("rating_behavior") if isinstance(persona, dict) else {}
    if isinstance(rating_behavior, dict) and rating_behavior.get("average_rating") is not None:
        return rating_behavior["average_rating"]
    return "n/a"


def friendly_category(category: str) -> str:
    """Convert 'Health_and_Household' to 'Health & Household'."""
    return category.replace("_", " ").replace(" and ", " & ")


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def parse_json_text(label: str, text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return parsed


def parse_json_or_text_input(label: str, text: str) -> dict[str, Any] | str:
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"{label} cannot be empty.")
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label} looks like JSON but is malformed: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{label} JSON must be an object.")
        return parsed
    return stripped


# ---------------------------------------------------------------------------
# Basic rendering helpers
# ---------------------------------------------------------------------------

def render_status_badge(label: str, ok: bool | None) -> None:
    if st is None:
        return
    if ok is True:
        st.success(f"{label}: ok")
    elif ok is False:
        st.error(f"{label}: not ready")
    else:
        st.info(f"{label}: not checked")


def render_error(error: Exception | str) -> None:
    if st is None:
        return
    st.error(str(error))


def safe_json_view(label: str, payload: Any, expanded: bool = False) -> None:
    if st is None:
        return
    with st.expander(label, expanded=expanded):
        st.json(payload)


def is_json_renderable(value: Any) -> bool:
    return isinstance(value, dict | list)


# ---------------------------------------------------------------------------
# Persona display components
# ---------------------------------------------------------------------------

def render_persona_section(title: str, persona: dict[str, Any], key: str) -> None:
    if st is None:
        return
    value = persona.get(key)
    with st.expander(title, expanded=key in {"writing_style", "preferences", "rating_behavior"}):
        if value is None:
            st.info("No data available.")
        elif is_json_renderable(value):
            st.json(value)
        else:
            st.write(str(value))


def render_persona_tabs(persona: dict[str, Any]) -> None:
    """Render persona sections as tabs instead of stacked expanders."""
    if st is None:
        return
    tab_map = {
        "Writing Style": "writing_style",
        "Preferences": "preferences",
        "Rating Behaviour": "rating_behavior",
        "Purchase Behaviour": "purchase_behavior",
        "Cultural Signals": "cultural_signals",
        "Evidence": "evidence",
    }
    available = {label: key for label, key in tab_map.items() if persona.get(key) is not None}
    if not available:
        st.info("No persona details available.")
        return
    tabs = st.tabs(list(available.keys()))
    for tab, (_, key) in zip(tabs, available.items()):
        value = persona.get(key)
        with tab:
            if is_json_renderable(value):
                st.json(value)
            else:
                st.write(str(value))


def render_persona_preview_card(persona_row: dict[str, Any]) -> None:
    """Compact persona preview card showing key metrics."""
    if st is None:
        return
    cols = st.columns(4)
    cols[0].metric("Reviews", persona_row.get("review_count") or 0)
    cols[1].metric("Avg Rating", format_score(get_persona_average_rating(persona_row)))
    cols[2].metric("Source Reviews", len(persona_row.get("source_review_ids") or []))
    cols[3].metric("Version", persona_row.get("persona_version") or "n/a")


# ---------------------------------------------------------------------------
# User selector widget
# ---------------------------------------------------------------------------

def render_user_selector(page_key: str) -> tuple[str | None, str, dict | None]:
    """Reusable user selection widget.

    Returns (user_id, category, persona_row) where persona_row may be None
    if not yet loaded.
    """
    if st is None:
        return None, "", None

    import api_client  # deferred import to avoid circular dependency at module level

    category = st.selectbox(
        "Category",
        api_client.CATEGORIES,
        index=api_client.CATEGORIES.index(
            st.session_state.get("category", api_client.DEFAULT_CATEGORY)
        )
        if st.session_state.get("category") in api_client.CATEGORIES
        else 0,
        key=f"{page_key}_category",
    )

    col_load, col_limit = st.columns([2, 1])
    with col_limit:
        limit = st.number_input("Limit", min_value=1, max_value=100, value=20, key=f"{page_key}_limit")
    with col_load:
        if st.button("Load users", key=f"{page_key}_load_users"):
            try:
                users = api_client.list_users(category=category, limit=int(limit))
                st.session_state[f"{page_key}_users"] = users
                st.session_state["category"] = category
            except Exception as exc:
                render_error(exc)

    users = st.session_state.get(f"{page_key}_users", [])
    user_id = None
    persona_row = None

    if users:
        user_options = [row["user_id"] for row in users]
        default_user = st.session_state.get("selected_user_id")
        index = user_options.index(default_user) if default_user and default_user in user_options else 0
        user_id = st.selectbox("User", user_options, index=index, key=f"{page_key}_user_select")
        st.session_state["selected_user_id"] = user_id

        selected_summary = next((row for row in users if row["user_id"] == user_id), {})
        summary_cols = st.columns(3)
        summary_cols[0].metric("Reviews", selected_summary.get("review_count") or 0)
        summary_cols[1].metric("Avg Rating", format_score(get_persona_average_rating(selected_summary)))
        summary_cols[2].metric("Version", selected_summary.get("persona_version") or "n/a")

        if st.button("Load persona", key=f"{page_key}_load_persona"):
            try:
                persona_row = api_client.get_persona(user_id, category=category)
                st.session_state[f"{page_key}_persona_row"] = persona_row
            except Exception as exc:
                render_error(exc)

        persona_row = st.session_state.get(f"{page_key}_persona_row")
        if persona_row:
            with st.expander("Persona preview", expanded=False):
                render_persona_preview_card(persona_row)
                persona = persona_row.get("persona") or {}
                render_persona_tabs(persona)
    else:
        st.info("Select a category and click **Load users** to begin.")

    return user_id, category, persona_row


# ---------------------------------------------------------------------------
# Simulation result rendering
# ---------------------------------------------------------------------------

def render_rating_breakdown(breakdown: dict[str, Any] | None) -> None:
    if st is None:
        return
    if not breakdown:
        st.info("No rating breakdown returned.")
        return
    st.dataframe([breakdown], use_container_width=True)
    safe_json_view("Raw rating breakdown", breakdown)


def render_simulation_result(result: dict[str, Any]) -> None:
    """Render a Task A simulation output card."""
    if st is None:
        return

    st.subheader(result.get("product_title") or result.get("parent_asin") or "Simulation Result")
    cols = st.columns(3)
    cols[0].metric("Final Rating", format_score(result.get("final_predicted_rating")))
    cols[1].metric("LLM Rating", format_score(result.get("llm_predicted_rating")))
    cols[2].metric("Statistical Rating", format_score(result.get("statistical_predicted_rating")))

    review_title = result.get("simulated_review_title")
    if review_title:
        st.markdown(f"**{review_title}**")
    st.write(result.get("simulated_review_text") or "No review text generated.")

    reasoning = result.get("reasoning_summary")
    if reasoning:
        with st.expander("Reasoning", expanded=False):
            st.write(reasoning)

    evidence = result.get("evidence_used") or []
    if evidence:
        with st.expander("Evidence used", expanded=False):
            for item in evidence:
                st.markdown(f"- {item}")

    render_rating_breakdown(result.get("rating_breakdown"))
    safe_json_view("Raw simulation output", result)


# ---------------------------------------------------------------------------
# Recommendation card rendering
# ---------------------------------------------------------------------------

def render_recommendation_card(item: dict[str, Any]) -> None:
    if st is None:
        return
    title = item.get("title") or item.get("parent_asin") or "Recommendation"
    with st.container(border=True):
        rank = item.get("rank", "?")
        st.markdown(f"#### #{rank} {title}")
        st.caption(item.get("parent_asin", ""))
        
        images = item.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            # Prefer the MAIN variant, fallback to the first image
            target_img = next((img for img in images if isinstance(img, dict) and img.get("variant") == "MAIN"), images[0])
            
            img_url = None
            if isinstance(target_img, dict):
                img_url = target_img.get("large") or target_img.get("hi_res") or target_img.get("thumb")
            elif isinstance(target_img, str):
                img_url = target_img
                
            if img_url:
                st.image(img_url, width=150)

        st.write(item.get("reason", "No reason returned."))
        cols = st.columns(2)
        cols[0].metric("Confidence", format_score(item.get("confidence")))
        score_breakdown = item.get("score_breakdown") or {}
        cols[1].metric("Final Score", format_score(score_breakdown.get("final_score")))
        if item.get("is_discovery_candidate") or score_breakdown.get("is_discovery_candidate"):
            st.info("Discovery candidate: limited review history.")
        evidence = item.get("evidence") or []
        if evidence:
            st.caption("Evidence: " + ", ".join(str(term) for term in evidence))
        safe_json_view("Score breakdown", score_breakdown)


def render_recommendation_results(result: dict[str, Any]) -> None:
    """Render a full recommendation response (intent + cards)."""
    if st is None:
        return
    intent = result.get("intent")
    if intent:
        with st.expander("Intent analysis", expanded=False):
            st.json(intent)
    recommendations = result.get("recommendations") or []
    if recommendations:
        for item in recommendations:
            render_recommendation_card(item)
    else:
        st.info("No recommendations returned.")
    candidate_count = result.get("candidate_count")
    if candidate_count is not None:
        st.caption(f"Candidates evaluated: {candidate_count}")
    safe_json_view("Raw recommendation output", result)
