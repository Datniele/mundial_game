import streamlit as st

from src.storage.json_storage import (
    load_knockout_bracket,
    load_results,
    load_group_rankings,
    load_group_standings,
    load_rankings_source,
    save_results,
    save_group_rankings,
    save_rankings_source,
)
from src.models.tournament import load_fixtures, get_knockout_slots
from src.scraper.live_refresh import refresh_group_standings_from_api

st.set_page_config(page_title="Real Results", page_icon="📡", layout="wide")
st.title("📡 Real Results")


# ── Aggiornamento live all'apertura della pagina ────────────────────────────────
# Appena si apre la pagina si interroga l'API e si salvano le classifiche, senza
# bisogno di premere alcun tasto. Il risultato è cachato (TTL) così i numerosi
# rerun di Streamlit non superano il limite del free tier (10 req/min).

@st.cache_data(ttl=60, show_spinner="Refreshing group standings from API…")
def _auto_refresh():
    return refresh_group_standings_from_api()


outcome = _auto_refresh()

_, groups = load_fixtures()
knockout_slots = get_knockout_slots()
actual_rankings = load_group_rankings()
actual_standings = load_group_standings()
rankings_source = load_rankings_source()
results = load_results()

# ── Esito aggiornamento via API ─────────────────────────────────────────────────

st.subheader("Group standings — live from API")
st.caption("Auto-refreshed when you open this page · Source: API-Football")

if outcome.status == "api":
    st.success("Auto-refreshed from API-Football. Fresh off the press! 📰")
elif outcome.status == "default":
    st.info(outcome.message)
elif outcome.status == "partial":
    st.error(outcome.message)
else:  # error
    st.error(
        f"{outcome.message} "
        "Double-check the `API_FOOTBALL_KEY` environment variable and your connection."
    )

if st.button("🔄 Refresh now"):
    _auto_refresh.clear()
    st.rerun()

# ── Riepilogo gironi caricati ──────────────────────────────────────────────────

if actual_rankings:
    st.divider()

    if rankings_source == "default":
        st.warning(
            "Heads up: these standings are just the **default fixture order** (not real results). "
            "The API came back empty-handed — refresh once the tournament is actually rolling."
        )

    source_label = {
        "api": "Source: API-Football",
        "default": "Source: default fixture order",
    }.get(rankings_source or "", "")

    st.subheader(f"Group standings loaded{'  ·  ' + source_label if source_label else ''}")

    group_ids = sorted(actual_rankings.keys())
    cols_per_row = 4
    for row_start in range(0, len(group_ids), cols_per_row):
        row_ids = group_ids[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, gid in zip(cols, row_ids):
            standing = actual_standings.get(gid)
            if standing:
                rows = "\n".join(
                    f"| {r['pos']} | {r['squadra'] or '—'} | {r['punti']} |"
                    for r in standing
                )
            else:
                # Fallback: solo posizioni (nessun punteggio disponibile)
                ranking = actual_rankings.get(gid, [])
                rows = "\n".join(
                    f"| {pos} | {team or '—'} | 0 |"
                    for pos, team in enumerate(ranking, 1)
                )
            col.markdown(
                f"**Group {gid}**\n\n"
                "| Pos | Team | Pts |\n"
                "|-----|------|-----|\n"
                + rows
            )

st.divider()

# ── Classifiche gironi (manuale) ───────────────────────────────────────────────

st.subheader("Group standings — manual entry")
st.caption("Type in the real final standings for each group (1st → 4th place).")

new_rankings: dict = {}

for group_id, group_teams in sorted(groups.items()):
    with st.expander(f"Group {group_id} — {', '.join(group_teams)}", expanded=False):
        existing = actual_rankings.get(group_id, [])
        while len(existing) < 4:
            existing.append(None)

        rank_cols = st.columns(4)
        labels = ["🥇 1st place", "🥈 2nd place", "🥉 3rd place", "4th place"]
        ranking = []
        for i, (col, label) in enumerate(zip(rank_cols, labels)):
            already_selected = {t for t in ranking if t is not None}
            options = ["—"] + [t for t in group_teams if t not in already_selected]
            current = existing[i] if i < len(existing) else None
            if current not in options:
                current = None
            idx = options.index(current) if current in options else 0
            val = col.selectbox(label, options=options, index=idx, key=f"rank_{group_id}_{i}")
            ranking.append(val if val != "—" else None)
        new_rankings[group_id] = ranking

if st.button("💾 Save group standings", type="primary"):
    save_group_rankings(new_rankings)
    save_rankings_source("manual")
    st.success("Group standings saved.")
    st.rerun()

st.divider()

# ── Risultati knockout (manuale) ───────────────────────────────────────────────

st.subheader("Knockout-stage results")
st.caption("Punch in the real scores for the knockout matches.")

PHASE_LABELS = {
    "sedicesimi": "Round of 32",
    "ottavi": "Round of 16",
    "quarti": "Quarter-finals",
    "semifinali": "Semi-finals",
    "finale_3posto": "Third-place play-off",
    "finale": "Final",
}

ko_bracket = load_knockout_bracket()

new_results: dict = {}

for slot_cfg in knockout_slots:
    prefix = slot_cfg["prefix"]
    n_slots = slot_cfg["slots"]
    label = PHASE_LABELS.get(slot_cfg["phase"], slot_cfg["phase"])

    with st.expander(label, expanded=False):
        h = st.columns([1, 3, 1, 0.5, 1, 3, 2.5, 1.5])
        h[0].markdown("**ID**")
        h[1].markdown("**Team 1**")
        h[2].markdown("**Goals**")
        h[3].markdown("")
        h[4].markdown("**Goals**")
        h[5].markdown("**Team 2**")
        h[6].markdown("**Advances**")
        h[7].markdown("**Played**")

        for i in range(1, n_slots + 1):
            match_id = f"{prefix}{i:02d}"
            existing = results.get(match_id)
            cols = st.columns([1, 3, 1, 0.5, 1, 3, 2.5, 1.5])
            cols[0].write(match_id)
            _entry = ko_bracket.get(match_id) or {}
            team1_label = _entry.get("home") or "Team 1"
            team2_label = _entry.get("away") or "Team 2"
            cols[1].text_input(
                "sq1", value=_entry.get("home") or "",
                key=f"sq1_{match_id}", label_visibility="collapsed",
            )
            g1 = cols[2].number_input(
                "g1", min_value=0, max_value=20,
                value=existing.home_goals if existing else 0,
                step=1, key=f"g1_{match_id}", label_visibility="collapsed",
            )
            cols[3].write("–")
            g2 = cols[4].number_input(
                "g2", min_value=0, max_value=20,
                value=existing.away_goals if existing else 0,
                step=1, key=f"g2_{match_id}", label_visibility="collapsed",
            )
            cols[5].text_input(
                "sq2", value=_entry.get("away") or "",
                key=f"sq2_{match_id}", label_visibility="collapsed",
            )
            adv_opts = [team1_label, team2_label]
            existing_adv = existing.advances if existing else None
            adv_idx = (0 if existing_adv == "home" else 1) if existing_adv in ("home", "away") else None
            sel_adv = cols[6].radio(
                "Advances", adv_opts, index=adv_idx,
                key=f"adv_{match_id}", horizontal=True, label_visibility="collapsed",
            )
            adv_value = "home" if sel_adv == team1_label else ("away" if sel_adv == team2_label else None)
            played = cols[7].checkbox(
                "Played", value=bool(existing), key=f"played_{match_id}"
            )
            if played:
                new_results[match_id] = {
                    "home_goals": int(g1),
                    "away_goals": int(g2),
                    "played": True,
                    "advances": adv_value,
                }

if st.button("💾 Save knockout results", type="primary"):
    save_results(new_results)
    st.success("Knockout results saved.")
    st.rerun()

st.divider()

# ── Riepilogo ──────────────────────────────────────────────────────────────────

st.subheader("Recap")

ranking_count = sum(1 for r in actual_rankings.values() if any(v for v in r))
c1, c2 = st.columns(2)
c1.metric("Groups with standings entered", f"{ranking_count} / 12")
c2.metric("Knockout matches with a result", len(results))
