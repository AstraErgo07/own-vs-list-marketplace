"""Footer for the Own vs List app."""
import streamlit as st

from common.text import FOOTER, VERSION


def footer() -> None:
    st.divider()
    st.caption(f"{VERSION} · {FOOTER}")
