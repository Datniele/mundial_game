"""Test per src/scoring/statistics.py.

Compatibili con pytest. Eseguibili anche senza pytest tramite:
    python tests/test_statistics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Outcome
from src.models.participant import Participant
from src.scoring.statistics import (
    group_consensus,
    knockout_consensus,
    least_shared,
    most_shared,
    unanimous_count,
)


def _p(name, group_rankings=None, match_predictions=None):
    p = Participant(name=name)
    p.group_rankings = group_rankings or {}
    p.match_predictions = {
        mid: MatchPrediction(match_id=mid, home_goals=h, away_goals=a)
        for mid, (h, a) in (match_predictions or {}).items()
    }
    return p


# ── group_consensus ──────────────────────────────────────────────────────────

def test_group_unanimous():
    ranking = ["X", "Y", "Z", "W"]
    parts = [_p("a", {"A": ranking}), _p("b", {"A": list(ranking)})]
    [ec] = group_consensus(parts)
    assert ec.label == "A"
    assert ec.total == 2
    assert ec.top_count == 2
    assert ec.top_value == ranking
    assert ec.is_unanimous


def test_group_fully_split():
    parts = [
        _p("a", {"A": ["X", "Y", "Z", "W"]}),
        _p("b", {"A": ["Y", "X", "Z", "W"]}),
        _p("c", {"A": ["Z", "X", "Y", "W"]}),
    ]
    [ec] = group_consensus(parts)
    assert ec.total == 3
    assert ec.top_count == 1
    assert not ec.is_unanimous


def test_group_partial_rankings_excluded():
    # b ha una classifica incompleta -> non conta; resta un solo partecipante -> evento ignorato
    parts = [
        _p("a", {"A": ["X", "Y", "Z", "W"]}),
        _p("b", {"A": ["X", "Y", None, None]}),
    ]
    assert group_consensus(parts) == []


def test_group_majority():
    r = ["X", "Y", "Z", "W"]
    parts = [_p("a", {"A": list(r)}), _p("b", {"A": list(r)}), _p("c", {"A": ["W", "Z", "Y", "X"]})]
    [ec] = group_consensus(parts)
    assert ec.top_count == 2
    assert ec.total == 3
    assert ec.top_value == r


# ── knockout_consensus ───────────────────────────────────────────────────────

def test_knockout_outcome_consensus():
    # tutti danno vittoria casa, ma punteggi diversi -> esito unanime, risultato no
    parts = [
        _p("a", match_predictions={"S01": (2, 1)}),
        _p("b", match_predictions={"S01": (3, 0)}),
        _p("c", match_predictions={"S01": (1, 0)}),
    ]
    [out] = knockout_consensus(parts, ["S01"], "outcome")
    assert out.top_count == 3
    assert out.top_value == Outcome.HOME
    assert out.is_unanimous

    [exact] = knockout_consensus(parts, ["S01"], "exact")
    assert exact.top_count == 1
    assert not exact.is_unanimous


def test_knockout_exact_consensus():
    parts = [
        _p("a", match_predictions={"S01": (2, 1)}),
        _p("b", match_predictions={"S01": (2, 1)}),
    ]
    [exact] = knockout_consensus(parts, ["S01"], "exact")
    assert exact.top_count == 2
    assert exact.top_value == (2, 1)
    assert exact.is_unanimous


def test_knockout_only_predicted_slots_counted():
    # solo 1 partecipante ha pronosticato S02 -> evento ignorato (total < 2)
    parts = [
        _p("a", match_predictions={"S01": (1, 0), "S02": (0, 0)}),
        _p("b", match_predictions={"S01": (0, 2)}),
    ]
    res = knockout_consensus(parts, ["S01", "S02"], "outcome")
    assert [e.label for e in res] == ["S01"]
    assert res[0].total == 2


def test_knockout_invalid_metric():
    try:
        knockout_consensus([], ["S01"], "bogus")
    except ValueError:
        return
    raise AssertionError("attesa ValueError per metric non valida")


# ── selettori ────────────────────────────────────────────────────────────────

def test_most_least_and_unanimous():
    parts = [
        _p("a", {"A": ["X", "Y", "Z", "W"], "B": ["1", "2", "3", "4"]}),
        _p("b", {"A": ["X", "Y", "Z", "W"], "B": ["4", "3", "2", "1"]}),
    ]
    events = group_consensus(parts)  # A unanime (2), B diviso (1)
    assert most_shared(events).label == "A"
    assert least_shared(events).label == "B"
    assert unanimous_count(events) == 1


def test_selectors_empty():
    assert most_shared([]) is None
    assert least_shared([]) is None
    assert unanimous_count([]) == 0


if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {fn.__name__}: {e!r}")
    print(f"\n{len(funcs) - failures}/{len(funcs)} passed")
    sys.exit(1 if failures else 0)
