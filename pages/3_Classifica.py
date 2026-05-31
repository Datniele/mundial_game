import streamlit as st
import pandas as pd

from src.storage.json_storage import load_all_participants, load_results, load_group_rankings
from src.models.tournament import load_fixtures
from src.scoring.calculator import calculate_scores

st.set_page_config(page_title="Classifica", page_icon="🏆", layout="wide")
st.title("🏆 Classifica")

participants = load_all_participants()
results = load_results()
matches, _ = load_fixtures()
group_rankings = load_group_rankings()

if not participants:
    st.info("Nessun partecipante caricato. Vai su **Carica Pronostici** per iniziare.")
    st.stop()

if not results:
    st.warning("Nessun risultato reale disponibile. Vai su **Risultati Reali** per aggiornare.")

if st.button("🔄 Ricalcola punteggi"):
    st.rerun()

# Calcolo punteggi
ranked = calculate_scores(participants, results, matches, group_rankings)

# --- Classifica generale ---
st.subheader("Classifica generale")

leaderboard = []
for i, p in enumerate(ranked, 1):
    leaderboard.append({
        "Pos": i,
        "Partecipante": p.name,
        "Punti Totali": p.total_score,
        "Partite pronosticate": len(p.match_predictions),
    })

df = pd.DataFrame(leaderboard)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- Dettaglio partecipante ---
st.subheader("Dettaglio punteggio")

selected = st.selectbox("Seleziona partecipante", [p.name for p in ranked])
participant = next(p for p in ranked if p.name == selected)

col1, col2 = st.columns(2)
with col1:
    st.metric("Punti totali", participant.total_score)
with col2:
    match_pts = sum(v for k, v in participant.score_breakdown.items() if not k.startswith("ranking_"))
    ranking_pts = sum(v for k, v in participant.score_breakdown.items() if k.startswith("ranking_"))
    st.metric("Di cui partite / classifiche", f"{match_pts} / {ranking_pts}")

# Breakdown partite
if participant.score_breakdown:
    rows = []
    for key, pts in sorted(participant.score_breakdown.items()):
        if key.startswith("ranking_"):
            group = key.replace("ranking_", "Girone ")
            pred = participant.group_rankings.get(key.replace("ranking_", ""), ["-", "-"])
            actual = group_rankings.get(key.replace("ranking_", ""), ["-", "-"])
            rows.append({
                "ID": key,
                "Tipo": "Classifica girone",
                "Pronostico": f"{pred[0]} / {pred[1]}" if len(pred) >= 2 else "-",
                "Reale": f"{actual[0]} / {actual[1]}" if len(actual) >= 2 else "?",
                "Punti": pts,
            })
        else:
            match = matches.get(key)
            pred = participant.match_predictions.get(key)
            real = results.get(key)
            rows.append({
                "ID": key,
                "Tipo": "Partita",
                "Pronostico": f"{pred.home_goals}-{pred.away_goals}" if pred else "-",
                "Reale": f"{real.home_goals}-{real.away_goals}" if real else "?",
                "Punti": pts,
            })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
