import streamlit as st

from src.models.participant import Participant
from src.models.match import MatchPrediction
from src.models.tournament import load_fixtures, get_knockout_slots, get_knockout_match_ids_by_phase
from src.storage.json_storage import (
    is_phase_locked,
    load_knockout_bracket,
    load_participant,
    load_registry,
    merge_participant,
    register_participant,
    update_registry_timestamp,
)

st.set_page_config(page_title="Make Your Predictions", page_icon="⚽", layout="wide")
st.title("⚽ Make Your Predictions")

# ── Registrazione ──────────────────────────────────────────────────────────────

st.subheader("Who are you?")

registry = load_registry()
known_names = sorted(p["name"] for p in registry.get("participants", []))

NEW_OPTION = "➕ New player"
options = ["—"] + known_names + [NEW_OPTION]
choice = st.selectbox("Pick your name", options=options, index=0)

if choice == "—":
    st.info("Pick your name to get the ball rolling.")
    st.stop()

if choice == NEW_OPTION:
    raw_name = st.text_input("First and last name", placeholder="e.g. John Smith")
    if not raw_name.strip():
        st.info("Drop your name in here to get started.")
        st.stop()
    name = raw_name.strip().title()
else:
    name = choice

participant = load_participant(name) or Participant(name=name)

if name not in set(known_names):
    register_participant(name)
    st.success(f"Welcome aboard, **{name}** — you're officially in the game!")
else:
    st.info(f"Look who's back: **{name}**. 👋")

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

PHASES = ["Groups", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]

PHASE_TO_INTERNAL: dict[str, list[str]] = {
    "Round of 32": ["sedicesimi"],
    "Round of 16": ["ottavi"],
    "Quarter-finals": ["quarti"],
    "Semi-finals": ["semifinali"],
    "Final": ["finale_3posto", "finale"],
}


def _phase_filled(p: Participant, phase_name: str) -> bool:
    """True if the player has already saved at least one prediction for the given phase."""
    if phase_name == "Groups":
        return bool(p.group_rankings) and any(
            any(v is not None for v in r) for r in p.group_rankings.values()
        )
    internal = PHASE_TO_INTERNAL.get(phase_name, [])
    ids = [mid for ip in internal for mid in ko_match_ids.get(ip, [])]
    return any(mid in p.match_predictions for mid in ids)


phase = st.radio("Which phase are we filling in?", PHASES, horizontal=True)

# Blocco admin: se la fase è bloccata i pronostici non sono più modificabili
if is_phase_locked(phase):
    st.error(
        f"🔒 Predictions for **{phase}** are locked. The deadline has passed — "
        "no more changes for this phase."
    )
    st.stop()

# Prerequisito: la fase precedente deve essere compilata
phase_idx = PHASES.index(phase)
if phase_idx > 0:
    prev_phase = PHASES[phase_idx - 1]
    if not _phase_filled(participant, prev_phase):
        st.warning(
            f"Whoa, not so fast! Before tackling **{phase}**, you need to save your **{prev_phase}** picks first."
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
            mid: MatchPrediction(
                match_id=mid,
                home_goals=v["home_goals"],
                away_goals=v["away_goals"],
                advances=v.get("advances"),
            )
            for mid, v in new_preds.items()
        },
    )
    merge_participant(updated)
    update_registry_timestamp(name)


# ── GIRONI ─────────────────────────────────────────────────────────────────────

if phase == "Groups":
    st.subheader("Final group standings")
    st.caption("Rank the 4 teams in each group, from top dog to wooden spoon.")

    new_rankings: dict = {}

    for group_id, group_teams in sorted(groups.items()):
        with st.expander(f"Group {group_id} — {', '.join(group_teams)}", expanded=False):
            existing_rank = participant.group_rankings.get(group_id, [])
            while len(existing_rank) < 4:
                existing_rank.append(None)

            rank_cols = st.columns(4)
            labels = ["🥇 1st place", "🥈 2nd place", "🥉 3rd place", "4th place"]
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

    if st.button("💾 Save Groups", type="primary"):
        _save_rankings(new_rankings)
        st.success("Group standings saved. Nicely done!")
        st.rerun()

# ── FASI A ELIMINAZIONE ────────────────────────────────────────────────────────

else:
    target_phases = PHASE_TO_INTERNAL[phase]
    slot_configs = [s for s in knockout_slots if s["phase"] in target_phases]

    st.subheader(f"Predictions — {phase}")
    st.caption(
        "Call the score for every clash. "
        "The qualified teams are worked out from your group-stage picks."
    )

    new_preds: dict = {}
    team_opts = ["TBD"] + all_teams
    bracket = load_knockout_bracket()

    for slot_cfg in slot_configs:
        prefix = slot_cfg["prefix"]
        n_slots = slot_cfg["slots"]
        phase_label = {
            "sedicesimi": "Round of 32",
            "ottavi": "Round of 16",
            "quarti": "Quarter-finals",
            "semifinali": "Semi-finals",
            "finale_3posto": "Third-place play-off",
            "finale": "Final",
        }.get(slot_cfg["phase"], slot_cfg["phase"])

        if len(slot_configs) > 1:
            st.markdown(f"**{phase_label}**")

        h = st.columns([3, 0.8, 0.5, 0.8, 3])
        h[0].markdown("**Team 1**")
        h[1].markdown("**Goals**")
        h[2].markdown("")
        h[3].markdown("**Goals**")
        h[4].markdown("**Team 2**")

        match_ids = [f"{prefix}{i:02d}" for i in range(1, n_slots + 1)]
        # Mostra in ordine cronologico se il bracket conosce le date; altrimenti ordine slot.
        match_ids.sort(key=lambda mid: (bracket.get(mid, {}).get("utc_date") or "", mid))

        for match_id in match_ids:
            pred = participant.match_predictions.get(match_id)
            home_g = pred.home_goals if pred else 0
            away_g = pred.away_goals if pred else 0
            entry = bracket.get(match_id)
            determined = bool(entry and entry.get("determined"))

            cols = st.columns([3, 0.8, 0.5, 0.8, 3])
            if determined:
                cols[0].markdown(f"**{entry['home']}**")
            else:
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
            if determined:
                cols[4].markdown(f"**{entry['away']}**")
            else:
                cols[4].selectbox(
                    f"t2_{match_id}", team_opts,
                    key=f"t2_{match_id}", label_visibility="collapsed",
                )
            # Riga 2: chi passa il turno (indipendente dal risultato)
            team1_label = entry["home"] if determined else "Team 1"
            team2_label = entry["away"] if determined else "Team 2"

            ctrl = st.columns([3, 0.8, 0.5, 0.8, 3])

            adv_opts = [team1_label, team2_label]
            adv_current = pred.advances if (pred and pred.advances) else None
            adv_idx = (0 if adv_current == "home" else 1) if adv_current in ("home", "away") else None
            sel_adv = ctrl[4].radio(
                "Passa il turno", adv_opts, index=adv_idx,
                key=f"adv_{match_id}", horizontal=True,
            )
            adv_value = None
            if sel_adv == team1_label:
                adv_value = "home"
            elif sel_adv == team2_label:
                adv_value = "away"

            new_preds[match_id] = {
                "home_goals": int(g1),
                "away_goals": int(g2),
                "advances": adv_value,   # "home"/"away" o None
            }

        if len(slot_configs) > 1:
            st.divider()

    if st.button(f"💾 Save {phase}", type="primary"):
        _save_knockout(new_preds)
        st.success(f"{phase} predictions saved. Fingers crossed! 🤞")
        st.rerun()

# ── Sommario copertura ─────────────────────────────────────────────────────────

st.divider()
st.subheader("Your predictions so far")

participant_updated = load_participant(name) or participant

ranking_count = sum(
    1 for r in participant_updated.group_rankings.values()
    if any(v is not None for v in r)
)
knockout_pred_count = len(participant_updated.match_predictions)

c1, c2 = st.columns(2)
c1.metric("Group standings", f"{ranking_count} / 12")
c2.metric("Knockout matches", str(knockout_pred_count))
