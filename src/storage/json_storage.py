import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.models.match import Result
from src.models.participant import Participant

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PREDICTIONS_DIR = DATA_DIR / "predictions"
RESULTS_PATH = DATA_DIR / "results" / "results.json"
RANKINGS_PATH = DATA_DIR / "results" / "group_rankings.json"
REGISTRY_PATH = DATA_DIR / "participants" / "registry.json"
RANKINGS_META_PATH = DATA_DIR / "results" / "group_rankings_meta.json"
GROUP_STANDINGS_PATH = DATA_DIR / "results" / "group_standings.json"
PHASE_LOCKS_PATH = DATA_DIR / "results" / "phase_locks.json"
KNOCKOUT_BRACKET_PATH = DATA_DIR / "results" / "knockout_bracket.json"


def _ensure_dirs():
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)


# ---------- Participants ----------

def save_participant(participant: Participant) -> None:
    _ensure_dirs()
    path = PREDICTIONS_DIR / f"{participant.name.lower().replace(' ', '_')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(participant.to_dict(), f, ensure_ascii=False, indent=2)


def load_participant(name: str) -> Optional[Participant]:
    path = PREDICTIONS_DIR / f"{name.lower().replace(' ', '_')}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return Participant.from_dict(json.load(f))


def load_all_participants() -> List[Participant]:
    _ensure_dirs()
    participants = []
    for path in sorted(PREDICTIONS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            participants.append(Participant.from_dict(json.load(f)))
    return participants


def delete_participant(name: str) -> bool:
    path = PREDICTIONS_DIR / f"{name.lower().replace(' ', '_')}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_participants() -> List[str]:
    _ensure_dirs()
    return [p.stem for p in sorted(PREDICTIONS_DIR.glob("*.json"))]


def merge_participant(participant: Participant) -> None:
    """Aggiorna solo le fasi presenti nel file caricato, preservando le altre già salvate."""
    existing = load_participant(participant.name)
    if existing is None:
        save_participant(participant)
        return
    existing.match_predictions.update(participant.match_predictions)
    existing.group_rankings.update(participant.group_rankings)
    save_participant(existing)


# ---------- Registry ----------

def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"participants": []}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    _ensure_dirs()
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def register_participant(name: str) -> None:
    """Aggiunge il partecipante al registry se non presente."""
    reg = load_registry()
    known = {p["name"] for p in reg.get("participants", [])}
    if name not in known:
        now = datetime.now().isoformat(timespec="seconds")
        reg.setdefault("participants", []).append({
            "name": name,
            "registered_at": now,
            "last_updated": now,
        })
        save_registry(reg)


def update_registry_timestamp(name: str) -> None:
    reg = load_registry()
    for entry in reg.get("participants", []):
        if entry["name"] == name:
            entry["last_updated"] = datetime.now().isoformat(timespec="seconds")
            break
    save_registry(reg)


def reset_all_predictions() -> int:
    """Elimina tutti i pronostici e svuota il registry. Restituisce il numero di file rimossi."""
    _ensure_dirs()
    removed = 0
    for path in PREDICTIONS_DIR.glob("*.json"):
        path.unlink()
        removed += 1
    save_registry({"participants": []})
    return removed


# ---------- Results ----------

def save_results(results: Dict[str, dict]) -> None:
    _ensure_dirs()
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def load_results() -> Dict[str, Result]:
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        mid: Result(
            match_id=mid,
            home_goals=v["home_goals"],
            away_goals=v["away_goals"],
            advances=v.get("advances"),
        )
        for mid, v in raw.items()
        if v.get("played", False)
    }


def save_group_rankings(rankings: Dict[str, List[str]]) -> None:
    _ensure_dirs()
    with open(RANKINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2)


def load_group_rankings() -> Dict[str, List[str]]:
    if not RANKINGS_PATH.exists():
        return {}
    with open(RANKINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_group_standings(standings: Dict[str, List[dict]]) -> None:
    """Salva la classifica completa dei gironi (pos, squadra, punti, statistiche) per la visualizzazione."""
    _ensure_dirs()
    with open(GROUP_STANDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(standings, f, ensure_ascii=False, indent=2)


def load_group_standings() -> Dict[str, List[dict]]:
    """Restituisce la classifica completa dei gironi, o {} se non disponibile."""
    if not GROUP_STANDINGS_PATH.exists():
        return {}
    with open(GROUP_STANDINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_rankings_source(source: str) -> None:
    """Salva la provenienza delle classifiche gironi: 'api', 'default' o 'manual'."""
    _ensure_dirs()
    with open(RANKINGS_META_PATH, "w", encoding="utf-8") as f:
        json.dump({"source": source}, f)


def load_rankings_source() -> str | None:
    """Restituisce la provenienza delle classifiche gironi, o None se non disponibile."""
    if not RANKINGS_META_PATH.exists():
        return None
    with open(RANKINGS_META_PATH, encoding="utf-8") as f:
        return json.load(f).get("source")


# ---------- Phase locks ----------

def load_phase_locks() -> set:
    """Restituisce l'insieme delle fasi bloccate (pronostici non più modificabili)."""
    if not PHASE_LOCKS_PATH.exists():
        return set()
    with open(PHASE_LOCKS_PATH, encoding="utf-8") as f:
        return set(json.load(f).get("locked_phases", []))


def save_phase_locks(locked_phases: set) -> None:
    """Salva l'insieme delle fasi bloccate."""
    _ensure_dirs()
    with open(PHASE_LOCKS_PATH, "w", encoding="utf-8") as f:
        json.dump({"locked_phases": sorted(locked_phases)}, f, ensure_ascii=False, indent=2)


def set_phase_lock(phase: str, locked: bool) -> set:
    """Blocca o sblocca una singola fase. Restituisce l'insieme aggiornato."""
    locks = load_phase_locks()
    if locked:
        locks.add(phase)
    else:
        locks.discard(phase)
    save_phase_locks(locks)
    return locks


def is_phase_locked(phase: str) -> bool:
    """True se i pronostici per la fase indicata sono bloccati."""
    return phase in load_phase_locks()


# ---------- Knockout bracket (accoppiamenti reali da API) ----------

def save_knockout_bracket(bracket: Dict[str, dict]) -> None:
    """Salva l'intero bracket knockout {slot_id: {home, away, utc_date, api_id, determined}}."""
    _ensure_dirs()
    with open(KNOCKOUT_BRACKET_PATH, "w", encoding="utf-8") as f:
        json.dump(bracket, f, ensure_ascii=False, indent=2)


def load_knockout_bracket() -> Dict[str, dict]:
    """Restituisce il bracket knockout salvato, o {} se non disponibile."""
    if not KNOCKOUT_BRACKET_PATH.exists():
        return {}
    with open(KNOCKOUT_BRACKET_PATH, encoding="utf-8") as f:
        return json.load(f)


def merge_knockout_bracket(phase_bracket: Dict[str, dict]) -> None:
    """Sovrascrive solo gli slot passati (di una fase), preservando le altre fasi."""
    existing = load_knockout_bracket()
    existing.update(phase_bracket)
    save_knockout_bracket(existing)
