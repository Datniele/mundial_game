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

st.set_page_config(page_title="Admin Settings", page_icon="🔧", layout="wide")
st.title("🔧 Admin Settings — Player Management")

# ── Identità admin ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Admin access")
    admin_email = st.text_input(
        "Your email",
        placeholder="you@email.com",
        key="admin_identity",
    ).strip().lower()

is_authorized = admin_email in _AUTHORIZED_EMAILS

if admin_email and not is_authorized:
    st.sidebar.warning("Access denied. Nice try, though. 🚫")
elif not admin_email:
    st.sidebar.info("Drop in your email to unlock the delete buttons.")

# ── Fixtures (per copertura fasi) ──────────────────────────────────────────────


@st.cache_data
def _group_match_ids() -> set:
    matches, _ = load_fixtures()
    return set(matches.keys())


_PHASES = [
    ("Group Standings", None),
    ("Round of 32", lambda mid, _: bool(re.match(r"^S\d", mid))),
    ("Round of 16", lambda mid, _: bool(re.match(r"^O\d", mid))),
    ("Quarter-finals", lambda mid, _: bool(re.match(r"^Q\d", mid))),
    ("Semi-finals", lambda mid, _: bool(re.match(r"^SF\d", mid))),
    ("Third Place", lambda mid, _: mid.startswith("3P")),
    ("Final", lambda mid, _: bool(re.match(r"^F\d", mid))),
]


def _phase_coverage(participant, group_ids: set) -> dict[str, bool]:
    preds = set(participant.match_predictions.keys())
    coverage = {}
    for label, check in _PHASES:
        if label == "Group Standings":
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

st.subheader("Registered players")

participants = load_all_participants()
group_ids = _group_match_ids()

if not participants:
    st.info("No players signed up yet.")
else:
    for p in participants:
        coverage = _phase_coverage(p, group_ids)
        covered_count = sum(coverage.values())
        total_phases = len(_PHASES)

        with st.expander(
            f"**{p.name}** — {covered_count}/{total_phases} phases · "
            f"{len(p.group_rankings)} groups ranked · "
            f"{len(p.match_predictions)} knockout matches"
        ):
            _show_coverage(coverage)
            st.write("")
            col_btn, col_msg = st.columns([1, 4])
            with col_btn:
                if col_btn.button(
                    "Delete",
                    key=f"del_{p.name}",
                    disabled=not is_authorized,
                ):
                    delete_participant(p.name)
                    st.rerun()
            if not is_authorized:
                col_msg.caption("Access denied.")

st.divider()

# ── Carica pronostici da file ──────────────────────────────────────────────────

st.subheader("📂 Upload predictions from a file")
st.caption(
    "Upload a JSON predictions file exported from the app. Both the single-player export "
    "and the per-phase export (multiple players) are accepted. "
    "The data gets merged with whatever's already there."
)


def _parse_upload(raw) -> list[Participant]:
    """Extract the players from an uploaded file.

    Accepts both formats produced by the app:
    - per-phase export: {"phase": ..., "participants": [{...}, ...]}
    - single player: {"name": ..., "match_predictions"/"group_rankings": ...}
    """
    if isinstance(raw, dict) and isinstance(raw.get("participants"), list):
        entries = raw["participants"]
    elif isinstance(raw, list):
        entries = raw
    else:
        entries = [raw]
    return [Participant.from_dict(entry) for entry in entries]


uploaded = st.file_uploader("Predictions JSON file", type="json", key="upload_predictions")

if uploaded is not None:
    try:
        raw = json.load(uploaded)
        parsed = _parse_upload(raw)
        if not parsed:
            st.warning("This file doesn't contain any predictions to import.")
        else:
            names = ", ".join(f"**{p.name}**" for p in parsed)
            st.caption(f"{len(parsed)} player(s) in the file: {names}")
            col_up, col_msg = st.columns([1, 4])
            with col_up:
                if st.button("⬆️ Import", key="btn_import", disabled=not is_authorized):
                    for participant in parsed:
                        register_participant(participant.name)
                        merge_participant(participant)
                        update_registry_timestamp(participant.name)
                    tot_gironi = sum(len(p.group_rankings) for p in parsed)
                    tot_knockout = sum(len(p.match_predictions) for p in parsed)
                    st.success(
                        f"Imported predictions for {len(parsed)} player(s) "
                        f"({tot_gironi} groups, {tot_knockout} knockout matches)."
                    )
                    st.rerun()
            if not is_authorized:
                col_msg.caption("Access denied.")
    except Exception as e:
        st.error(f"Invalid file: {e}")

# ── Scarica pronostici per fase ─────────────────────────────────────────────────

st.subheader("📥 Download predictions by phase")
st.caption("Pick a game phase and export everyone's predictions for it to JSON.")


def _phase_export(participant, label: str, check, group_ids: set) -> dict | None:
    """Extract a player's predictions for the given phase. None if empty."""
    if label == "Group Standings":
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
        "Game phase",
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
        "⬇️ Download JSON",
        data=export_payload,
        file_name=f"predictions_{phase_slug}.json",
        mime="application/json",
        disabled=not phase_entries,
    )

if not phase_entries:
    st.info(f"No predictions submitted for the «{selected_label}» phase yet.")
else:
    st.caption(f"{len(phase_entries)} players with predictions for «{selected_label}».")

st.divider()

# ── Reset completo ─────────────────────────────────────────────────────────────

st.subheader("⚠️ Full reset")
st.warning(
    "This wipes **all** predictions and the entire player registry. "
    "There's no undo button — point of no return!"
)

confirm = st.checkbox("Yes, I really want to delete everything", disabled=not is_authorized)
if st.button("🗑️ Full reset", type="primary", disabled=not (confirm and is_authorized)):
    removed = reset_all_predictions()
    st.success(f"Reset done: {removed} files deleted, registry wiped clean.")
    st.rerun()
if not is_authorized:
    st.caption("Access denied.")
