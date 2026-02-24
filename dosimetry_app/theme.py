from __future__ import annotations

from pathlib import Path

import streamlit as st

from dosimetry_app.config import BASE_DIR

STYLE_FILE = BASE_DIR / "style.css"

FALLBACK_STYLE = """
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
.main .block-container { max-width: 1180px; padding: 1rem 1rem 2rem 1rem; }
"""


def apply_theme() -> None:
    css_text = FALLBACK_STYLE
    if Path(STYLE_FILE).exists():
        try:
            css_text = Path(STYLE_FILE).read_text(encoding="utf-8")
        except OSError:
            css_text = FALLBACK_STYLE

    st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)

