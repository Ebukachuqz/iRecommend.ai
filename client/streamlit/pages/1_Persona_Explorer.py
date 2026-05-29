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
    ensure_backend_ready,
    render_error,
    render_persona_preview_card,
    render_persona_tabs,
    render_user_selector,
    safe_json_view,
)

st.set_page_config(
    page_title="Persona Explorer",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Persona Explorer")
ensure_backend_ready()
st.markdown("Browse and inspect user personas generated from review history.")

st.divider()

# --- Persona selection ---
user_id, category, persona_row = render_user_selector(page_key="explorer")

if persona_row is None:
    st.info("Select a user above to load their persona.")
    st.stop()

persona: dict = persona_row.get("persona", {})

if not persona:
    render_error("No persona data found for this user.")
    st.stop()

# --- Persona preview card (metrics) ---
render_persona_preview_card(persona_row)

st.divider()

# --- Persona detail tabs ---
render_persona_tabs(persona)

st.divider()

# --- Copy Persona JSON ---
st.subheader("Export")

if st.button("📋 Copy Persona JSON", key="copy_persona_json"):
    st.session_state["show_persona_json"] = True

if st.session_state.get("show_persona_json", False):
    st.caption("Select and copy the JSON below:")
    st.code(json.dumps(persona, indent=2, default=str), language="json")

# --- Raw row data ---
safe_json_view("Raw persona row", persona_row)
