import json
from pathlib import Path
from typing import Dict, List
from src.models.match import Match, Phase

FIXTURES_PATH = Path(__file__).parent.parent.parent / "data" / "fixtures" / "fixtures.json"


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
