import json
from pathlib import Path
from typing import Dict, List, Optional

from src.models.match import Result
from src.models.participant import Participant

DATA_DIR = Path(__file__).parent.parent.parent / "data"
PREDICTIONS_DIR = DATA_DIR / "predictions"
RESULTS_PATH = DATA_DIR / "results" / "results.json"
RANKINGS_PATH = DATA_DIR / "results" / "group_rankings.json"


def _ensure_dirs():
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)


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
        mid: Result(match_id=mid, home_goals=v["home_goals"], away_goals=v["away_goals"])
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
