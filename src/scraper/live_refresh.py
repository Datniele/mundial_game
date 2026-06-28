"""
Aggiornamento "live" delle classifiche gironi dall'API.

Funzione pensata per essere chiamata all'apertura di una pagina Streamlit: scarica
le classifiche da football-data.org e le salva su disco, restituendo un riepilogo
dell'esito (senza dipendere da Streamlit). Le pagine la avvolgono con
`st.cache_data(ttl=...)` così che i frequenti rerun di Streamlit non superino il
limite del free tier (10 richieste/minuto).
"""

from dataclasses import dataclass
from typing import List, Optional

from src.scraper.results_scraper import scrape_group_data, DefaultRankingsUsed
from src.storage.json_storage import (
    save_group_rankings,
    save_group_standings,
    save_rankings_source,
)
from src.models.tournament import get_knockout_slots
from src.scraper.knockout_bracket import fetch_matches, build_phase_bracket
from src.storage.json_storage import merge_knockout_bracket

_ALL_GROUPS = "ABCDEFGHIJKL"


@dataclass
class RefreshOutcome:
    """Esito di un tentativo di aggiornamento live delle classifiche gironi."""
    status: str            # "api" | "default" | "partial" | "error"
    message: str
    missing: Optional[List[str]] = None


def refresh_group_standings_from_api() -> RefreshOutcome:
    """
    Scarica le classifiche gironi dall'API e le salva su disco.

    Non solleva eccezioni: ogni caso (successo, fallback all'ordine standard, dati
    parziali, errore) viene tradotto in un `RefreshOutcome`, così la pagina può
    decidere come comunicarlo senza gestire i singoli errori.
    """
    try:
        scraped, standings = scrape_group_data()
        missing = [g for g in _ALL_GROUPS if g not in scraped]
        if missing:
            # Dati parziali: non salviamo nulla per non corrompere le classifiche.
            return RefreshOutcome(
                status="partial",
                message=f"Partial data from the API — missing groups {', '.join(missing)}. "
                        "Nothing was saved.",
                missing=missing,
            )
        save_group_rankings(scraped)
        save_group_standings(standings)
        save_rankings_source("api")
        return RefreshOutcome(status="api", message="Group standings refreshed from API-Football.")
    except DefaultRankingsUsed as e:
        # Torneo non iniziato o API senza standings: si usa l'ordine standard da fixtures.
        save_group_rankings(e.rankings)
        save_group_standings(e.standings)
        save_rankings_source("default")
        return RefreshOutcome(
            status="default",
            message="The API has no standings yet — using the default fixture order.",
        )
    except Exception as e:  # noqa: BLE001 — qualsiasi errore va riportato alla pagina
        return RefreshOutcome(status="error", message=f"Live refresh failed: {e}")


def refresh_knockout_bracket_from_api(phase: str) -> RefreshOutcome:
    """Scarica gli accoppiamenti di UNA fase knockout e li salva (merge) su disco.

    Salva solo se tutti gli accoppiamenti della fase sono determinati; altrimenti
    avvisa senza scrivere nulla. Non solleva eccezioni: ogni errore diventa un
    RefreshOutcome di stato "error".
    """
    try:
        payload = fetch_matches()
        bracket = build_phase_bracket(payload, phase)
        if not bracket:
            return RefreshOutcome(
                status="error",
                message="The API has no matches for this phase yet — nothing saved.",
            )
        # Salva solo il bracket COMPLETO della fase: se l'API ne restituisce solo una
        # parte (slot mancanti), non popolare per non lasciare slot misti reale/TBD.
        expected = next((s["slots"] for s in get_knockout_slots() if s["phase"] == phase), None)
        if expected is not None and len(bracket) != expected:
            return RefreshOutcome(
                status="error",
                message="The full bracket for this phase isn’t available yet — nothing saved.",
            )
        undetermined = [sid for sid, e in bracket.items() if not e["determined"]]
        if undetermined:
            return RefreshOutcome(
                status="error",
                message="Pairings for this phase aren’t determined yet — nothing saved.",
            )
        merge_knockout_bracket(bracket)
        return RefreshOutcome(
            status="api",
            message=f"{len(bracket)} pairings populated from the API.",
        )
    except Exception as e:  # noqa: BLE001 — qualsiasi errore va riportato alla pagina
        return RefreshOutcome(status="error", message=f"Bracket refresh failed: {e}")
