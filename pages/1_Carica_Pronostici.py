import streamlit as st
import tempfile
from pathlib import Path

from src.parsers.prediction_parser import parse_prediction_file
from src.storage.json_storage import save_participant, load_all_participants, delete_participant, list_participants

st.set_page_config(page_title="Carica Pronostici", page_icon="📤", layout="wide")
st.title("📤 Carica Pronostici")

# --- Upload ---
st.subheader("Carica file Excel partecipante")
uploaded = st.file_uploader(
    "Seleziona il file Excel del partecipante (formato: nome_cognome.xlsx)",
    type=["xlsx"],
)

if uploaded:
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = Path(tmp.name)

    try:
        with st.spinner("Parsing del file in corso..."):
            participant = parse_prediction_file(tmp_path)
            participant.name = Path(uploaded.name).stem.replace("_", " ").title()
        save_participant(participant)
        st.success(f"Pronostici di **{participant.name}** caricati correttamente.")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Partite pronosticate", len(participant.match_predictions))
        with col2:
            st.metric("Gironi classificati", len(participant.group_rankings))

    except Exception as e:
        st.error(f"Errore nel parsing: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

st.divider()

# --- Partecipanti registrati ---
st.subheader("Partecipanti registrati")

participants = load_all_participants()

if not participants:
    st.info("Nessun partecipante ancora caricato.")
else:
    for p in participants:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"**{p.name}**")
        with col2:
            st.write(f"{len(p.match_predictions)} partite · {len(p.group_rankings)} gironi")
        with col3:
            if st.button("Elimina", key=f"del_{p.name}"):
                delete_participant(p.name)
                st.rerun()
