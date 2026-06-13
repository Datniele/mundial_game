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
st.caption(
    "Carica un file JSON di pronostici esportato dall'app. Sono accettati sia "
    "l'export di un singolo partecipante sia l'export per fase (più partecipanti). "
    "I dati vengono uniti con quelli già presenti."
)


def _parse_upload(raw) -> list[Participant]:
    """Estrae i partecipanti da un file caricato.

    Accetta entrambi i formati prodotti dall'app:
    - export per fase: {"phase": ..., "participants": [{...}, ...]}
    - singolo partecipante: {"name": ..., "match_predictions"/"group_rankings": ...}
    """
    if isinstance(raw, dict) and isinstance(raw.get("participants"), list):
        entries = raw["participants"]
    elif isinstance(raw, list):
        entries = raw
    else:
        entries = [raw]
    return [Participant.from_dict(entry) for entry in entries]


uploaded = st.file_uploader("File JSON pronostici", type="json", key="upload_predictions")

if uploaded is not None:
    try:
        raw = json.load(uploaded)
        parsed = _parse_upload(raw)
        if not parsed:
            st.warning("Il file non contiene pronostici da importare.")
        else:
            names = ", ".join(f"**{p.name}**" for p in parsed)
            st.caption(f"{len(parsed)} partecipante/i nel file: {names}")
            col_up, col_msg = st.columns([1, 4])
            with col_up:
                if st.button("⬆️ Importa", key="btn_import", disabled=not is_authorized):
                    for participant in parsed:
                        register_participant(participant.name)
                        merge_participant(participant)
                        update_registry_timestamp(participant.name)
                    tot_gironi = sum(len(p.group_rankings) for p in parsed)
                    tot_knockout = sum(len(p.match_predictions) for p in parsed)
                    st.success(
                        f"Importati i pronostici di {len(parsed)} partecipante/i "
                        f"({tot_gironi} gironi, {tot_knockout} partite knockout)."
                    )
                    st.rerun()
            if not is_authorized:
                col_msg.caption("Accesso non autorizzato.")
    except Exception as e:
        st.error(f"File non valido: {e}")

# ── Scarica pronostici per fase ─────────────────────────────────────────────────

st.subheader("📥 Scarica pronostici per fase")
st.caption("Seleziona una fase di gioco ed esporta in JSON i pronostici di tutti i partecipanti per quella fase.")


def _phase_export(participant, label: str, check, group_ids: set) -> dict | None:
    """Estrae i pronostici di un partecipante per la fase indicata. None se vuoti."""
    if label == "Class. Gironi":
        if not participant.group_rankings:
            return None
        return {"name": participant.name, "group_rankings": participant.group_rankings}
    match_preds = {
        mid: {"home_goals": p.home_goals, "away_goals": p.away_goals}
        for mid, p in participant.match_predictions.items()
        if check(mid, group_ids)
    }
    if not match_preds:
        return None
    return {"name": participant.name, "match_predictions": match_preds}


col_phase, col_dl = st.columns([2, 1])
with col_phase:
    selected_label = st.selectbox(
        "Fase di gioco",
        options=[label for label, _ in _PHASES],
        key="download_phase",
    )

selected_check = next(check for label, check in _PHASES if label == selected_label)
phase_entries = [
    entry
    for p in participants
    if (entry := _phase_export(p, selected_label, selected_check, group_ids)) is not None
]

export_payload = json.dumps(
    {"phase": selected_label, "participants": phase_entries},
    ensure_ascii=False,
    indent=2,
)
phase_slug = re.sub(r"[^a-z0-9]+", "_", selected_label.lower()).strip("_")

with col_dl:
    st.write("")
    st.write("")
    st.download_button(
        "⬇️ Scarica JSON",
        data=export_payload,
        file_name=f"pronostici_{phase_slug}.json",
        mime="application/json",
        disabled=not phase_entries,
    )

if not phase_entries:
    st.info(f"Nessun pronostico inserito per la fase «{selected_label}».")
else:
    st.caption(f"{len(phase_entries)} partecipanti con pronostici per «{selected_label}».")

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
