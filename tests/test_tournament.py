"""Test per src/models/tournament.py — esclusione slot knockout."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.tournament import (
    EXCLUDED_KNOCKOUT_SLOTS,
    get_knockout_match_ids_by_phase,
    get_knockout_slots,
)


def test_excluded_slot_is_not_in_phase_ids():
    by_phase = get_knockout_match_ids_by_phase()
    all_ids = [mid for ids in by_phase.values() for mid in ids]
    for excluded in EXCLUDED_KNOCKOUT_SLOTS:
        assert excluded not in all_ids


def test_excluded_slot_reduces_phase_count_by_its_size():
    import re

    by_phase = get_knockout_match_ids_by_phase()
    slots = {s["phase"]: s["slots"] for s in get_knockout_slots()}
    # slot 'sedicesimi' = prefix "S" seguito da cifre (es. S03), distinto da "SF.." (semifinali).
    n_excluded_sedicesimi = sum(1 for mid in EXCLUDED_KNOCKOUT_SLOTS if re.match(r"^S\d", mid))
    assert len(by_phase["sedicesimi"]) == slots["sedicesimi"] - n_excluded_sedicesimi


if __name__ == "__main__":
    test_excluded_slot_is_not_in_phase_ids()
    test_excluded_slot_reduces_phase_count_by_its_size()
    print("OK")
