import importlib

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
