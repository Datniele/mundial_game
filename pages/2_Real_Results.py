import streamlit as st

from src.storage.json_storage import (
    load_knockout_bracket,
    load_results,
    load_group_rankings,
    load_group_standings,
    load_rankings_source,
)
from src.models.tournament import get_knockout_slots
from src.scraper.live_refresh import (
    refresh_group_standings_from_api,
    refresh_knockout_results_from_api,
)

st.set_page_config(page_title="Real Results", page_icon="📡", layout="wide")
st.title("📡 Real Results")

st.caption(
    "All real data is pulled from API-Football and is **read-only** — it can't be edited by hand."
)


# ── Aggiornamento live all'apertura della pagina ────────────────────────────────
# Appena si apre la pagina si interroga l'API e si salvano classifiche e risultati,
# senza premere alcun tasto. Le chiamate sono cachate (TTL) così i numerosi rerun di
# Streamlit non superano il limite del free tier (10 req/min).

@st.cache_data(ttl=60, show_spinner="Refreshing group standings from API…")
def _auto_refresh_standings():
    return refresh_group_standings_from_api()


@st.cache_data(ttl=60, show_spinner="Refreshing knockout results from API…")
def _auto_refresh_results():
    return refresh_knockout_results_from_api()


standings_outcome = _auto_refresh_standings()
results_outcome = _auto_refresh_results()

knockout_slots = get_knockout_slots()
actual_rankings = load_group_rankings()
actual_standings = load_group_standings()
rankings_source = load_rankings_source()
results = load_results()

if st.button("🔄 Refresh now"):
    _auto_refresh_standings.clear()
    _auto_refresh_results.clear()
    st.rerun()

# ── Classifiche gironi — live da API ─────────────────────────────────────────────

st.subheader("Group standings — live from API")
st.caption("Auto-refreshed when you open this page · Source: API-Football")

if standings_outcome.status == "api":
    st.success("Auto-refreshed from API-Football. Fresh off the press! 📰")
elif standings_outcome.status == "default":
    st.info(standings_outcome.message)
elif standings_outcome.status == "partial":
    st.error(standings_outcome.message)
else:  # error
    st.error(
        f"{standings_outcome.message} "
        "Double-check the `API_FOOTBALL_KEY` environment variable and your connection."
    )

if actual_rankings:
    if rankings_source == "default":
        st.warning(
            "Heads up: these standings are just the **default fixture order** (not real results). "
            "The API came back empty-handed — refresh once the tournament is actually rolling."
        )

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

# ── Risultati knockout — live da API (sola lettura) ─────────────────────────────

st.subheader("Knockout-stage results — live from API")
st.caption("Scores and who advances are pulled from API-Football. Source of truth, no manual edits.")

if results_outcome.status == "api":
    st.success(results_outcome.message)
elif results_outcome.status == "default":
    st.info(results_outcome.message)
else:  # error
    st.error(
        f"{results_outcome.message} "
        "Double-check the `API_FOOTBALL_KEY` environment variable and your connection."
    )

PHASE_LABELS = {
    "sedicesimi": "Round of 32",
    "ottavi": "Round of 16",
    "quarti": "Quarter-finals",
    "semifinali": "Semi-finals",
    "finale_3posto": "Third-place play-off",
    "finale": "Final",
}

ko_bracket = load_knockout_bracket()


def _adv_team(entry: dict, advances) -> str:
    """Nome della squadra che passa il turno, o '—' se non determinato."""
    if advances == "home":
        return entry.get("home") or "Team 1"
    if advances == "away":
        return entry.get("away") or "Team 2"
    return "—"


for slot_cfg in knockout_slots:
    prefix = slot_cfg["prefix"]
    n_slots = slot_cfg["slots"]
    label = PHASE_LABELS.get(slot_cfg["phase"], slot_cfg["phase"])

    played_in_phase = sum(
        1 for i in range(1, n_slots + 1) if f"{prefix}{i:02d}" in results
    )

    with st.expander(f"{label} — {played_in_phase}/{n_slots} played", expanded=False):
        rows = []
        for i in range(1, n_slots + 1):
            match_id = f"{prefix}{i:02d}"
            entry = ko_bracket.get(match_id) or {}
            team1 = entry.get("home") or "Team 1"
            team2 = entry.get("away") or "Team 2"
            res = results.get(match_id)
            if res:
                score = f"{res.home_goals}–{res.away_goals}"
                advances = _adv_team(entry, res.advances)
            else:
                score = "—"
                advances = "—"
            rows.append(f"| {match_id} | {team1} | {score} | {team2} | {advances} |")

        st.markdown(
            "| ID | Team 1 | Score | Team 2 | Advances |\n"
            "|----|--------|:-----:|--------|----------|\n"
            + "\n".join(rows)
        )

st.divider()

# ── Riepilogo ──────────────────────────────────────────────────────────────────

st.subheader("Recap")

ranking_count = sum(1 for r in actual_rankings.values() if any(v for v in r))
c1, c2 = st.columns(2)
c1.metric("Groups with standings entered", f"{ranking_count} / 12")
c2.metric("Knockout matches with a result", len(results))
