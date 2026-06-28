"""Test per i modelli e i loro helper di (de)serializzazione."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Outcome, Result


def test_outcome_token_roundtrip():
    for o, token in [(Outcome.HOME, "1"), (Outcome.DRAW, "X"), (Outcome.AWAY, "2")]:
        assert o.token == token
        assert Outcome.from_token(token) == o


def test_match_prediction_new_fields_default_none():
    p = MatchPrediction(match_id="S01", home_goals=2, away_goals=1)
    assert p.outcome_90 is None
    assert p.advances is None
    # la property derivata dal punteggio resta disponibile
    assert p.outcome == Outcome.HOME


def test_match_prediction_discordant_fields():
    # 2-2 (esito derivato = DRAW) ma esito esplicito X e passa away
    p = MatchPrediction(
        match_id="S01", home_goals=2, away_goals=2,
        outcome_90=Outcome.DRAW, advances="away",
    )
    assert p.outcome_90 == Outcome.DRAW
    assert p.advances == "away"


def test_result_advances_default_none():
    r = Result(match_id="S01", home_goals=1, away_goals=0)
    assert r.advances is None
    r2 = Result(match_id="S02", home_goals=0, away_goals=0, advances="home")
    assert r2.advances == "home"


from src.models.participant import Participant


def test_participant_roundtrip_new_fields():
    p = Participant(name="Mario Rossi")
    p.match_predictions = {
        "S01": MatchPrediction(
            match_id="S01", home_goals=2, away_goals=2,
            outcome_90=Outcome.DRAW, advances="away",
        ),
    }
    data = p.to_dict()
    assert data["match_predictions"]["S01"]["outcome_90"] == "X"
    assert data["match_predictions"]["S01"]["advances"] == "away"

    back = Participant.from_dict(data)
    pred = back.match_predictions["S01"]
    assert pred.outcome_90 == Outcome.DRAW
    assert pred.advances == "away"


def test_participant_from_dict_legacy_without_new_fields():
    # pronostico vecchio: solo punteggio, niente outcome_90/advances
    data = {
        "name": "Old Player",
        "match_predictions": {"S01": {"home_goals": 1, "away_goals": 0}},
        "group_rankings": {},
    }
    back = Participant.from_dict(data)
    pred = back.match_predictions["S01"]
    assert pred.outcome_90 is None
    assert pred.advances is None


if __name__ == "__main__":
    test_outcome_token_roundtrip()
    test_match_prediction_new_fields_default_none()
    test_match_prediction_discordant_fields()
    test_result_advances_default_none()
    test_participant_roundtrip_new_fields()
    test_participant_from_dict_legacy_without_new_fields()
    print("OK")
