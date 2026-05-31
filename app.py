import streamlit as st

st.set_page_config(
    page_title="Mondiali 2026 - Pronostici",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Mondiali 2026 — Gestione Pronostici")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.info("**📤 Carica Pronostici**\nCarica il file Excel di un partecipante")

with col2:
    st.info("**📡 Risultati Reali**\nScarica i risultati dal sito ufficiale")

with col3:
    st.info("**🏆 Classifica**\nVisualizza la classifica aggiornata")

with col4:
    st.info("**⚙️ Configurazione**\nModifica le regole di punteggio")

st.markdown("---")
st.caption("Usa il menu laterale per navigare tra le sezioni.")
