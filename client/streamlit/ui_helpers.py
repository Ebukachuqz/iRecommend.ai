from __future__ import annotations

from typing import Any

try:
    import streamlit as st
except ModuleNotFoundError:  # Allows lightweight unit tests before Streamlit is installed.
    st = None


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


def render_persona_section(title: str, persona: dict[str, Any], key: str) -> None:
    if st is None:
        return
    value = persona.get(key)
    with st.expander(title, expanded=key in {"writing_style", "preferences", "rating_behavior"}):
        st.json(value if value is not None else {})


def render_rating_breakdown(breakdown: dict[str, Any] | None) -> None:
    if st is None:
        return
    if not breakdown:
        st.info("No rating breakdown returned.")
        return
    st.dataframe([breakdown], use_container_width=True)
    safe_json_view("Raw rating breakdown", breakdown)


def render_recommendation_card(item: dict[str, Any]) -> None:
    if st is None:
        return
    title = item.get("title") or item.get("parent_asin") or "Recommendation"
    with st.container(border=True):
        st.subheader(f"#{item.get('rank', '?')} {title}")
        st.caption(item.get("parent_asin", ""))
        st.write(item.get("reason", "No reason returned."))
        cols = st.columns(2)
        cols[0].metric("Confidence", format_score(item.get("confidence")))
        score_breakdown = item.get("score_breakdown") or {}
        cols[1].metric("Final score", format_score(score_breakdown.get("final_score")))
        evidence = item.get("evidence") or []
        if evidence:
            st.write("Evidence: " + ", ".join(str(term) for term in evidence))
        safe_json_view("Score breakdown", score_breakdown)
