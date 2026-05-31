import streamlit as st
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

st.set_page_config(page_title="Configurazione", page_icon="⚙️", layout="centered")
st.title("⚙️ Configurazione Punteggi")

with open(CONFIG_PATH, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

gs = cfg["scoring"]["group_stage"]
ko = cfg["scoring"]["knockout"]

st.subheader("Fase a gironi")

col1, col2 = st.columns(2)
with col1:
    exact = st.number_input("Risultato esatto", min_value=0, max_value=20, value=gs["exact_score"])
    outcome = st.number_input("Esito corretto (V/P/N)", min_value=0, max_value=20, value=gs["correct_outcome"])
with col2:
    rank_exact = st.number_input("Classifica girone identica", min_value=0, max_value=20, value=gs["group_ranking_exact"])
    rank_partial = st.number_input("Classifica girone parziale", min_value=0, max_value=20, value=gs["group_ranking_partial"])

st.subheader("Fase a eliminazione diretta")

col3, col4 = st.columns(2)
with col3:
    ko_winner = st.number_input("Chi passa il turno", min_value=0, max_value=20, value=ko["correct_winner"])
with col4:
    ko_exact = st.number_input("Risultato esatto", min_value=0, max_value=20, value=ko["exact_score"], key="ko_exact")

if st.button("💾 Salva configurazione"):
    cfg["scoring"]["group_stage"]["exact_score"] = int(exact)
    cfg["scoring"]["group_stage"]["correct_outcome"] = int(outcome)
    cfg["scoring"]["group_stage"]["group_ranking_exact"] = int(rank_exact)
    cfg["scoring"]["group_stage"]["group_ranking_partial"] = int(rank_partial)
    cfg["scoring"]["knockout"]["correct_winner"] = int(ko_winner)
    cfg["scoring"]["knockout"]["exact_score"] = int(ko_exact)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    st.success("Configurazione salvata. I punteggi verranno ricalcolati al prossimo accesso alla Classifica.")

st.divider()
st.caption("I valori vengono applicati al prossimo ricalcolo punteggi.")
