import re
from pathlib import Path
from typing import Optional
import pandas as pd

from src.models.match import MatchPrediction, Phase
from src.models.participant import Participant
from src.models.tournament import load_fixtures

SHEETS = {
    "group": "GIRONI",
    "rankings": "CLASSIFICHE_GIRONI",
    "r32": "SEDICESIMI",
    "r16": "OTTAVI",
    "qf": "QUARTI",
    "sf": "SEMIFINALI",
    "final": "FINALE",
}

KNOCKOUT_PHASE_MAP = {
    "SEDICESIMI": Phase.ROUND_OF_32,
    "OTTAVI": Phase.ROUND_OF_16,
    "QUARTI": Phase.QUARTER,
    "SEMIFINALI": Phase.SEMI,
    "FINALE": Phase.FINAL,
}


def _participant_name_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").title()


def _safe_int(val) -> Optional[int]:
    try:
        v = int(val)
        return v if v >= 0 else None
    except (TypeError, ValueError):
        return None


def parse_prediction_file(file_path: Path) -> Participant:
    name = _participant_name_from_filename(file_path)
    participant = Participant(name=name)

    xl = pd.ExcelFile(file_path)

    # --- GIRONI ---
    if SHEETS["group"] in xl.sheet_names:
        matches_by_id, _ = load_fixtures()
        df = xl.parse(SHEETS["group"])
        for _, row in df.iterrows():
            match_id = str(row.get("ID Partita", "")).strip()
            g1 = _safe_int(row.get("Gol Casa"))
            g2 = _safe_int(row.get("Gol Ospite"))
            if match_id and g1 is not None and g2 is not None:
                participant.match_predictions[match_id] = MatchPrediction(
                    match_id=match_id, home_goals=g1, away_goals=g2
                )

    # --- CLASSIFICHE GIRONI ---
    if SHEETS["rankings"] in xl.sheet_names:
        df = xl.parse(SHEETS["rankings"])
        for _, row in df.iterrows():
            girone = str(row.get("Girone", "")).strip()
            primo = str(row.get("1° Posto", "")).strip()
            secondo = str(row.get("2° Posto", "")).strip()
            if girone and primo and secondo:
                participant.group_rankings[girone] = [primo, secondo]

    # --- FASI A ELIMINAZIONE ---
    for sheet_key, sheet_name in [
        ("r32", SHEETS["r32"]),
        ("r16", SHEETS["r16"]),
        ("qf", SHEETS["qf"]),
        ("sf", SHEETS["sf"]),
        ("final", SHEETS["final"]),
    ]:
        if sheet_name in xl.sheet_names:
            phase = KNOCKOUT_PHASE_MAP.get(sheet_name, Phase.FINAL)
            df = xl.parse(sheet_name)
            for _, row in df.iterrows():
                match_id = str(row.get("ID Partita", "")).strip()
                g1 = _safe_int(row.get("Gol Sq1"))
                g2 = _safe_int(row.get("Gol Sq2"))
                if match_id and g1 is not None and g2 is not None:
                    participant.match_predictions[match_id] = MatchPrediction(
                        match_id=match_id, home_goals=g1, away_goals=g2
                    )

    return participant
