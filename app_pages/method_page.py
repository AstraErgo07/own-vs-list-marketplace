"""Data and method page."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.text import VERSION  # noqa: E402

st.caption(f"Own vs List {VERSION}")
st.markdown((ROOT / "data" / "SOURCES.md").read_text(encoding="utf-8"))
