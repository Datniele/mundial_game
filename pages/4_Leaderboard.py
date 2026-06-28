import streamlit as st
import pandas as pd

from src.storage.json_storage import load_all_participants, load_results, load_group_rankings
from src.models.tournament import get_knockout_match_ids_by_phase
from src.scoring.calculator import score_group_stage, score_knockout_round
from src.scraper.live_refresh import refresh_group_standings_from_api

st.set_page_config(page_title="Leaderboard", page_icon="🏆", layout="wide")
st.title("🏆 Leaderboard")


# ── Aggiornamento live all'apertura della pagina ────────────────────────────────
# La classifica viene calcolata su dati freschi: appena si apre la pagina si
# interrogano le classifiche reali dall'API e si salvano su disco, prima di caricare
# i dati per lo scoring. Cachato con TTL per non superare il free tier (10 req/min).

@st.cache_data(ttl=60, show_spinner="Refreshing real results from API…")
def _auto_refresh():
    return refresh_group_standings_from_api()


_refresh = _auto_refresh()
if _refresh.status == "api":
    st.caption("✅ Real group standings auto-refreshed from API-Football.")
elif _refresh.status == "default":
    st.caption("ℹ️ API has no standings yet — scores use the default fixture order.")
elif _refresh.status == "partial":
    st.caption(f"⚠️ {_refresh.message}")
else:
    st.caption(f"⚠️ {_refresh.message}")

participants = load_all_participants()
results = load_results()
actual_group_rankings = load_group_rankings()


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

tabs = st.tabs(["Group Stage"] + [label for _, label in KNOCKOUT_PHASES])

# ── Tab Gironi ─────────────────────────────────────────────────────────────────

with tabs[0]:
    st.subheader("Leaderboard — Group Stage")
    st.caption("Score based on how far off your positions were across all groups. **Higher = better.**")

    group_participants = [
        p for p in participants
        if p.group_rankings and any(any(v is not None for v in r) for r in p.group_rankings.values())
    ]

    if not group_participants:
        st.info("No one has filled in the group standings yet.")
    elif not actual_group_rankings:
        st.warning("The real group results aren't in yet.")
        st.caption(
            f"{len(group_participants)} players have submitted picks: "
            + ", ".join(p.name for p in group_participants)
        )
    else:
        scores = score_group_stage(group_participants, actual_group_rankings)
        df = pd.DataFrame([
            {"Pos": i, "Player": s.name, "Score": round(s.score, 2)}
            for i, s in enumerate(scores, 1)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Group-by-group breakdown"):
            selected = st.selectbox("Player", [s.name for s in scores], key="gironi_sel")
            score = next(s for s in scores if s.name == selected)
            det_df = pd.DataFrame([
                {"Group": g, "Score": round((8 - e) / 9.6, 2)}
                for g, e in sorted(score.per_group.items())
            ])
            st.dataframe(det_df, use_container_width=True, hide_index=True)

# ── Tab fasi knockout ──────────────────────────────────────────────────────────

for tab_idx, (phase_keys, phase_label) in enumerate(KNOCKOUT_PHASES, 1):
    with tabs[tab_idx]:
        st.subheader(f"Leaderboard — {phase_label}")
        st.caption(
            "C1 = correct winners ↓ | C2 = exact scores ↓ (tiebreaker) | "
            "C3 = goal-difference error ↑ (tiebreaker). **Higher C1 = better.**"
        )

        match_ids = [mid for pk in phase_keys for mid in ko_ids.get(pk, [])]

        if not match_ids:
            st.info("No matches defined for this phase yet.")
            continue

        round_participants = [
            p for p in participants
            if any(mid in p.match_predictions for mid in match_ids)
        ]

        if not round_participants:
            st.info("No one has submitted predictions for this phase yet.")
            continue

        round_results = {mid: r for mid, r in results.items() if mid in match_ids}

        if not round_results:
            st.warning("The results for this phase aren't in yet.")
            st.caption(
                f"{len(round_participants)} players have submitted picks: "
                + ", ".join(p.name for p in round_participants)
            )
            continue

        scores = score_knockout_round(round_participants, results, match_ids)
        df = pd.DataFrame([
            {
                "Pos": i,
                "Player": s.name,
                "C1 — Who advances": s.correct_advances,
                "C2 — Exact scores": s.exact_scores,
                "C3 — Goal-diff error": s.goal_diff_error,
            }
            for i, s in enumerate(scores, 1)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
