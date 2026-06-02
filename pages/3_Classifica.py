import streamlit as st
import pandas as pd

from src.storage.json_storage import load_all_participants, load_results, load_group_rankings
from src.models.tournament import get_knockout_match_ids_by_phase
from src.scoring.calculator import score_group_stage, score_knockout_round

st.set_page_config(page_title="Classifica", page_icon="🏆", layout="wide")
st.title("🏆 Classifica")

participants = load_all_participants()
results = load_results()
actual_group_rankings = load_group_rankings()


@st.cache_data
def _ko_ids() -> dict:
    return get_knockout_match_ids_by_phase()


ko_ids = _ko_ids()

if not participants:
    st.info("Nessun partecipante. Vai su **Inserisci Pronostici** per iniziare.")
    st.stop()

KNOCKOUT_PHASES = [
    (["sedicesimi"], "Sedicesimi"),
    (["ottavi"], "Ottavi"),
    (["quarti"], "Quarti"),
    (["semifinali"], "Semifinali"),
    (["finale_3posto", "finale"], "Finale"),
]

tabs = st.tabs(["Fase Gironi"] + [label for _, label in KNOCKOUT_PHASES])

# ── Tab Gironi ─────────────────────────────────────────────────────────────────

with tabs[0]:
    st.subheader("Classifica — Fase Gironi")
    st.caption("Errore = somma degli scarti di posizione su tutti i gironi. **Più basso = meglio.**")

    group_participants = [
        p for p in participants
        if p.group_rankings and any(any(v is not None for v in r) for r in p.group_rankings.values())
    ]

    if not group_participants:
        st.info("Nessun partecipante ha ancora inserito le classifiche dei gironi.")
    elif not actual_group_rankings:
        st.warning("I risultati dei gironi non sono ancora disponibili.")
        st.caption(
            f"{len(group_participants)} partecipanti hanno compilato: "
            + ", ".join(p.name for p in group_participants)
        )
    else:
        scores = score_group_stage(group_participants, actual_group_rankings)
        df = pd.DataFrame([
            {"Pos": i, "Partecipante": s.name, "Errore totale": s.total_error}
            for i, s in enumerate(scores, 1)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Dettaglio per girone"):
            selected = st.selectbox("Partecipante", [s.name for s in scores], key="gironi_sel")
            score = next(s for s in scores if s.name == selected)
            det_df = pd.DataFrame([
                {"Girone": g, "Errore": e}
                for g, e in sorted(score.per_group.items())
            ])
            st.dataframe(det_df, use_container_width=True, hide_index=True)

# ── Tab fasi knockout ──────────────────────────────────────────────────────────

for tab_idx, (phase_keys, phase_label) in enumerate(KNOCKOUT_PHASES, 1):
    with tabs[tab_idx]:
        st.subheader(f"Classifica — {phase_label}")
        st.caption(
            "C1 = vincitori corretti ↓ | C2 = risultati esatti ↓ (spareggio) | "
            "C3 = errore differenza reti ↑ (spareggio). **C1 più alto = meglio.**"
        )

        match_ids = [mid for pk in phase_keys for mid in ko_ids.get(pk, [])]

        if not match_ids:
            st.info("Nessuna partita definita per questa fase.")
            continue

        round_participants = [
            p for p in participants
            if any(mid in p.match_predictions for mid in match_ids)
        ]

        if not round_participants:
            st.info("Nessun partecipante ha ancora inserito i pronostici per questa fase.")
            continue

        round_results = {mid: r for mid, r in results.items() if mid in match_ids}

        if not round_results:
            st.warning("I risultati di questa fase non sono ancora disponibili.")
            st.caption(
                f"{len(round_participants)} partecipanti hanno compilato: "
                + ", ".join(p.name for p in round_participants)
            )
            continue

        scores = score_knockout_round(round_participants, results, match_ids)
        df = pd.DataFrame([
            {
                "Pos": i,
                "Partecipante": s.name,
                "C1 — Vincitori corretti": s.correct_winners,
                "C2 — Risultati esatti": s.exact_scores,
                "C3 — Errore diff. reti": s.goal_diff_error,
            }
            for i, s in enumerate(scores, 1)
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
