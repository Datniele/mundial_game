import streamlit as st

from src.storage.json_storage import (
    load_results,
    load_group_rankings,
    load_rankings_source,
    save_results,
    save_group_rankings,
    save_rankings_source,
)
from src.models.tournament import load_fixtures, get_knockout_slots

st.set_page_config(page_title="Risultati Reali", page_icon="📡", layout="wide")
st.title("📡 Risultati Reali")

_, groups = load_fixtures()
knockout_slots = get_knockout_slots()
actual_rankings = load_group_rankings()
rankings_source = load_rankings_source()
results = load_results()

# ── Scraping via API-Football ──────────────────────────────────────────────────

st.subheader("Aggiorna classifiche gironi via API")
st.caption("Fonte: API-Football (api-sports.io)")

run_scrape = st.button("🔄 Scarica classifiche da API-Football")

if run_scrape:
    from src.scraper.results_scraper import scrape_group_rankings, DefaultRankingsUsed
    with st.spinner("Download classifiche in corso…"):
        try:
            scraped = scrape_group_rankings()
            missing = [g for g in "ABCDEFGHIJKL" if g not in scraped]
            if missing:
                st.error(
                    f"Dati parziali: gironi mancanti {', '.join(missing)}. "
                    "Nessun dato salvato — verifica che il torneo sia in corso "
                    "e che la chiave API sia valida."
                )
            else:
                save_group_rankings(scraped)
                save_rankings_source("api")
                st.session_state["scrape_done"] = True
                st.success("Classifiche aggiornate per tutti i 12 gironi.")
                st.rerun()
        except DefaultRankingsUsed as e:
            save_group_rankings(e.rankings)
            save_rankings_source("default")
            st.session_state["scrape_done"] = True
            st.rerun()
        except Exception as e:
            st.error(
                f"Download fallito: {e}. "
                "Controlla la variabile d'ambiente `API_FOOTBALL_KEY` e la connessione."
            )

# ── Riepilogo gironi caricati ──────────────────────────────────────────────────

if actual_rankings and st.session_state.get("scrape_done"):
    st.divider()

    if rankings_source == "default":
        st.warning(
            "Le classifiche mostrate sono l'**ordine standard da calendario** (non risultati reali). "
            "L'API non ha restituito dati — aggiorna quando il torneo è in corso."
        )

    source_label = {
        "api": "Fonte: API-Football",
        "default": "Fonte: ordine standard da calendario",
    }.get(rankings_source or "", "")

    st.subheader(f"Classifiche gironi caricate{'  ·  ' + source_label if source_label else ''}")

    group_ids = sorted(actual_rankings.keys())
    cols_per_row = 4
    for row_start in range(0, len(group_ids), cols_per_row):
        row_ids = group_ids[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, gid in zip(cols, row_ids):
            ranking = actual_rankings.get(gid, [])
            rows = "\n".join(
                f"| {pos}° | {team or '—'} | 0 |"
                for pos, team in enumerate(ranking, 1)
            )
            col.markdown(
                f"**Girone {gid}**\n\n"
                "| Pos | Squadra | Pt |\n"
                "|-----|---------|----|\n"
                + rows
            )

st.divider()

# ── Classifiche gironi (manuale) ───────────────────────────────────────────────

st.subheader("Classifiche gironi — inserimento manuale")
st.caption("Inserisci la classifica finale reale di ogni girone (1° → 4° posto).")

new_rankings: dict = {}

for group_id, group_teams in sorted(groups.items()):
    with st.expander(f"Girone {group_id} — {', '.join(group_teams)}", expanded=False):
        existing = actual_rankings.get(group_id, [])
        while len(existing) < 4:
            existing.append(None)

        rank_cols = st.columns(4)
        labels = ["🥇 1° posto", "🥈 2° posto", "🥉 3° posto", "4° posto"]
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

if st.button("💾 Salva classifiche gironi", type="primary"):
    save_group_rankings(new_rankings)
    save_rankings_source("manual")
    st.success("Classifiche gironi salvate.")
    st.rerun()

st.divider()

# ── Risultati knockout (manuale) ───────────────────────────────────────────────

st.subheader("Risultati fase a eliminazione")
st.caption("Inserisci i risultati reali delle partite knockout.")

PHASE_LABELS = {
    "sedicesimi": "Sedicesimi di finale",
    "ottavi": "Ottavi di finale",
    "quarti": "Quarti di finale",
    "semifinali": "Semifinali",
    "finale_3posto": "Finale 3° posto",
    "finale": "Finale",
}

new_results: dict = {}

for slot_cfg in knockout_slots:
    prefix = slot_cfg["prefix"]
    n_slots = slot_cfg["slots"]
    label = PHASE_LABELS.get(slot_cfg["phase"], slot_cfg["phase"])

    with st.expander(label, expanded=False):
        h = st.columns([1, 3, 1, 0.5, 1, 3, 2])
        h[0].markdown("**ID**")
        h[1].markdown("**Squadra 1**")
        h[2].markdown("**Gol**")
        h[3].markdown("")
        h[4].markdown("**Gol**")
        h[5].markdown("**Squadra 2**")
        h[6].markdown("**Giocata**")

        for i in range(1, n_slots + 1):
            match_id = f"{prefix}{i:02d}"
            existing = results.get(match_id)
            cols = st.columns([1, 3, 1, 0.5, 1, 3, 2])
            cols[0].write(match_id)
            cols[1].text_input("sq1", value="", key=f"sq1_{match_id}", label_visibility="collapsed")
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
            cols[5].text_input("sq2", value="", key=f"sq2_{match_id}", label_visibility="collapsed")
            played = cols[6].checkbox(
                "Giocata", value=bool(existing), key=f"played_{match_id}"
            )
            if played:
                new_results[match_id] = {"home_goals": int(g1), "away_goals": int(g2), "played": True}

if st.button("💾 Salva risultati knockout", type="primary"):
    save_results(new_results)
    st.success("Risultati knockout salvati.")
    st.rerun()

st.divider()

# ── Riepilogo ──────────────────────────────────────────────────────────────────

st.subheader("Riepilogo")

ranking_count = sum(1 for r in actual_rankings.values() if any(v for v in r))
c1, c2 = st.columns(2)
c1.metric("Gironi con classifica inserita", f"{ranking_count} / 12")
c2.metric("Partite knockout con risultato", len(results))
