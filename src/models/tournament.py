import json
from pathlib import Path
from typing import Dict, List
from src.models.match import Match, Phase

FIXTURES_PATH = Path(__file__).parent.parent.parent / "data" / "fixtures" / "fixtures.json"

# Slot knockout esclusi dal gioco: partite disputate prima che i pronostici fossero
# disponibili, quindi non si pronosticano né concorrono al punteggio/statistiche.
EXCLUDED_KNOCKOUT_SLOTS: set[str] = {"S03"}  # South Africa vs Canada (giocata il 2026-06-28)


def load_fixtures() -> tuple[Dict[str, Match], Dict[str, List[str]]]:
    """Returns (matches_by_id, groups_by_name)."""
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)

    matches: Dict[str, Match] = {}

    for m in data["group_matches"]:
        matches[m["id"]] = Match(
            id=m["id"],
            phase=Phase.GROUP,
            home_team=m["home"],
            away_team=m["away"],
            group=m["group"],
            date=m.get("date"),
        )

    groups: Dict[str, List[str]] = {
        g: info["teams"] for g, info in data["groups"].items()
    }

    return matches, groups


def get_group_match_ids() -> List[str]:
    matches, _ = load_fixtures()
    return [mid for mid, m in matches.items() if m.phase == Phase.GROUP]


def get_knockout_slots() -> List[dict]:
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["knockout_rounds"]


def get_knockout_match_ids_by_phase() -> Dict[str, List[str]]:
    """Returns {phase_name: [match_ids]} for all knockout rounds."""
    result: Dict[str, List[str]] = {}
    for slot in get_knockout_slots():
        phase = slot["phase"]
        ids = [
            f"{slot['prefix']}{i:02d}"
            for i in range(1, slot["slots"] + 1)
            if f"{slot['prefix']}{i:02d}" not in EXCLUDED_KNOCKOUT_SLOTS
        ]
        result.setdefault(phase, []).extend(ids)
    return result
