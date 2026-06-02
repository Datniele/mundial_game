import json
import re

import streamlit as st

from src.models.tournament import load_fixtures
from src.models.participant import Participant
from src.storage.json_storage import (
    delete_participant,
    load_all_participants,
    merge_participant,
    register_participant,
    reset_all_predictions,
    update_registry_timestamp,
)

_AUTHORIZED_EMAILS = {"dani.testav@gmail.com", "pietrosestito96@gmail.com"}

st.set_page_config(page_title="Impostazioni Admin", page_icon="🔧", layout="wide")
st.title("🔧 Impostazioni Admin — Gestione Partecipanti")

# ── Identità admin ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Accesso admin")
    admin_email = st.text_input(
        "La tua email",
        placeholder="indirizzo@email.com",
        key="admin_identity",
    ).strip().lower()

is_authorized = admin_email in _AUTHORIZED_EMAILS

if admin_email and not is_authorized:
    st.sidebar.warning("Accesso non autorizzato.")
elif not admin_email:
    st.sidebar.info("Inserisci la tua email per abilitare le operazioni di eliminazione.")

# ── Fixtures (per copertura fasi) ──────────────────────────────────────────────


@st.cache_data
def _group_match_ids() -> set:
    matches, _ = load_fixtures()
    return set(matches.keys())


_PHASES = [
    ("Class. Gironi", None),
    ("Sedicesimi", lambda mid, _: bool(re.match(r"^S\d", mid))),
    ("Ottavi", lambda mid, _: bool(re.match(r"^O\d", mid))),
    ("Quarti", lambda mid, _: bool(re.match(r"^Q\d", mid))),
    ("Semifinali", lambda mid, _: bool(re.match(r"^SF\d", mid))),
    ("3° Posto", lambda mid, _: mid.startswith("3P")),
    ("Finale", lambda mid, _: bool(re.match(r"^F\d", mid))),
]


def _phase_coverage(participant, group_ids: set) -> dict[str, bool]:
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


# ── Partecipanti registrati ────────────────────────────────────────────────────

st.subheader("Partecipanti registrati")

participants = load_all_participants()
group_ids = _group_match_ids()

if not participants:
    st.info("Nessun partecipante ancora registrato.")
else:
    for p in participants:
        coverage = _phase_coverage(p, group_ids)
        covered_count = sum(coverage.values())
        total_phases = len(_PHASES)

        with st.expander(
            f"**{p.name}** — {covered_count}/{total_phases} fasi · "
            f"{len(p.group_rankings)} gironi classificati · "
            f"{len(p.match_predictions)} partite knockout"
        ):
            _show_coverage(coverage)
            st.write("")
            col_btn, col_msg = st.columns([1, 4])
            with col_btn:
                if col_btn.button(
                    "Elimina",
                    key=f"del_{p.name}",
                    disabled=not is_authorized,
                ):
                    delete_participant(p.name)
                    st.rerun()
            if not is_authorized:
                col_msg.caption("Accesso non autorizzato.")

st.divider()

# ── Carica pronostici da file ──────────────────────────────────────────────────

st.subheader("📂 Carica pronostici da file")
st.caption("Carica un file JSON di pronostici esportato dall'app. I dati vengono uniti con quelli già presenti.")

uploaded = st.file_uploader("File JSON pronostici", type="json", key="upload_predictions")

if uploaded is not None:
    try:
        raw = json.load(uploaded)
        participant = Participant.from_dict(raw)
        col_up, col_msg = st.columns([1, 4])
        with col_up:
            if st.button("⬆️ Importa", key="btn_import", disabled=not is_authorized):
                register_participant(participant.name)
                merge_participant(participant)
                update_registry_timestamp(participant.name)
                st.success(
                    f"Pronostici di **{participant.name}** importati correttamente "
                    f"({len(participant.group_rankings)} gironi, "
                    f"{len(participant.match_predictions)} partite knockout)."
                )
                st.rerun()
        if not is_authorized:
            col_msg.caption("Accesso non autorizzato.")
    except Exception as e:
        st.error(f"File non valido: {e}")

st.divider()

# ── Reset completo ─────────────────────────────────────────────────────────────

st.subheader("⚠️ Reset completo")
st.warning(
    "Questa operazione elimina **tutti** i pronostici e il registro dei partecipanti. "
    "L'azione è irreversibile."
)

confirm = st.checkbox("Confermo di voler cancellare tutti i dati", disabled=not is_authorized)
if st.button("🗑️ Reset completo", type="primary", disabled=not (confirm and is_authorized)):
    removed = reset_all_predictions()
    st.success(f"Reset completato: {removed} file eliminati, registry svuotato.")
    st.rerun()
if not is_authorized:
    st.caption("Accesso non autorizzato.")
