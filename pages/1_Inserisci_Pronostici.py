import streamlit as st

from src.models.participant import Participant
from src.models.match import MatchPrediction
from src.models.tournament import load_fixtures, get_knockout_slots, get_knockout_match_ids_by_phase
from src.storage.json_storage import (
    load_participant,
    load_registry,
    merge_participant,
    register_participant,
    update_registry_timestamp,
)

st.set_page_config(page_title="Inserisci Pronostici", page_icon="⚽", layout="wide")
st.title("⚽ Inserisci i tuoi Pronostici")

# ── Registrazione ──────────────────────────────────────────────────────────────

st.subheader("Chi sei?")
raw_name = st.text_input("Nome e Cognome", placeholder="es. Mario Rossi")

if not raw_name.strip():
    st.info("Inserisci il tuo nome per iniziare.")
    st.stop()

name = raw_name.strip().title()
participant = load_participant(name) or Participant(name=name)

registry = load_registry()
known = {p["name"] for p in registry.get("participants", [])}
if name not in known:
    register_participant(name)
    st.success(f"Benvenuto **{name}** — sei stato registrato!")
else:
    st.info(f"Bentornato **{name}**.")

# ── Fixtures ───────────────────────────────────────────────────────────────────


@st.cache_data
def _fixtures():
    _, groups = load_fixtures()
    slots = get_knockout_slots()
    all_teams = sorted({t for teams in groups.values() for t in teams})
    return groups, slots, all_teams


@st.cache_data
def _ko_ids() -> dict:
    return get_knockout_match_ids_by_phase()


groups, knockout_slots, all_teams = _fixtures()
ko_match_ids = _ko_ids()

# ── Selettore fase ─────────────────────────────────────────────────────────────

PHASES = ["Gironi", "Sedicesimi", "Ottavi", "Quarti", "Semifinali", "Finale"]

PHASE_TO_INTERNAL: dict[str, list[str]] = {
    "Sedicesimi": ["sedicesimi"],
    "Ottavi": ["ottavi"],
    "Quarti": ["quarti"],
    "Semifinali": ["semifinali"],
    "Finale": ["finale_3posto", "finale"],
}


def _phase_filled(p: Participant, phase_name: str) -> bool:
    """True se il partecipante ha già salvato almeno un pronostico per la fase data."""
    if phase_name == "Gironi":
        return bool(p.group_rankings) and any(
            any(v is not None for v in r) for r in p.group_rankings.values()
        )
    internal = PHASE_TO_INTERNAL.get(phase_name, [])
    ids = [mid for ip in internal for mid in ko_match_ids.get(ip, [])]
    return any(mid in p.match_predictions for mid in ids)


phase = st.radio("Fase da compilare", PHASES, horizontal=True)

# Prerequisito: la fase precedente deve essere compilata
phase_idx = PHASES.index(phase)
if phase_idx > 0:
    prev_phase = PHASES[phase_idx - 1]
    if not _phase_filled(participant, prev_phase):
        st.warning(
            f"Per compilare **{phase}** devi prima salvare i pronostici di **{prev_phase}**."
        )
        st.stop()

st.divider()

# ── Helper ─────────────────────────────────────────────────────────────────────


def _save_rankings(new_rankings: dict) -> None:
    updated = Participant(name=name)
    updated.group_rankings = new_rankings
    merge_participant(updated)
    update_registry_timestamp(name)


def _save_knockout(new_preds: dict) -> None:
    updated = Participant(
        name=name,
        match_predictions={
            mid: MatchPrediction(match_id=mid, home_goals=v["home_goals"], away_goals=v["away_goals"])
            for mid, v in new_preds.items()
        },
    )
    merge_participant(updated)
    update_registry_timestamp(name)


# ── GIRONI ─────────────────────────────────────────────────────────────────────

if phase == "Gironi":
    st.subheader("Classifica finale dei gironi")
    st.caption("Ordina le 4 squadre di ogni girone dalla prima all'ultima classificata.")

    new_rankings: dict = {}

    for group_id, group_teams in sorted(groups.items()):
        with st.expander(f"Girone {group_id} — {', '.join(group_teams)}", expanded=False):
            existing_rank = participant.group_rankings.get(group_id, [])
            while len(existing_rank) < 4:
                existing_rank.append(None)

            rank_cols = st.columns(4)
            labels = ["🥇 1° posto", "🥈 2° posto", "🥉 3° posto", "4° posto"]
            ranking = []
            for i, (col, label) in enumerate(zip(rank_cols, labels)):
                already_selected = {t for t in ranking if t is not None}
                options = ["—"] + [t for t in group_teams if t not in already_selected]
                current = existing_rank[i] if i < len(existing_rank) else None
                if current not in options:
                    current = None
                idx = options.index(current) if current in options else 0
                val = col.selectbox(label, options=options, index=idx, key=f"rank_{group_id}_{i}")
                ranking.append(val if val != "—" else None)
            new_rankings[group_id] = ranking

    if st.button("💾 Salva Gironi", type="primary"):
        _save_rankings(new_rankings)
        st.success("Classifiche gironi salvate correttamente.")
        st.rerun()

# ── FASI A ELIMINAZIONE ────────────────────────────────────────────────────────

else:
    target_phases = PHASE_TO_INTERNAL[phase]
    slot_configs = [s for s in knockout_slots if s["phase"] in target_phases]

    st.subheader(f"Pronostici — {phase}")
    st.caption(
        "Inserisci il risultato previsto per ogni sfida. "
        "Le squadre qualificate vengono derivate dai pronostici sui gironi."
    )

    new_preds: dict = {}
    team_opts = ["Da definire"] + all_teams

    for slot_cfg in slot_configs:
        prefix = slot_cfg["prefix"]
        n_slots = slot_cfg["slots"]
        phase_label = {
            "sedicesimi": "Sedicesimi di finale",
            "ottavi": "Ottavi di finale",
            "quarti": "Quarti di finale",
            "semifinali": "Semifinali",
            "finale_3posto": "Finale 3° posto",
            "finale": "Finale",
        }.get(slot_cfg["phase"], slot_cfg["phase"])

        if len(slot_configs) > 1:
            st.markdown(f"**{phase_label}**")

        h = st.columns([3, 0.8, 0.5, 0.8, 3])
        h[0].markdown("**Squadra 1**")
        h[1].markdown("**Gol**")
        h[2].markdown("")
        h[3].markdown("**Gol**")
        h[4].markdown("**Squadra 2**")

        for i in range(1, n_slots + 1):
            match_id = f"{prefix}{i:02d}"
            pred = participant.match_predictions.get(match_id)
            home_g = pred.home_goals if pred else 0
            away_g = pred.away_goals if pred else 0

            cols = st.columns([3, 0.8, 0.5, 0.8, 3])
            cols[0].selectbox(
                f"t1_{match_id}", team_opts,
                key=f"t1_{match_id}", label_visibility="collapsed",
            )
            g1 = cols[1].number_input(
                f"g1_{match_id}", min_value=0, max_value=20, value=home_g, step=1,
                key=f"g1_{match_id}", label_visibility="collapsed",
            )
            cols[2].write("–")
            g2 = cols[3].number_input(
                f"g2_{match_id}", min_value=0, max_value=20, value=away_g, step=1,
                key=f"g2_{match_id}", label_visibility="collapsed",
            )
            cols[4].selectbox(
                f"t2_{match_id}", team_opts,
                key=f"t2_{match_id}", label_visibility="collapsed",
            )
            new_preds[match_id] = {"home_goals": int(g1), "away_goals": int(g2)}

        if len(slot_configs) > 1:
            st.divider()

    if st.button(f"💾 Salva {phase}", type="primary"):
        _save_knockout(new_preds)
        st.success(f"Pronostici {phase} salvati correttamente.")
        st.rerun()

# ── Sommario copertura ─────────────────────────────────────────────────────────

st.divider()
st.subheader("Riepilogo pronostici inseriti")

participant_updated = load_participant(name) or participant

ranking_count = sum(
    1 for r in participant_updated.group_rankings.values()
    if any(v is not None for v in r)
)
knockout_pred_count = len(participant_updated.match_predictions)

c1, c2 = st.columns(2)
c1.metric("Classifiche gironi", f"{ranking_count} / 12")
c2.metric("Partite knockout", str(knockout_pred_count))
