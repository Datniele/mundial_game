import streamlit as st
import pandas as pd

from src.storage.json_storage import load_all_participants
from src.models.match import Outcome
from src.models.tournament import get_knockout_match_ids_by_phase
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

_OUTCOME_LABEL = {
    Outcome.HOME: "1 (home win)",
    Outcome.AWAY: "2 (away win)",
    Outcome.DRAW: "X (draw)",
}


def _fmt_ranking(value) -> str:
    return " › ".join(value)


def _fmt_outcome(value) -> str:
    return _OUTCOME_LABEL.get(value, str(value))


def _fmt_score(value) -> str:
    return f"{value[0]}-{value[1]}"


def _frac(ec: EventConsensus) -> str:
    return f"{ec.top_count}/{ec.total}"


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
            "One event = one match slot. Two metrics: **outcome** (1/X/2) and **exact score**."
        )

        match_ids = [mid for pk in phase_keys for mid in ko_ids.get(pk, [])]
        if not match_ids:
            st.info("No matches defined for this phase yet.")
            continue

        outcome_events = knockout_consensus(participants, match_ids, "outcome")
        exact_events = knockout_consensus(participants, match_ids, "exact")

        if not outcome_events:
            st.info("We need at least 2 players who've predicted the same match.")
            continue

        m1, m2 = st.columns(2)
        m1.metric("Outcomes everyone agrees on", f"{unanimous_count(outcome_events)}/{len(outcome_events)}")
        m2.metric(
            "Exact scores everyone agrees on",
            f"{unanimous_count(exact_events)}/{len(exact_events)}",
        )

        st.markdown("**Outcome (1/X/2)**")
        _callouts(outcome_events, _fmt_outcome)
        st.markdown("**Exact score**")
        _callouts(exact_events, _fmt_score)

        exact_by_label = {ec.label: ec for ec in exact_events}
        df = pd.DataFrame([
            {
                "Slot": o.label,
                "Outcome — most shared": _frac(o),
                "Most common outcome": _fmt_outcome(o.top_value),
                "Score — most shared": _frac(exact_by_label[o.label]),
                "Most common score": _fmt_score(exact_by_label[o.label].top_value),
            }
            for o in outcome_events
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
