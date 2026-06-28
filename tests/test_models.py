"""Test per i modelli e i loro helper di (de)serializzazione."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Outcome, Result


def test_match_prediction_advances_default_none():
    p = MatchPrediction(match_id="S01", home_goals=2, away_goals=1)
    assert p.advances is None
    # la property derivata dal punteggio resta disponibile
    assert p.outcome == Outcome.HOME


def test_match_prediction_advances_independent_from_score():
    # 2-2 (esito derivato = DRAW) ma passa away (es. ai rigori)
    p = MatchPrediction(match_id="S01", home_goals=2, away_goals=2, advances="away")
    assert p.outcome == Outcome.DRAW
    assert p.advances == "away"


def test_result_advances_default_none():
    r = Result(match_id="S01", home_goals=1, away_goals=0)
    assert r.advances is None
    r2 = Result(match_id="S02", home_goals=0, away_goals=0, advances="home")
    assert r2.advances == "home"


from src.models.participant import Participant


def test_participant_roundtrip_advances():
    p = Participant(name="Mario Rossi")
    p.match_predictions = {
        "S01": MatchPrediction(match_id="S01", home_goals=2, away_goals=2, advances="away"),
    }
    data = p.to_dict()
    assert data["match_predictions"]["S01"]["home_goals"] == 2
    assert data["match_predictions"]["S01"]["advances"] == "away"

    back = Participant.from_dict(data)
    pred = back.match_predictions["S01"]
    assert pred.advances == "away"


def test_participant_from_dict_legacy_without_advances():
    # pronostico vecchio: solo punteggio, niente advances
    data = {
        "name": "Old Player",
        "match_predictions": {"S01": {"home_goals": 1, "away_goals": 0}},
        "group_rankings": {},
    }
    back = Participant.from_dict(data)
    pred = back.match_predictions["S01"]
    assert pred.advances is None


if __name__ == "__main__":
    test_match_prediction_advances_default_none()
    test_match_prediction_advances_independent_from_score()
    test_result_advances_default_none()
    test_participant_roundtrip_advances()
    test_participant_from_dict_legacy_without_advances()
    print("OK")
