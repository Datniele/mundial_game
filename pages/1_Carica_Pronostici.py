import re
import tempfile
from pathlib import Path

import streamlit as st

from src.models.participant import Participant
from src.models.tournament import load_fixtures
from src.parsers.prediction_parser import parse_prediction_file
from src.storage.json_storage import (
    delete_participant,
    load_all_participants,
    load_participant,
    merge_participant,
    save_participant,
)

st.set_page_config(page_title="Carica Pronostici", page_icon="📤", layout="wide")
st.title("📤 Carica Pronostici")


@st.cache_data
def _group_match_ids() -> set:
    matches, _ = load_fixtures()
    return set(matches.keys())


# (label, predicate(match_id, group_ids) | None for special cases)
_PHASES = [
    ("Gironi", lambda mid, gids: mid in gids),
    ("Class. Gironi", None),
    ("Sedicesimi", lambda mid, _: bool(re.match(r"^S\d", mid))),
    ("Ottavi", lambda mid, _: bool(re.match(r"^O\d", mid))),
    ("Quarti", lambda mid, _: bool(re.match(r"^Q\d", mid))),
    ("Semifinali", lambda mid, _: bool(re.match(r"^SF\d", mid))),
    ("3° Posto", lambda mid, _: mid.startswith("3P")),
    ("Finale", lambda mid, _: bool(re.match(r"^F\d", mid))),
]


def _phase_coverage(participant: Participant, group_ids: set) -> dict[str, bool]:
    preds = set(participant.match_predictions.keys())
    coverage = {}
    for label, check in _PHASES:
        if label == "Class. Gironi":
            coverage[label] = len(participant.group_rankings) > 0
        else:
            coverage[label] = any(check(mid, group_ids) for mid in preds)
    return coverage


def _show_coverage(coverage: dict[str, bool]):
    cols = st.columns(len(_PHASES))
    for col, (label, _) in zip(cols, _PHASES):
        icon = "✅" if coverage.get(label) else "⬜"
        col.metric(label=label, value=icon)


# ---------- Upload ----------

st.subheader("Carica file Excel partecipante")

st.info(
    "Puoi caricare i pronostici **fase per fase**, anche in momenti diversi. "
    "Ogni file aggiorna solo le fasi presenti al suo interno; le altre restano invariate."
)

replace_mode = st.checkbox(
    "Sostituisci completamente i pronostici esistenti",
    value=False,
    help="Attiva solo se vuoi azzerare e ricaricare tutto da zero per questo partecipante.",
)

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

        if replace_mode:
            save_participant(participant)
            action = "sostituiti completamente"
        else:
            merge_participant(participant)
            action = "aggiornati"

        st.success(f"Pronostici di **{participant.name}** {action} correttamente.")

        group_ids = _group_match_ids()

        # Stato dopo il salvataggio (include eventuali fasi già presenti)
        saved = load_participant(participant.name) or participant
        coverage = _phase_coverage(saved, group_ids)

        st.write("**Copertura complessiva del partecipante:**")
        _show_coverage(coverage)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Partite totali salvate", len(saved.match_predictions))
        with col2:
            st.metric("Gironi classificati", len(saved.group_rankings))

    except Exception as e:
        st.error(f"Errore nel parsing: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

st.divider()

# ---------- Partecipanti registrati ----------

st.subheader("Partecipanti registrati")

participants = load_all_participants()

if not participants:
    st.info("Nessun partecipante ancora caricato.")
else:
    group_ids = _group_match_ids()

    for p in participants:
        coverage = _phase_coverage(p, group_ids)
        covered_count = sum(coverage.values())
        total_phases = len(_PHASES)

        with st.expander(
            f"**{p.name}** — {covered_count}/{total_phases} fasi · "
            f"{len(p.match_predictions)} partite · {len(p.group_rankings)} gironi"
        ):
            _show_coverage(coverage)
            st.write("")
            if st.button("Elimina", key=f"del_{p.name}"):
                delete_participant(p.name)
                st.rerun()
