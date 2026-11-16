"""Native Streamlit page; leaves the frozen design-change app.py unchanged."""
from pathlib import Path
import sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from research.ifc4d.viewer_ui import render
st.set_page_config(page_title="PMI | Synthetic IFC4D",layout="wide")
render(ROOT)
