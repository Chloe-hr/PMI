"""PMI decision dashboard, separate from the frozen midterm entry point."""
from pathlib import Path
import sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from research.ifc4d.dashboard import render
st.set_page_config(page_title="PMI | Project dashboard",layout="wide",initial_sidebar_state="collapsed")
render(ROOT)
