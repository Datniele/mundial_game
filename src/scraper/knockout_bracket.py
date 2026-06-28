"""
Accoppiamenti delle fasi a eliminazione diretta — football-data.org (free tier).
Endpoint: GET https://api.football-data.org/v4/competitions/WC/matches

A differenza delle standings (solo gironi), questo modulo recupera gli accoppiamenti
reali del tabellone knockout e li mappa sugli slot interni (S01…, O01…). Lo scarico è
pensato per essere innescato manualmente dall'Admin, una fase per volta.
"""

from typing import Dict

import requests

from src.models.tournament import load_fixtures, get_knockout_slots
from src.scraper.results_scraper import (
    BASE_URL,
    HEADERS,
    _build_team_resolver,
    _resolve_team,
)

# API stage -> fase interna (coerente con src/models/match.py Phase)
STAGE_TO_PHASE = {
    "LAST_32": "sedicesimi",
    "LAST_16": "ottavi",
    "QUARTER_FINALS": "quarti",
    "SEMI_FINALS": "semifinali",
    "THIRD_PLACE": "finale_3posto",
    "FINAL": "finale",
}


def fetch_matches() -> dict:
    """Scarica tutte le partite del Mondiale corrente (gironi + knockout)."""
    resp = requests.get(
        f"{BASE_URL}/competitions/WC/matches",
        headers=HEADERS,
        timeout=15,
    )
    if resp.status_code == 403:
        raise PermissionError(
            "403 Forbidden — la tua API key non ha accesso a questa risorsa."
        )
    if resp.status_code == 429:
        raise RuntimeError("429 Too Many Requests — superate le 10 req/min del free tier.")
    resp.raise_for_status()
    return resp.json()


def build_phase_bracket(payload: dict, phase: str) -> Dict[str, dict]:
    """Costruisce {slot_id: {...}} per la fase richiesta a partire dal payload /matches.

    Funzione pura (nessuna rete): filtra le partite dello stage corrispondente, le ordina
    per `api_id` crescente (chiave stabile) e le assegna agli slot S01/O01/… normalizzando
    i nomi squadra ai nomi canonici di fixtures.json.
    """
    slot_cfg = next((s for s in get_knockout_slots() if s["phase"] == phase), None)
    if slot_cfg is None:
        return {}
    prefix = slot_cfg["prefix"]

    stages = [api for api, ph in STAGE_TO_PHASE.items() if ph == phase]
    matches = [m for m in payload.get("matches", []) if m.get("stage") in stages]
    matches.sort(key=lambda m: m.get("id", 0))

    _, groups = load_fixtures()
    lookup = _build_team_resolver(groups)

    bracket: Dict[str, dict] = {}
    for i, m in enumerate(matches, 1):
        slot_id = f"{prefix}{i:02d}"
        home_raw = (m.get("homeTeam") or {}).get("name")
        away_raw = (m.get("awayTeam") or {}).get("name")
        determined = bool(home_raw) and bool(away_raw)
        bracket[slot_id] = {
            "home": _resolve_team(home_raw, lookup) if home_raw else None,
            "away": _resolve_team(away_raw, lookup) if away_raw else None,
            "utc_date": m.get("utcDate"),
            "api_id": m.get("id"),
            "determined": determined,
        }
    return bracket


def build_knockout_results(payload: dict) -> Dict[str, dict]:
    """Risultati reali knockout dai match FINISHED dell'API, mappati sugli slot S01/O01/…

    Funzione pura (nessuna rete). Per ogni fase a eliminazione ordina le partite per
    `api_id` crescente (stessa chiave di build_phase_bracket, così gli slot coincidono),
    poi per le sole partite concluse estrae:
      - home_goals / away_goals dei **90 minuti**: `score.regularTime` se presente
        (match andato ai supplementari/rigori), altrimenti `score.fullTime` (match
        chiuso nei regolamentari, dove fullTime è già il punteggio a 90').
      - advances ("home"/"away") da `score.winner` (vincitore complessivo, rigori inclusi).

    Le partite non ancora concluse o senza punteggio non vengono incluse.
    """
    results: Dict[str, dict] = {}
    for phase in STAGE_TO_PHASE.values():
        slot_cfg = next((s for s in get_knockout_slots() if s["phase"] == phase), None)
        if slot_cfg is None:
            continue
        prefix = slot_cfg["prefix"]
        stages = [api for api, ph in STAGE_TO_PHASE.items() if ph == phase]
        matches = [m for m in payload.get("matches", []) if m.get("stage") in stages]
        matches.sort(key=lambda m: m.get("id", 0))
        for i, m in enumerate(matches, 1):
            if m.get("status") != "FINISHED":
                continue
            score = m.get("score") or {}
            # 90 minuti: regularTime quando il match è andato oltre, altrimenti fullTime.
            regular = score.get("regularTime") or {}
            full_time = score.get("fullTime") or {}
            home_g = regular.get("home", full_time.get("home"))
            away_g = regular.get("away", full_time.get("away"))
            if home_g is None or away_g is None:
                continue
            winner = score.get("winner")
            advances = {"HOME_TEAM": "home", "AWAY_TEAM": "away"}.get(winner)
            results[f"{prefix}{i:02d}"] = {
                "home_goals": int(home_g),
                "away_goals": int(away_g),
                "played": True,
                "advances": advances,
            }
    return results


def slot_label(match_id: str, bracket: Dict[str, dict]) -> str:
    """'S01 — France vs Sweden' se l'accoppiamento è noto, altrimenti il solo id."""
    entry = bracket.get(match_id)
    if entry and entry.get("determined"):
        return f"{match_id} — {entry['home']} vs {entry['away']}"
    return match_id
