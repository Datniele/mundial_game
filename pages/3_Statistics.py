from collections import Counter

import streamlit as st
import pandas as pd

from src.storage.json_storage import load_all_participants, load_knockout_bracket
from src.models.tournament import get_knockout_match_ids_by_phase
from src.scraper.knockout_bracket import slot_label
from src.scoring.statistics import (
    EventConsensus,
    group_consensus,
    knockout_consensus,
    least_shared,
    most_shared,
    unanimous_count,
)

st.set_page_config(page_title="Stats", page_icon="📊", layout="wide")
st.title("📊 Stats")
st.caption(
    "Diocan 🐶 if you made it all the way down here, you're one nosy little number-cruncher."
)

participants = load_all_participants()


@st.cache_data
def _ko_ids() -> dict:
    return get_knockout_match_ids_by_phase()


ko_ids = _ko_ids()
bracket = load_knockout_bracket()

if not participants:
    st.info("Nobody's here yet. Head over to **Make Your Predictions** to kick things off.")
    st.stop()

KNOCKOUT_PHASES = [
    (["sedicesimi"], "Round of 32"),
    (["ottavi"], "Round of 16"),
    (["quarti"], "Quarter-finals"),
    (["semifinali"], "Semi-finals"),
    (["finale_3posto", "finale"], "Final"),
]

def _fmt_ranking(value) -> str:
    return " › ".join(value)


def _frac(ec: EventConsensus) -> str:
    return f"{ec.top_count}/{ec.total}"


def _advancing_team(label: str, side: str) -> str:
    """Nome della squadra che passa il turno per lo slot, o Team 1/Team 2 se non determinato."""
    entry = bracket.get(label) or {}
    if side == "home":
        return entry.get("home") or "Team 1"
    return entry.get("away") or "Team 2"


def _callouts(events: list[EventConsensus], fmt) -> None:
    """Show the most agreed-upon and the most divisive event."""
    top = most_shared(events)
    bottom = least_shared(events)
    c1, c2 = st.columns(2)
    with c1:
        st.success(
            f"🟢 **Crowd favourite: {top.label}** — {_frac(top)} agree\n\n{fmt(top.top_value)}"
        )
    with c2:
        st.error(
            f"🔴 **Biggest squabble: {bottom.label}** — {_frac(bottom)} agree\n\n{fmt(bottom.top_value)}"
        )


def _advances_by_player(match_ids: list[str]) -> None:
    """Tabella riepilogo: una riga per slot, una colonna per giocatore, la squadra
    che ciascuno ha indicato come qualificata (solo chi ha compilato la fase)."""
    active = [
        p for p in participants
        if any(
            (pred := p.match_predictions.get(mid)) is not None and pred.advances is not None
            for mid in match_ids
        )
    ]
    if not active:
        st.info("Nobody has picked who advances in this phase yet.")
        return

    rows = []
    for mid in match_ids:
        row = {"Slot": slot_label(mid, bracket)}
        for p in active:
            pred = p.match_predictions.get(mid)
            if pred is not None and pred.advances is not None:
                row[p.name] = _advancing_team(mid, pred.advances)
            else:
                row[p.name] = "—"
        rows.append(row)

    st.caption(f"{len(active)} player(s) · {len(match_ids)} match slot(s)")
    styled = pd.DataFrame(rows).style.apply(_highlight_non_modal, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _highlight_non_modal(row: pd.Series) -> list[str]:
    """Evidenzia le celle-giocatore che si discostano dalla scelta modale della riga.
    Le celle non pronosticate ('—') e la colonna Slot restano neutre."""
    player_cols = [c for c in row.index if c != "Slot"]
    picks = [row[c] for c in player_cols if row[c] != "—"]
    highlight = "background-color: rgba(255, 99, 71, 0.28)"
    styles = {c: "" for c in row.index}
    if picks:
        modal_pick = Counter(picks).most_common(1)[0][0]
        for c in player_cols:
            if row[c] != "—" and row[c] != modal_pick:
                styles[c] = highlight
    return [styles[c] for c in row.index]


tabs = st.tabs(["Group Stage"] + [label for _, label in KNOCKOUT_PHASES])

# ── Tab Gironi ─────────────────────────────────────────────────────────────────

with tabs[0]:
    st.subheader("Consensus — Group Stage")
    st.caption("One event = one group. Two picks count as the same only if the whole 1st→4th order matches.")

    events = group_consensus(participants)

    if not events:
        st.info("We need at least 2 players who've fully ranked the same group before any stats appear.")
    else:
        st.metric("Groups everyone agrees on (unanimous)", f"{unanimous_count(events)}/{len(events)}")
        _callouts(events, _fmt_ranking)
        df = pd.DataFrame([
            {
                "Group": ec.label,
                "Most shared": _frac(ec),
                "Most common standings": _fmt_ranking(ec.top_value),
            }
            for ec in events
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── Tab fasi knockout ──────────────────────────────────────────────────────────

for tab_idx, (phase_keys, phase_label) in enumerate(KNOCKOUT_PHASES, 1):
    with tabs[tab_idx]:
        st.subheader(f"Consensus — {phase_label}")
        st.caption(
            "One event = one match slot. Metric: **who advances** (chi passa il turno)."
        )

        match_ids = [mid for pk in phase_keys for mid in ko_ids.get(pk, [])]
        if not match_ids:
            st.info("No matches defined for this phase yet.")
            continue

        adv_events = knockout_consensus(participants, match_ids, "advances")

        if not adv_events:
            st.info("We need at least 2 players who've picked who advances in the same match.")
            continue

        st.metric(
            "Who-advances picks everyone agrees on",
            f"{unanimous_count(adv_events)}/{len(adv_events)}",
        )

        top = most_shared(adv_events)
        bottom = least_shared(adv_events)
        c1, c2 = st.columns(2)
        with c1:
            st.success(
                f"🟢 **Crowd favourite: {slot_label(top.label, bracket)}** — {_frac(top)} agree"
                f"\n\nAdvances: {_advancing_team(top.label, top.top_value)}"
            )
        with c2:
            st.error(
                f"🔴 **Biggest squabble: {slot_label(bottom.label, bracket)}** — {_frac(bottom)} agree"
                f"\n\nAdvances: {_advancing_team(bottom.label, bottom.top_value)}"
            )

        df = pd.DataFrame([
            {
                "Slot": slot_label(ec.label, bracket),
                "Who-advances — most shared": _frac(ec),
                "Most common pick": _advancing_team(ec.label, ec.top_value),
            }
            for ec in adv_events
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("**Who advances — by player**")
        st.caption(
            "Le squadre che ciascun giocatore ha indicato come qualificate. "
            "Se il tabellone non è ancora popolato da API, si legge «Team 1 / Team 2»."
        )
        _advances_by_player(match_ids)
