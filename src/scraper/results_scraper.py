"""
Classifiche gironi Mondiali 2026 — football-data.org (free tier)
Endpoint: GET https://api.football-data.org/v4/competitions/WC/standings

Le classifiche vengono lette direttamente dall'endpoint /standings: per il torneo
in corso l'API restituisce le tabelle GROUP_STAGE già ordinate secondo i criteri
ufficiali FIFA (tie-breaker inclusi). Posizione e punti sono quelli ufficiali, non
serve ricostruire né riordinare nulla a partire dalle singole partite.

Dipendenze: pip install requests python-dotenv
API key gratuita: https://www.football-data.org/client/register
Limite free tier: 10 richieste/minuto
"""

import os
import json
import unicodedata
import requests
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()  # Carica variabili d'ambiente da .env se presente

API_KEY  = os.getenv("API_FOOTBALL_KEY", "TUA_API_KEY_QUI")
BASE_URL = "https://api.football-data.org/v4"
HEADERS  = {"X-Auth-Token": API_KEY}

FIXTURES_PATH = Path(__file__).parent.parent.parent / "data" / "fixtures" / "fixtures.json"


class DefaultRankingsUsed(Exception):
    """Sollevata quando l'API non ha classifiche: i rankings sono l'ordine standard da fixtures."""
    def __init__(self, rankings: Dict[str, List[str]], standings: Optional[Dict[str, List[dict]]] = None):
        self.rankings = rankings
        self.standings = standings or {}
        super().__init__(
            "L'API non ha restituito classifiche GROUP_STAGE (torneo non ancora iniziato o dati assenti). "
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
# Normalizzazione nomi squadra (API ↔ fixtures)
# ──────────────────────────────────────────────
# Lo scoring confronta i nomi squadra letteralmente con i pronostici, che usano i
# nomi di fixtures.json. I nomi restituiti da football-data.org possono differire,
# quindi ogni squadra viene ricondotta al nome canonico del calendario.

# Varianti note (forma normalizzata dell'API) -> nome canonico in fixtures.json
_TEAM_ALIASES = {
    "korearepublic": "South Korea",
    "republicofkorea": "South Korea",
    "iriran": "Iran",
    "usa": "United States",
    "unitedstatesofamerica": "United States",
    "cotedivoire": "Ivory Coast",
    "czechrepublic": "Czechia",
    "turkiye": "Turkey",
    "drcongo": "DR Congo",
    "congodr": "DR Congo",
    "democraticrepublicofthecongo": "DR Congo",
    "bosniaandherzegovina": "Bosnia and Herzegovina",
    "bosniaherzegovina": "Bosnia and Herzegovina",
}


def _normalize(name: str) -> str:
    """Riduce un nome a lettere/cifre minuscole senza accenti per il confronto."""
    nfkd = unicodedata.normalize("NFKD", name or "")
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return "".join(ch for ch in no_accents.lower() if ch.isalnum())


def _build_team_resolver(groups: Dict[str, List[str]]) -> Dict[str, str]:
    """Costruisce {nome_normalizzato: nome_canonico_fixtures}."""
    lookup: Dict[str, str] = {}
    for teams in groups.values():
        for t in teams:
            lookup[_normalize(t)] = t
    for variant, canonical in _TEAM_ALIASES.items():
        lookup[variant] = canonical
    return lookup


def _resolve_team(name: str, lookup: Dict[str, str]) -> str:
    """Ricava il nome canonico di fixtures dal nome restituito dall'API.

    Se non trova corrispondenza restituisce il nome originale, così la squadra
    compare comunque in classifica (meglio di scartarla)."""
    norm = _normalize(name)
    if not norm:
        return name
    if norm in lookup:
        return lookup[norm]
    # Fallback: corrispondenza per sottostringa (es. "IR Iran" -> "Iran")
    for key, canonical in lookup.items():
        if norm in key or key in norm:
            return canonical
    return name


# ──────────────────────────────────────────────
# Fetch
# ──────────────────────────────────────────────

def _fetch_standings() -> dict:
    """Scarica le classifiche della fase a gironi da football-data.org.

    Non si passa il parametro `season`: sul free tier l'endpoint /standings, se
    riceve `season`, restituisce una vista aggregata senza gironi. Senza parametro
    risponde con le 12 tabelle della stagione corrente (2026), che è ciò che serve.
    """
    resp = requests.get(
        f"{BASE_URL}/competitions/WC/standings",
        headers=HEADERS,
        timeout=15,
    )

    if resp.status_code == 403:
        raise PermissionError(
            "403 Forbidden — la tua API key non ha accesso a questa risorsa "
            "(controlla il piano o la stagione richiesta)."
        )
    if resp.status_code == 429:
        raise RuntimeError("429 Too Many Requests — hai superato le 10 req/min del free tier.")
    resp.raise_for_status()

    return resp.json()


# ──────────────────────────────────────────────
# Parsing classifiche
# ──────────────────────────────────────────────

def _group_key(group_name: str) -> str:
    """Estrae la lettera del girone da 'GROUP_A' / 'Group A' -> 'A'."""
    token = (group_name or "").replace("_", " ").strip().split()
    return token[-1].upper() if token else ""


def parse_standings(
    payload: dict,
    groups: Dict[str, List[str]],
) -> Tuple[Dict[str, List[RigaClassifica]], int]:
    """
    Estrae le tabelle 'TOTAL' della fase a gironi dalla risposta /standings.

    Le righe sono già nell'ordine ufficiale restituito dall'API: posizione e punti
    non vengono ricalcolati. I nomi squadra sono ricondotti al nome canonico di
    fixtures.json per essere coerenti con i pronostici e con lo scoring.

    Returns:
        (standings, partite_giocate) dove standings = {"A": [RigaClassifica], ...}
    """
    resolver = _build_team_resolver(groups)
    standings: Dict[str, List[RigaClassifica]] = {}
    played_total = 0

    for standing in payload.get("standings", []):
        # Solo la tabella complessiva (non HOME/AWAY). Lo `stage` dell'endpoint
        # /standings è "ALL", non "GROUP_STAGE": il girone è identificato dal campo
        # `group` ("Group A"), quindi ci basta filtrare per tipo e girone valido.
        if standing.get("type") != "TOTAL":
            continue

        gid = _group_key(standing.get("group", ""))
        if gid not in groups:
            continue

        righe: List[RigaClassifica] = []
        for row in standing.get("table", []):
            played = row.get("playedGames", 0)
            played_total += played
            righe.append(
                RigaClassifica(
                    pos=row.get("position", len(righe) + 1),
                    squadra=_resolve_team(row.get("team", {}).get("name", ""), resolver),
                    giocate=played,
                    vinte=row.get("won", 0),
                    nulle=row.get("draw", 0),
                    perse=row.get("lost", 0),
                    gol_fatti=row.get("goalsFor", 0),
                    gol_subiti=row.get("goalsAgainst", 0),
                    differenza_reti=row.get("goalDifference", 0),
                    punti=row.get("points", 0),
                )
            )
        if righe:
            standings[gid] = sorted(righe, key=lambda r: r.pos)

    return standings, played_total


def get_classifiche() -> dict[str, list[RigaClassifica]]:
    """
    Restituisce le classifiche della fase a gironi del Mondiale lette dall'API.

    Returns:
        { "A": [RigaClassifica, ...], "B": [...], ... }
    """
    payload = _fetch_standings()
    groups = _get_default_rankings()
    standings, _ = parse_standings(payload, groups)
    return standings


# ──────────────────────────────────────────────
# Fallback ordine standard da calendario
# ──────────────────────────────────────────────

def _get_default_rankings() -> Dict[str, List[str]]:
    """Ordine standard delle squadre per girone, letto da fixtures.json."""
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {g: info["teams"] for g, info in data["groups"].items()}


def _default_standings_payload(groups: Dict[str, List[str]]) -> Dict[str, List[dict]]:
    """Classifica completa di fallback (tutte le squadre a 0 punti, ordine calendario)."""
    return {
        gid: [
            RigaClassifica(
                pos=pos, squadra=team, giocate=0, vinte=0, nulle=0, perse=0,
                gol_fatti=0, gol_subiti=0, differenza_reti=0, punti=0,
            ).as_dict()
            for pos, team in enumerate(teams, 1)
        ]
        for gid, teams in groups.items()
    }


# ──────────────────────────────────────────────
# API pubbliche per la pagina Streamlit
# ──────────────────────────────────────────────

def scrape_group_rankings() -> Dict[str, List[str]]:
    """
    Scarica le classifiche da football-data.org e le restituisce nel formato atteso
    da save_group_rankings(): {"A": ["Squadra1", ...], "B": [...], ...}

    Raises:
        ValueError: se la API key non è configurata.
        DefaultRankingsUsed: se l'API non ha restituito classifiche GROUP_STAGE;
            l'eccezione porta dentro i rankings di fallback (ordine standard da fixtures).
    """
    if API_KEY == "TUA_API_KEY_QUI":
        raise ValueError(
            "API key non configurata. "
            "Imposta la variabile d'ambiente API_FOOTBALL_KEY nel file .env o nel sistema."
        )
    payload = _fetch_standings()
    groups = _get_default_rankings()
    standings, played = parse_standings(payload, groups)
    if not standings or played == 0:
        # Nessuna classifica reale: si usa l'ordine di calendario.
        raise DefaultRankingsUsed(groups, _default_standings_payload(groups))
    return to_rankings(standings)


def scrape_group_data() -> Tuple[Dict[str, List[str]], Dict[str, List[dict]]]:
    """
    Variante di scrape_group_rankings() che restituisce anche la classifica completa.

    Returns:
        (rankings, standings) dove
          - rankings:  {"A": ["Squadra1", ...], ...}  → per lo scoring
          - standings: {"A": [{"pos", "squadra", "punti", ...}], ...}  → per la visualizzazione

    Raises:
        ValueError: se la API key non è configurata.
        DefaultRankingsUsed: se l'API non ha restituito classifiche GROUP_STAGE;
            l'eccezione porta dentro sia i rankings sia la classifica completa di fallback.
    """
    if API_KEY == "TUA_API_KEY_QUI":
        raise ValueError(
            "API key non configurata. "
            "Imposta la variabile d'ambiente API_FOOTBALL_KEY nel file .env o nel sistema."
        )
    payload = _fetch_standings()
    groups = _get_default_rankings()
    standings, played = parse_standings(payload, groups)
    if not standings or played == 0:
        raise DefaultRankingsUsed(groups, _default_standings_payload(groups))
    return to_rankings(standings), to_standings_payload(standings)


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


# ──────────────────────────────────────────────
# Conversioni di formato
# ──────────────────────────────────────────────

def to_rankings(classifiche: dict[str, list[RigaClassifica]]) -> Dict[str, List[str]]:
    """
    Converte le classifiche nel formato atteso da save_group_rankings().

    {"A": ["Squadra1", ...], ...} con squadre ordinate per posizione crescente.
    Compatibile con participant.group_rankings e score_group_stage().
    """
    return {
        gid: [r.squadra for r in sorted(righe, key=lambda r: r.pos)]
        for gid, righe in classifiche.items()
    }


def to_standings_payload(classifiche: dict[str, list[RigaClassifica]]) -> Dict[str, List[dict]]:
    """
    Converte le classifiche in un payload serializzabile per la visualizzazione:
    {"A": [{"pos", "squadra", "punti", ...}], ...} ordinato per posizione.
    """
    return {
        gid: [r.as_dict() for r in sorted(righe, key=lambda r: r.pos)]
        for gid, righe in classifiche.items()
    }


def to_json(classifiche: dict[str, list[RigaClassifica]], path: str | None = None) -> str:
    output = {g: [r.as_dict() for r in righe] for g, righe in classifiche.items()}
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nSalvato in: {path}")
    return text


# ──────────────────────────────────────────────
# Utilità di stampa
# ──────────────────────────────────────────────

def stampa_classifiche(classifiche: dict[str, list[RigaClassifica]]) -> None:
    intestazione = (
        f"{'Pos':<4} {'Squadra':<26} {'G':>3} {'V':>3} "
        f"{'N':>3} {'P':>3} {'GF':>4} {'GS':>4} {'DR':>5} {'Pt':>4}"
    )
    sep = "─" * 62

    for gruppo, squadre in sorted(classifiche.items()):
        print(f"\n{'═' * 62}")
        print(f"  Girone {gruppo}")
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


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if API_KEY == "TUA_API_KEY_QUI":
        print("⚠️  Imposta la variabile d'ambiente API_FOOTBALL_KEY oppure sostituisci API_KEY nel codice.")
        exit(1)

    from src.storage.json_storage import save_group_rankings

    classifiche = get_classifiche()
    stampa_classifiche(classifiche)

    rankings = to_rankings(classifiche)
    save_group_rankings(rankings)
    print(f"\nClassifiche salvate in storage ({len(rankings)} gironi).")
