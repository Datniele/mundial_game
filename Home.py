import asyncio
import sys

# Fix Windows ProactorEventLoop + ConnectionResetError (WinError 10054)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="Home",
    page_icon="⚽",
    layout="wide",
)

st.title("Mundial Game")
st.subheader("⚽ Il giocone ludopatico dei mondiali")
st.markdown("---")
st.caption("Usa il menu a sinistra per navigare tra le sezioni.")

col_l, col_c, col_r = st.columns([2, 1, 2])
with col_c:
    logo_path = Path(__file__).parent / "data" / "download.png"
    st.image(str(logo_path))
