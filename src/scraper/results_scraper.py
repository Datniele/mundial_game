"""
Classifiche gironi Mondiali 2026 — football-data.org (free tier)
Endpoint: GET https://api.football-data.org/v4/competitions/WC/standings

Dipendenze: pip install requests
API key gratuita: https://www.football-data.org/client/register
Limite free tier: 10 richieste/minuto
"""

import os
import json
import requests
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()  # Carica variabili d'ambiente da .env se presente

API_KEY  = os.getenv("API_FOOTBALL_KEY", "TUA_API_KEY_QUI")
BASE_URL = "https://api.football-data.org/v4"
HEADERS  = {"X-Auth-Token": API_KEY}

FIXTURES_PATH = Path(__file__).parent.parent.parent / "data" / "fixtures" / "fixtures.json"


class DefaultRankingsUsed(Exception):
    """Sollevata quando l'API non ha dati: i rankings sono l'ordine standard da fixtures."""
    def __init__(self, rankings: Dict[str, List[str]]):
        self.rankings = rankings
        super().__init__(
            "L'API non ha restituito classifiche (torneo non ancora iniziato o dati assenti). "
            "È stato usato l'ordine standard dal calendario gironi."
        )


# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────

@dataclass
class RigaClassifica:
    pos: int
    squadra: str
    giocate: int
    vinte: int
    nulle: int
    perse: int
    gol_fatti: int
    gol_subiti: int
    differenza_reti: int
    punti: int

    def as_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────
# Fetch + parsing
# ──────────────────────────────────────────────

def get_classifiche(season: int | None = None) -> dict[str, list[RigaClassifica]]:
    """
    Restituisce tutte le classifiche della fase a gironi del Mondiale.

    Args:
        season: anno della stagione (es. 2026). None = stagione corrente.

    Returns:
        { "Group A": [RigaClassifica, ...], "Group B": [...], ... }

    Note sulla struttura JSON di football-data.org per LEAGUE_CUP:
        response["standings"] è una lista di gironi.
        Ogni girone ha:
            - "stage":  "GROUP_STAGE"
            - "type":   "TOTAL"
            - "group":  "GROUP_A" | "GROUP_B" | ...
            - "table":  lista di entry (una per squadra)
    """
    params = {}
    if season:
        params["season"] = season

    resp = requests.get(
        f"{BASE_URL}/competitions/WC/standings",
        headers=HEADERS,
        params=params,
        timeout=15,
    )

    # Gestione errori HTTP esplicita
    if resp.status_code == 403:
        raise PermissionError(
            "403 Forbidden — la tua API key non ha accesso a questa risorsa "
            "(controlla il piano o la stagione richiesta)."
        )
    if resp.status_code == 429:
        raise RuntimeError("429 Too Many Requests — hai superato le 10 req/min del free tier.")
    resp.raise_for_status()

    data = resp.json()
    standings_raw: list[dict] = data.get("standings", [])

    if not standings_raw:
        raise ValueError(f"Nessun dato standings nella risposta:\n{json.dumps(data, indent=2)}")

    risultati: dict[str, list[RigaClassifica]] = {}

    for girone in standings_raw:
        # Filtra solo la fase a gironi (esclude eventuali KNOCKOUT o PLAYOFF)
        if girone.get("stage") != "GROUP_STAGE":
            continue

        # "GROUP_A" -> "Group A"
        raw_group = girone.get("group", "GROUP_UNKNOWN")
        label = raw_group.replace("_", " ").title()  # "Group A"

        righe = []
        for entry in girone.get("table", []):
            team  = entry.get("team", {})
            stats = entry  # i campi sono flat nell'entry

            righe.append(RigaClassifica(
                pos=stats.get("position", 0),
                squadra=team.get("name", ""),
                giocate=stats.get("playedGames", 0),
                vinte=stats.get("won", 0),
                nulle=stats.get("draw", 0),
                perse=stats.get("lost", 0),
                gol_fatti=stats.get("goalsFor", 0),
                gol_subiti=stats.get("goalsAgainst", 0),
                differenza_reti=stats.get("goalDifference", 0),
                punti=stats.get("points", 0),
            ))

        if righe:
            risultati[label] = righe

    return risultati


# ──────────────────────────────────────────────
# Utilità
# ──────────────────────────────────────────────

def stampa_classifiche(classifiche: dict[str, list[RigaClassifica]]) -> None:
    intestazione = (
        f"{'Pos':<4} {'Squadra':<26} {'G':>3} {'V':>3} "
        f"{'N':>3} {'P':>3} {'GF':>4} {'GS':>4} {'DR':>5} {'Pt':>4}"
    )
    sep = "─" * 62

    for gruppo, squadre in sorted(classifiche.items()):
        print(f"\n{'═' * 62}")
        print(f"  {gruppo}")
        print(sep)
        print(intestazione)
        print(sep)
        for r in squadre:
            dr = f"{r.differenza_reti:+d}"
            print(
                f"{r.pos:<4} {r.squadra:<26} {r.giocate:>3} {r.vinte:>3} "
                f"{r.nulle:>3} {r.perse:>3} {r.gol_fatti:>4} "
                f"{r.gol_subiti:>4} {dr:>5} {r.punti:>4}"
            )


def _get_default_rankings() -> Dict[str, List[str]]:
    """Ordine standard delle squadre per girone, letto da fixtures.json."""
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {g: info["teams"] for g, info in data["groups"].items()}


def scrape_group_rankings(season: int | None = None) -> Dict[str, List[str]]:
    """
    Scarica le classifiche da football-data.org e le restituisce nel formato
    atteso da save_group_rankings(): {"A": ["Squadra1", ...], "B": [...], ...}

    Raises:
        ValueError: se la API key non è configurata.
        DefaultRankingsUsed: se l'API non ha dati GROUP_STAGE; l'eccezione
            porta dentro i rankings di fallback (ordine standard da fixtures).
    """
    if API_KEY == "TUA_API_KEY_QUI":
        raise ValueError(
            "API key non configurata. "
            "Imposta la variabile d'ambiente API_FOOTBALL_KEY nel file .env o nel sistema."
        )
    classifiche = get_classifiche(season=season)
    rankings = to_rankings(classifiche)
    if not rankings:
        raise DefaultRankingsUsed(_get_default_rankings())
    return rankings


def controlla_quota() -> dict:
    """
    Verifica la quota API corrente tramite una richiesta leggera.
    Restituisce: {"piano": str, "richieste_usate_oggi": int, "limite_giornaliero": int}
    """
    resp = requests.get(
        f"{BASE_URL}/competitions/WC",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 403:
        raise PermissionError("403 Forbidden — API key non valida o piano non abilitato.")
    resp.raise_for_status()

    richieste_usate = int(resp.headers.get("X-RequestCounter-Reset", 0))
    disponibili = int(resp.headers.get("X-Requests-Available-Minute", 10))

    return {
        "piano": "Free" if disponibili <= 10 else "Pro",
        "richieste_usate_oggi": richieste_usate,
        "limite_giornaliero": 10,
    }


def to_rankings(classifiche: dict[str, list[RigaClassifica]]) -> Dict[str, List[str]]:
    """
    Converte l'output di get_classifiche() nel formato atteso da save_group_rankings().

    "Group A" -> "A", squadre ordinate per posizione crescente.
    Compatibile con participant.group_rankings e score_group_stage().
    """
    result: Dict[str, List[str]] = {}
    for label, righe in classifiche.items():
        # "Group A" -> "A", "Group L" -> "L"
        key = label.split()[-1]
        result[key] = [r.squadra for r in sorted(righe, key=lambda r: r.pos)]
    return result


def to_json(classifiche: dict[str, list[RigaClassifica]], path: str | None = None) -> str:
    output = {g: [r.as_dict() for r in righe] for g, righe in classifiche.items()}
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nSalvato in: {path}")
    return text


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if API_KEY == "TUA_API_KEY_QUI":
        print("⚠️  Imposta la variabile d'ambiente FOOTBALL_DATA_KEY oppure sostituisci API_KEY nel codice.")
        exit(1)

    from src.storage.json_storage import save_group_rankings

    classifiche = get_classifiche(season=2026)
    stampa_classifiche(classifiche)

    rankings = to_rankings(classifiche)
    save_group_rankings(rankings)
    print(f"\nClassifiche salvate in storage ({len(rankings)} gironi).")