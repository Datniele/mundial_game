import streamlit as st
import json
from src.storage.json_storage import load_results, save_results, save_group_rankings, load_group_rankings
from src.models.tournament import load_fixtures

st.set_page_config(page_title="Risultati Reali", page_icon="📡", layout="wide")
st.title("📡 Risultati Reali")

matches, groups = load_fixtures()
results = load_results()

# --- Scraping ---
st.subheader("Aggiorna risultati via scraping")
scraper_url = st.text_input("URL sito sorgente", placeholder="https://...")

if st.button("🔄 Scarica risultati", disabled=not scraper_url):
    try:
        from src.scraper.results_scraper import scrape_results, scrape_group_rankings
        with st.spinner("Scraping in corso..."):
            new_results = scrape_results(scraper_url)
            new_rankings = scrape_group_rankings(scraper_url)
        save_results(new_results)
        save_group_rankings(new_rankings)
        st.success(f"Aggiornati {len(new_results)} risultati e {len(new_rankings)} classifiche gironi.")
        st.rerun()
    except NotImplementedError:
        st.warning("Scraper non ancora implementato. Inserisci i risultati manualmente qui sotto.")
    except Exception as e:
        st.error(f"Errore durante lo scraping: {e}")

st.divider()

# --- Inserimento manuale ---
st.subheader("Inserimento manuale risultati")

with st.expander("Inserisci/modifica risultati partite", expanded=False):
    raw_results = {}
    if st.session_state.get("manual_results_json"):
        raw_results = json.loads(st.session_state["manual_results_json"])

    group_filter = st.selectbox("Filtra per girone", ["Tutti"] + sorted(groups.keys()))

    for mid, match in sorted(matches.items()):
        if group_filter != "Tutti" and match.group != group_filter:
            continue

        existing = results.get(mid)
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
        with col1:
            st.write(f"**{mid}** — {match.home_team} vs {match.away_team}")
        with col2:
            g1 = st.number_input("Gol Casa", min_value=0, max_value=20,
                                  value=existing.home_goals if existing else 0,
                                  key=f"g1_{mid}")
        with col3:
            g2 = st.number_input("Gol Ospite", min_value=0, max_value=20,
                                  value=existing.away_goals if existing else 0,
                                  key=f"g2_{mid}")
        with col4:
            played = st.checkbox("Giocata", value=bool(existing), key=f"played_{mid}")
        with col5:
            st.write("")

        if played:
            raw_results[mid] = {"home_goals": g1, "away_goals": g2, "played": True}

    if st.button("💾 Salva risultati manuali"):
        save_results(raw_results)
        st.success("Risultati salvati.")
        st.rerun()

st.divider()

# --- Riepilogo ---
st.subheader("Partite giocate")
played = {mid: r for mid, r in results.items()}
st.metric("Partite con risultato", len(played))

if played:
    import pandas as pd
    rows = []
    for mid, r in sorted(played.items()):
        m = matches.get(mid)
        if m:
            rows.append({
                "ID": mid,
                "Girone": m.group or "-",
                "Casa": m.home_team,
                "Gol": f"{r.home_goals} - {r.away_goals}",
                "Ospite": m.away_team,
            })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
