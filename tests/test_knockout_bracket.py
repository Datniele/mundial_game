import importlib
import json
from pathlib import Path

from src.storage import json_storage


def _isolate_bracket(tmp_path, monkeypatch):
    """Reindirizza il file del bracket in una cartella temporanea."""
    path = tmp_path / "knockout_bracket.json"
    monkeypatch.setattr(json_storage, "KNOCKOUT_BRACKET_PATH", path)
    return path


def test_load_bracket_missing_returns_empty(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    assert json_storage.load_knockout_bracket() == {}


def test_save_then_load_bracket_roundtrip(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    bracket = {"S01": {"home": "France", "away": "Sweden",
                       "utc_date": "2026-06-30T21:00:00Z",
                       "api_id": 537416, "determined": True}}
    json_storage.save_knockout_bracket(bracket)
    assert json_storage.load_knockout_bracket() == bracket


def test_merge_bracket_preserves_other_phases(tmp_path, monkeypatch):
    _isolate_bracket(tmp_path, monkeypatch)
    json_storage.save_knockout_bracket(
        {"S01": {"home": "A", "away": "B", "utc_date": None,
                 "api_id": 1, "determined": True}}
    )
    json_storage.merge_knockout_bracket(
        {"O01": {"home": "C", "away": "D", "utc_date": None,
                 "api_id": 2, "determined": True}}
    )
    merged = json_storage.load_knockout_bracket()
    assert set(merged.keys()) == {"S01", "O01"}
    assert merged["S01"]["home"] == "A"


from src.scraper import knockout_bracket as kb

_SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "wc_matches_sample.json").read_text(encoding="utf-8")
)


def test_build_phase_bracket_assigns_slots_by_api_id():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    # id 100 viene prima di id 200 -> S01, S02
    assert list(bracket.keys()) == ["S01", "S02"]
    assert bracket["S01"]["api_id"] == 100
    assert bracket["S02"]["api_id"] == 200


def test_build_phase_bracket_normalizes_team_names():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    assert bracket["S01"]["home"] == "South Korea"  # "Korea Republic" -> alias
    assert bracket["S01"]["away"] == "Brazil"
    assert bracket["S01"]["determined"] is True


def test_build_phase_bracket_marks_undetermined():
    bracket = kb.build_phase_bracket(_SAMPLE, "ottavi")
    assert bracket["O01"]["home"] is None
    assert bracket["O01"]["determined"] is False


def test_slot_label_uses_real_teams_when_determined():
    bracket = kb.build_phase_bracket(_SAMPLE, "sedicesimi")
    assert kb.slot_label("S01", bracket) == "S01 — South Korea vs Brazil"


def test_slot_label_falls_back_to_id():
    assert kb.slot_label("S99", {}) == "S99"
    bracket = kb.build_phase_bracket(_SAMPLE, "ottavi")
    assert kb.slot_label("O01", bracket) == "O01"  # non determinato -> solo id
