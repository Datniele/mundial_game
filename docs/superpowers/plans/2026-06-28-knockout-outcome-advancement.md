# Esito 90' e passaggio del turno nei pronostici knockout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettere, per ogni partita knockout, di pronosticare in modo indipendente risultato esatto, esito 90' (1/X/2) e chi passa il turno, aggiornando di conseguenza scoring e statistiche.

**Architecture:** Si estendono i dataclass `MatchPrediction` e `Result` con due campi opzionali (`outcome_90`, `advances`) e la relativa (de)serializzazione JSON. Lo scoring knockout passa ai criteri C1=passaggio, C2=esito esplicito, C3=errore differenza reti. Le pagine Streamlit (Make Predictions, Real Results, Statistics, Leaderboard, Rules) e il README vengono allineati. Funzioni pure (modelli, scoring, statistiche) sono coperte da test; le pagine Streamlit si verificano manualmente.

**Tech Stack:** Python 3.13, Streamlit 1.58, pandas, pytest 9. Persistenza su file JSON.

**Spec:** `docs/superpowers/specs/2026-06-28-knockout-outcome-advancement-design.md`

> **Revisione 2026-06-28.** Requisiti modificati in corso d'opera: niente esito 90' esplicito. Le predizioni
> raccolgono solo **risultato esatto** + **passaggio del turno**; criteri **C1 = passaggio**, **C2 = risultati
> esatti (conteggio)**, **C3 = errore differenza reti**. Dove i task sotto citano `outcome_90` o C2=esito, vale
> invece: nessun campo `outcome_90`, C2 = conteggio risultati esatti. Make Predictions ha solo il radio "passa il
> turno" (niente radio esito).

---

## Note di formato dati (riferimento per tutti i task)

- `outcome_90` in memoria è un `Outcome` (`HOME`/`DRAW`/`AWAY`); su JSON è il token `"1"`/`"X"`/`"2"` (o `null`).
- `advances` è il **lato** `"home"`/`"away"` (o `null`), sia per le previsioni che per i risultati reali.
- Mapping token ↔ Outcome: `HOME→"1"`, `DRAW→"X"`, `AWAY→"2"`.

---

## Task 1: Estendere i modelli `Outcome`, `MatchPrediction`, `Result`

**Files:**
- Modify: `src/models/match.py`
- Test: `tests/test_models.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
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


if __name__ == "__main__":
    test_outcome_token_roundtrip()
    test_match_prediction_new_fields_default_none()
    test_match_prediction_discordant_fields()
    test_result_advances_default_none()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — `AttributeError: type object 'Outcome' has no attribute 'token'` / `from_token`, e `TypeError` sui campi non esistenti.

- [ ] **Step 3: Implement the model changes**

In `src/models/match.py`, estendi `Outcome` con token helpers:

```python
class Outcome(str, Enum):
    HOME = "home"
    AWAY = "away"
    DRAW = "draw"

    @property
    def token(self) -> str:
        """Rappresentazione 1/X/2 dell'esito."""
        return {"home": "1", "draw": "X", "away": "2"}[self.value]

    @classmethod
    def from_token(cls, token: str) -> "Outcome":
        """Costruisce un Outcome dal token 1/X/2."""
        return {"1": cls.HOME, "X": cls.DRAW, "2": cls.AWAY}[token]
```

Aggiungi `advances` a `Result`:

```python
@dataclass
class Result:
    match_id: str
    home_goals: int
    away_goals: int
    advances: Optional[str] = None  # "home" | "away" — chi passa il turno
```

Aggiungi i due campi a `MatchPrediction` (la property `outcome` resta invariata):

```python
@dataclass
class MatchPrediction:
    match_id: str
    home_goals: int
    away_goals: int
    outcome_90: Optional["Outcome"] = None  # esito esplicito 1/X/2 a 90'
    advances: Optional[str] = None           # "home" | "away" — chi passa il turno

    @property
    def outcome(self) -> Outcome:
        if self.home_goals > self.away_goals:
            return Outcome.HOME
        if self.away_goals > self.home_goals:
            return Outcome.AWAY
        return Outcome.DRAW
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (4 test).

- [ ] **Step 5: Commit**

```bash
git add src/models/match.py tests/test_models.py
git commit -m "feat: campi outcome_90 e advances nei modelli knockout"
```

---

## Task 2: (De)serializzazione di previsioni e risultati

**Files:**
- Modify: `src/models/participant.py`
- Modify: `src/storage/json_storage.py:133-142` (load_results)
- Test: `tests/test_models.py` (Modify — aggiunta test)

- [ ] **Step 1: Write the failing test**

Aggiungi in coda a `tests/test_models.py` (prima del blocco `if __name__`):

```python
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
```

E aggiorna il blocco `if __name__ == "__main__":` aggiungendo le due chiamate:

```python
    test_participant_roundtrip_new_fields()
    test_participant_from_dict_legacy_without_new_fields()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -k participant -v`
Expected: FAIL — `to_dict` non include i nuovi campi (`KeyError "outcome_90"`).

- [ ] **Step 3: Implement serialization**

In `src/models/participant.py`, importa `Outcome` e aggiorna `to_dict`/`from_dict`:

```python
from src.models.match import MatchPrediction, Outcome
```

```python
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "match_predictions": {
                mid: {
                    "home_goals": p.home_goals,
                    "away_goals": p.away_goals,
                    "outcome_90": p.outcome_90.token if p.outcome_90 else None,
                    "advances": p.advances,
                }
                for mid, p in self.match_predictions.items()
            },
            "group_rankings": self.group_rankings,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Participant":
        p = cls(name=data["name"])
        p.match_predictions = {
            mid: MatchPrediction(
                match_id=mid,
                home_goals=v["home_goals"],
                away_goals=v["away_goals"],
                outcome_90=Outcome.from_token(v["outcome_90"]) if v.get("outcome_90") else None,
                advances=v.get("advances"),
            )
            for mid, v in data.get("match_predictions", {}).items()
        }
        p.group_rankings = data.get("group_rankings", {})
        return p
```

In `src/storage/json_storage.py`, aggiorna `load_results` per leggere `advances`:

```python
def load_results() -> Dict[str, Result]:
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        mid: Result(
            match_id=mid,
            home_goals=v["home_goals"],
            away_goals=v["away_goals"],
            advances=v.get("advances"),
        )
        for mid, v in raw.items()
        if v.get("played", False)
    }
```

> `save_results` non cambia: salva il dict così com'è ricevuto, e la pagina Real Results
> includerà `advances` nelle entry (Task 5).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (6 test).

- [ ] **Step 5: Commit**

```bash
git add src/models/participant.py src/storage/json_storage.py tests/test_models.py
git commit -m "feat: serializzazione JSON di outcome_90 e advances"
```

---

## Task 3: Riscrittura dello scoring knockout (C1/C2/C3)

**Files:**
- Modify: `src/scoring/calculator.py:16-21` (dataclass) e `:61-100` (funzione)
- Test: `tests/test_calculator.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_calculator.py`:

```python
"""Test per src/scoring/calculator.py — scoring knockout C1/C2/C3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.match import MatchPrediction, Outcome, Result
from src.models.participant import Participant
from src.scoring.calculator import score_knockout_round


def _p(name, preds):
    p = Participant(name=name)
    p.match_predictions = preds
    return p


def test_criteria_are_independent_on_discordant_match():
    # Reale: 90' = 2-2 (esito X), passa "home". Diff reti reale = 0.
    results = {"S01": Result("S01", 2, 2, advances="home")}
    # Pronostico discordante ma con passaggio e esito corretti, punteggio diverso
    pred = MatchPrediction("S01", 1, 1, outcome_90=Outcome.DRAW, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 1      # C1: home == home
    assert s.correct_outcomes == 1      # C2: X == X (esito esplicito)
    assert s.goal_diff_error == 0       # C3: diff prevista 0, reale 0


def test_wrong_advance_right_outcome():
    results = {"S01": Result("S01", 0, 0, advances="away")}
    pred = MatchPrediction("S01", 0, 0, outcome_90=Outcome.DRAW, advances="home")
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 0      # home != away
    assert s.correct_outcomes == 1      # X == X
    assert s.goal_diff_error == 0


def test_none_fields_earn_nothing_on_c1_c2():
    results = {"S01": Result("S01", 1, 0, advances="home")}
    pred = MatchPrediction("S01", 1, 0)  # outcome_90 e advances = None
    [s] = score_knockout_round([_p("a", {"S01": pred})], results, ["S01"])
    assert s.correct_advances == 0
    assert s.correct_outcomes == 0
    assert s.goal_diff_error == 0       # diff prevista +1, reale +1


def test_ordering_c1_then_c2_then_c3():
    results = {
        "S01": Result("S01", 1, 0, advances="home"),
        "S02": Result("S02", 2, 0, advances="home"),
    }
    # alice: 2 passaggi giusti
    alice = _p("alice", {
        "S01": MatchPrediction("S01", 1, 0, outcome_90=Outcome.HOME, advances="home"),
        "S02": MatchPrediction("S02", 2, 0, outcome_90=Outcome.HOME, advances="home"),
    })
    # bob: 1 passaggio giusto
    bob = _p("bob", {
        "S01": MatchPrediction("S01", 1, 0, outcome_90=Outcome.HOME, advances="home"),
        "S02": MatchPrediction("S02", 0, 1, outcome_90=Outcome.AWAY, advances="away"),
    })
    ranking = score_knockout_round([bob, alice], results, ["S01", "S02"])
    assert [s.name for s in ranking] == ["alice", "bob"]  # C1 alice(2) > bob(1)


if __name__ == "__main__":
    test_criteria_are_independent_on_discordant_match()
    test_wrong_advance_right_outcome()
    test_none_fields_earn_nothing_on_c1_c2()
    test_ordering_c1_then_c2_then_c3()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_calculator.py -v`
Expected: FAIL — `AttributeError: 'KnockoutRoundScore' object has no attribute 'correct_advances'`.

- [ ] **Step 3: Implement the calculator changes**

In `src/scoring/calculator.py`, sostituisci il dataclass `KnockoutRoundScore`:

```python
@dataclass
class KnockoutRoundScore:
    name: str
    correct_advances: int   # C1 — chi passa il turno corretto (higher = better)
    correct_outcomes: int   # C2 — esito 90' (1/X/2) corretto (higher = better)
    goal_diff_error: int    # C3 — errore differenza reti (lower = better)
```

E sostituisci interamente `score_knockout_round`:

```python
def score_knockout_round(
    participants: List[Participant],
    results: Dict[str, Result],
    match_ids: List[str],
) -> List[KnockoutRoundScore]:
    """
    Per ogni partecipante con previsioni per i match_ids dati:
      C1 = passaggi del turno corretti (pred.advances == result.advances)
      C2 = esiti 90' corretti (pred.outcome_90 == result.outcome)
      C3 = somma |diff_reti_predetta - diff_reti_reale| per ogni partita

    Ordinamento: C1 desc, C2 desc, C3 asc.
    Vengono valutate solo le partite con sia la previsione che il risultato reale.
    I campi outcome_90/advances a None non guadagnano C1/C2.
    """
    scores = []
    for p in participants:
        if not any(mid in p.match_predictions for mid in match_ids):
            continue
        correct_advances = 0
        correct_outcomes = 0
        goal_diff_error = 0
        for mid in match_ids:
            pred = p.match_predictions.get(mid)
            result = results.get(mid)
            if pred is None or result is None:
                continue
            if pred.advances is not None and result.advances is not None \
                    and pred.advances == result.advances:
                correct_advances += 1
            if pred.outcome_90 is not None and pred.outcome_90 == result.outcome:
                correct_outcomes += 1
            pred_diff = pred.home_goals - pred.away_goals
            actual_diff = result.home_goals - result.away_goals
            goal_diff_error += abs(pred_diff - actual_diff)
        scores.append(KnockoutRoundScore(
            name=p.name,
            correct_advances=correct_advances,
            correct_outcomes=correct_outcomes,
            goal_diff_error=goal_diff_error,
        ))
    return sorted(scores, key=lambda s: (-s.correct_advances, -s.correct_outcomes, s.goal_diff_error))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_calculator.py -v`
Expected: PASS (4 test).

- [ ] **Step 5: Commit**

```bash
git add src/scoring/calculator.py tests/test_calculator.py
git commit -m "feat: scoring knockout C1=passaggio C2=esito C3=diff reti"
```

---

## Task 4: Metrica "advances" nelle statistiche di consenso

**Files:**
- Modify: `src/scoring/statistics.py:84-118` (knockout_consensus)
- Test: `tests/test_statistics.py` (Modify)

- [ ] **Step 1: Write the failing test**

Aggiungi in `tests/test_statistics.py`, dopo `test_knockout_exact_consensus` (riga ~102). Nota: l'helper `_p` esistente non imposta `advances`, quindi il test costruisce i `MatchPrediction` a mano:

```python
def test_knockout_advances_consensus():
    from src.models.match import MatchPrediction

    def pa(name, side):
        p = Participant(name=name)
        p.match_predictions = {
            "S01": MatchPrediction(match_id="S01", home_goals=0, away_goals=0, advances=side)
        }
        return p

    parts = [pa("a", "home"), pa("b", "home"), pa("c", "away")]
    [ec] = knockout_consensus(parts, ["S01"], "advances")
    assert ec.total == 3
    assert ec.top_count == 2
    assert ec.top_value == "home"
    assert not ec.is_unanimous


def test_knockout_advances_skips_none():
    from src.models.match import MatchPrediction

    p1 = Participant(name="a")
    p1.match_predictions = {"S01": MatchPrediction("S01", 1, 0, advances="home")}
    p2 = Participant(name="b")
    p2.match_predictions = {"S01": MatchPrediction("S01", 1, 0)}  # advances None
    # solo 1 partecipante valido -> evento ignorato (total < 2)
    res = knockout_consensus([p1, p2], ["S01"], "advances")
    assert res == []
```

E aggiungi le chiamate nel blocco `if __name__ == "__main__":` se presente in fondo al file (cerca il blocco e aggiungi `test_knockout_advances_consensus()` e `test_knockout_advances_skips_none()`).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_statistics.py -k advances -v`
Expected: FAIL — `ValueError: metric sconosciuta: 'advances'`.

- [ ] **Step 3: Implement the metric**

In `src/scoring/statistics.py`, aggiorna `knockout_consensus`. Cambia la guardia:

```python
    if metric not in ("outcome", "exact", "advances"):
        raise ValueError(f"metric sconosciuta: {metric!r}")
```

E nel ciclo sui partecipanti sostituisci il blocco `if metric == "outcome": ... else: ...` con:

```python
            if metric == "outcome":
                outcome = _outcome(pred.home_goals, pred.away_goals)
                keys.append(outcome)
                values.append(outcome)
            elif metric == "exact":
                score = (pred.home_goals, pred.away_goals)
                keys.append(score)
                values.append(score)
            else:  # advances
                if pred.advances is None:
                    continue
                keys.append(pred.advances)
                values.append(pred.advances)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_statistics.py -v`
Expected: PASS (tutti, inclusi i 2 nuovi).

- [ ] **Step 5: Commit**

```bash
git add src/scoring/statistics.py tests/test_statistics.py
git commit -m "feat: metrica advances nel consenso knockout"
```

---

## Task 5: UI Make Predictions — radio esito 90' e passaggio

**Files:**
- Modify: `pages/1_Make_Predictions.py` (import, `_save_knockout`, loop slot knockout)

> Pagina Streamlit: nessun unit test, verifica manuale a fine task.

- [ ] **Step 1: Aggiungi l'import di `Outcome`**

In `pages/1_Make_Predictions.py`, riga 4, sostituisci:

```python
from src.models.match import MatchPrediction
```

con:

```python
from src.models.match import MatchPrediction, Outcome
```

- [ ] **Step 2: Aggiorna `_save_knockout` per i nuovi campi**

Sostituisci la funzione `_save_knockout` (righe ~126-135):

```python
def _save_knockout(new_preds: dict) -> None:
    updated = Participant(
        name=name,
        match_predictions={
            mid: MatchPrediction(
                match_id=mid,
                home_goals=v["home_goals"],
                away_goals=v["away_goals"],
                outcome_90=Outcome.from_token(v["outcome_90"]) if v.get("outcome_90") else None,
                advances=v.get("advances"),
            )
            for mid, v in new_preds.items()
        },
    )
    merge_participant(updated)
    update_registry_timestamp(name)
```

- [ ] **Step 3: Aggiungi i due radio nella riga-partita**

Nel ciclo `for match_id in match_ids:` (righe ~213-244), sostituisci la riga finale
`new_preds[match_id] = {"home_goals": int(g1), "away_goals": int(g2)}` con il blocco
seguente (che aggiunge una seconda riga di controlli sotto al punteggio):

```python
            # Riga 2: esito 90' (1/X/2) e chi passa il turno — sempre manuali
            team1_label = entry["home"] if determined else "Team 1"
            team2_label = entry["away"] if determined else "Team 2"

            ctrl = st.columns([3, 0.8, 0.5, 0.8, 3])

            out_opts = ["1", "X", "2"]
            out_current = pred.outcome_90.token if (pred and pred.outcome_90) else None
            out_idx = out_opts.index(out_current) if out_current in out_opts else None
            sel_out = ctrl[0].radio(
                "Esito 90'", out_opts, index=out_idx,
                key=f"out_{match_id}", horizontal=True,
            )

            adv_opts = [team1_label, team2_label]
            adv_current = pred.advances if (pred and pred.advances) else None
            adv_idx = (0 if adv_current == "home" else 1) if adv_current in ("home", "away") else None
            sel_adv = ctrl[4].radio(
                "Passa il turno", adv_opts, index=adv_idx,
                key=f"adv_{match_id}", horizontal=True,
            )
            adv_value = None
            if sel_adv == team1_label:
                adv_value = "home"
            elif sel_adv == team2_label:
                adv_value = "away"

            new_preds[match_id] = {
                "home_goals": int(g1),
                "away_goals": int(g2),
                "outcome_90": sel_out,   # token "1"/"X"/"2" o None
                "advances": adv_value,   # "home"/"away" o None
            }
```

- [ ] **Step 4: Verifica manuale**

Run: `streamlit run Home.py`
Nella pagina **Make Predictions**: scegli un nome, compila i gironi e salva (per sbloccare le fasi knockout), poi vai su **Round of 32**. Per una partita imposta un punteggio (es. `2-2`), esito `X`, e "passa il turno" il Team 2. Salva. Riapri la pagina e verifica che i tre valori siano ricaricati come salvati e indipendenti. Controlla il file `data/predictions/<nome>.json`: la entry dello slot deve avere `"outcome_90": "X"` e `"advances": "away"`.

- [ ] **Step 5: Commit**

```bash
git add pages/1_Make_Predictions.py
git commit -m "feat: input esito 90' e passaggio del turno in Make Predictions"
```

---

## Task 6: UI Real Results — radio "chi passa" per slot knockout

**Files:**
- Modify: `pages/2_Real_Results.py:159-208` (header colonne, riga slot, salvataggio)

> Pagina Streamlit: verifica manuale a fine task.

- [ ] **Step 1: Aggiorna l'header e il numero di colonne**

In `pages/2_Real_Results.py`, dentro `for slot_cfg in knockout_slots:` sostituisci il blocco header
(righe ~165-172) per aggiungere la colonna "Advances". Cambia la lista colonne da
`[1, 3, 1, 0.5, 1, 3, 2]` a `[1, 3, 1, 0.5, 1, 3, 2.5, 1.5]`:

```python
        h = st.columns([1, 3, 1, 0.5, 1, 3, 2.5, 1.5])
        h[0].markdown("**ID**")
        h[1].markdown("**Team 1**")
        h[2].markdown("**Goals**")
        h[3].markdown("")
        h[4].markdown("**Goals**")
        h[5].markdown("**Team 2**")
        h[6].markdown("**Advances**")
        h[7].markdown("**Played**")
```

- [ ] **Step 2: Aggiungi il radio "advances" nella riga e salvalo**

Sostituisci il corpo del `for i in range(1, n_slots + 1):` (righe ~174-203) con:

```python
        for i in range(1, n_slots + 1):
            match_id = f"{prefix}{i:02d}"
            existing = results.get(match_id)
            cols = st.columns([1, 3, 1, 0.5, 1, 3, 2.5, 1.5])
            cols[0].write(match_id)
            _entry = ko_bracket.get(match_id) or {}
            team1_label = _entry.get("home") or "Team 1"
            team2_label = _entry.get("away") or "Team 2"
            cols[1].text_input(
                "sq1", value=_entry.get("home") or "",
                key=f"sq1_{match_id}", label_visibility="collapsed",
            )
            g1 = cols[2].number_input(
                "g1", min_value=0, max_value=20,
                value=existing.home_goals if existing else 0,
                step=1, key=f"g1_{match_id}", label_visibility="collapsed",
            )
            cols[3].write("–")
            g2 = cols[4].number_input(
                "g2", min_value=0, max_value=20,
                value=existing.away_goals if existing else 0,
                step=1, key=f"g2_{match_id}", label_visibility="collapsed",
            )
            cols[5].text_input(
                "sq2", value=_entry.get("away") or "",
                key=f"sq2_{match_id}", label_visibility="collapsed",
            )
            adv_opts = [team1_label, team2_label]
            existing_adv = existing.advances if existing else None
            adv_idx = (0 if existing_adv == "home" else 1) if existing_adv in ("home", "away") else None
            sel_adv = cols[6].radio(
                "Advances", adv_opts, index=adv_idx,
                key=f"adv_{match_id}", horizontal=True, label_visibility="collapsed",
            )
            adv_value = "home" if sel_adv == team1_label else ("away" if sel_adv == team2_label else None)
            played = cols[7].checkbox(
                "Played", value=bool(existing), key=f"played_{match_id}"
            )
            if played:
                new_results[match_id] = {
                    "home_goals": int(g1),
                    "away_goals": int(g2),
                    "played": True,
                    "advances": adv_value,
                }
```

- [ ] **Step 3: Verifica manuale**

Run: `streamlit run Home.py`
Pagina **Real Results** → espandi "Round of 32", per uno slot imposta punteggio `2-2`, "Advances" = Team 2, spunta "Played", salva. Verifica in `data/results/results.json` che la entry abbia `"advances": "away"` e `"played": true`. Riapri la pagina: il radio deve mostrare Team 2 selezionato.

- [ ] **Step 4: Commit**

```bash
git add pages/2_Real_Results.py
git commit -m "feat: inserimento chi passa il turno in Real Results"
```

---

## Task 7: Leaderboard — etichette colonne knockout

**Files:**
- Modify: `pages/4_Leaderboard.py:131-140`

> Pagina Streamlit: verifica manuale.

- [ ] **Step 1: Aggiorna le colonne del DataFrame**

In `pages/4_Leaderboard.py`, sostituisci il blocco `df = pd.DataFrame([...])` (righe ~131-140):

```python
        df = pd.DataFrame([
            {
                "Pos": i,
                "Player": s.name,
                "C1 — Who advances": s.correct_advances,
                "C2 — Outcome (90')": s.correct_outcomes,
                "C3 — Goal-diff error": s.goal_diff_error,
            }
            for i, s in enumerate(scores, 1)
        ])
```

- [ ] **Step 2: Verifica manuale**

Run: `streamlit run Home.py`
Pagina **Leaderboard**: con almeno un partecipante e un risultato knockout inserito (Task 5/6),
verifica che la tabella di fase mostri le colonne `C1 — Who advances`, `C2 — Outcome (90')`,
`C3 — Goal-diff error` senza errori.

- [ ] **Step 3: Commit**

```bash
git add pages/4_Leaderboard.py
git commit -m "feat: etichette C1/C2/C3 aggiornate in Leaderboard"
```

---

## Task 8: Statistics — knockout basato sul passaggio del turno

**Files:**
- Modify: `pages/3_Statistics.py:111-153`

> Pagina Streamlit: verifica manuale.

- [ ] **Step 1: Sostituisci il corpo del tab knockout**

In `pages/3_Statistics.py`, sostituisci l'intero blocco del ciclo `for tab_idx, (phase_keys, phase_label) in enumerate(KNOCKOUT_PHASES, 1):` (righe ~111-153) con:

```python
for tab_idx, (phase_keys, phase_label) in enumerate(KNOCKOUT_PHASES, 1):
    with tabs[tab_idx]:
        st.subheader(f"Consensus — {phase_label}")
        st.caption(
            "One event = one match slot. Metric: **who advances** (chi passa il turno)."
        )

        match_ids = [mid for pk in phase_keys for mid in ko_ids.get(pk, [])]
        if not match_ids:
            st.info("No matches defined for this phase yet.")
            continue

        adv_events = knockout_consensus(participants, match_ids, "advances")

        if not adv_events:
            st.info("We need at least 2 players who've picked who advances in the same match.")
            continue

        def _team_for(label: str, side: str) -> str:
            entry = bracket.get(label) or {}
            if side == "home":
                return entry.get("home") or "Team 1"
            return entry.get("away") or "Team 2"

        st.metric(
            "Who-advances picks everyone agrees on",
            f"{unanimous_count(adv_events)}/{len(adv_events)}",
        )

        top = most_shared(adv_events)
        bottom = least_shared(adv_events)
        c1, c2 = st.columns(2)
        with c1:
            st.success(
                f"🟢 **Crowd favourite: {slot_label(top.label, bracket)}** — {_frac(top)} agree"
                f"\n\nAdvances: {_team_for(top.label, top.top_value)}"
            )
        with c2:
            st.error(
                f"🔴 **Biggest squabble: {slot_label(bottom.label, bracket)}** — {_frac(bottom)} agree"
                f"\n\nAdvances: {_team_for(bottom.label, bottom.top_value)}"
            )

        df = pd.DataFrame([
            {
                "Slot": slot_label(ec.label, bracket),
                "Who-advances — most shared": _frac(ec),
                "Most common pick": _team_for(ec.label, ec.top_value),
            }
            for ec in adv_events
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
```

> Le funzioni `_OUTCOME_LABEL`, `_fmt_outcome`, `_fmt_score` e `_callouts` restano definite ma
> non sono più usate dai tab knockout (le usa ancora il tab Gironi tramite `_callouts`/`_fmt_ranking`).
> Lasciale: rimuoverle è fuori scope e `_fmt_outcome`/`_fmt_score` non danno fastidio.

- [ ] **Step 2: Verifica manuale**

Run: `streamlit run Home.py`
Crea/usa 2+ partecipanti con previsioni knockout su uno stesso slot (almeno il campo "passa il turno").
Pagina **Stats** → tab "Round of 32": deve mostrare una sola metrica (who advances), i due callout
e una tabella con "Most common pick" = nome squadra (o Team 1/Team 2 se non determinato). Nessuna
colonna esito/risultato esatto.

- [ ] **Step 3: Commit**

```bash
git add pages/3_Statistics.py
git commit -m "feat: statistiche knockout basate sul passaggio del turno"
```

---

## Task 9: Aggiornare Rules e README

**Files:**
- Modify: `pages/5_Rules.py:95-132`
- Modify: `README.md` (sezioni "Statistiche", "Make Predictions", "Sistema di punteggio")

- [ ] **Step 1: Aggiorna la pagina Rules**

In `pages/5_Rules.py`, sostituisci il testo del knockout (righe ~95-110) con la nuova descrizione
dei criteri e dell'input a tre valori:

```python
From the **Round of 32** onwards (Round of 32, Round of 16, Quarter-finals, Semi-finals,
Third-place play-off and Final) you predict, for every match and **independently**: the
**exact 90' score**, the **90' outcome** (1/X/2) and **who advances** (these need not agree —
e.g. 2–2 at 90', outcome X, but Team 2 goes through on penalties).

For each phase the ranking is built on **three criteria**, applied in order:

| | Criterion | What it means | Direction |
|---|---|---|:---:|
| **C1** | Who advances | How often you called **who goes through** to the next round | higher = better |
| **C2** | Outcome (90') | How often you nailed the **1/X/2 result after 90 minutes** | higher = better |
| **C3** | Goal-difference error | Sum of the gaps between your predicted **goal difference** and the real one — *tiebreaker* | lower = better |

#### How the ranking is decided

1. First we look at **C1** (who advances): whoever has more sits higher.
2. Tied on C1? **C2** (90' outcome) settles it: the more, the merrier.
3. Still tied? **C3** (goal-difference error) breaks the deadlock: the lower, the better.
```

Poi sostituisci l'esempio (righe ~114-128) con uno coerente con i nuovi criteri:

```python
with st.expander("📊 Worked example — one match"):
    st.markdown(
        """
Your pick: **2–2 at 90'**, outcome **X**, **Team 2** advances ·
Real: **1–1 at 90'** (outcome X), **Team 2** went through on penalties.

| Criterion | Calculation | Outcome |
|---|---|:---:|
| **C1** — who advances | You said Team 2, Team 2 advanced | ✅ +1 |
| **C2** — outcome (90') | You said X, real was X | ✅ +1 |
| **C3** — goal-diff error | predicted diff = 0, real diff = 0 → \\|0−0\\| = **0** | +0 |

You nailed both who advances (C1) and the 90' outcome (C2), with zero goal-difference error (C3).
"""
    )
```

- [ ] **Step 2: Aggiorna il README**

In `README.md`:

(a) Nella tabella "Cosa si pronostica per fase" (righe ~122-129), aggiorna le righe knockout per
indicare i tre valori. Sostituisci le righe da `Round of 32` a `Final` con:

```markdown
| `Round of 32` | 16 match slot: risultato esatto 90' + esito (1/X/2) + chi passa il turno |
| `Round of 16` | 8 match slot: risultato esatto 90' + esito (1/X/2) + chi passa il turno |
| `Quarter-finals` | 4 match slot: risultato esatto 90' + esito (1/X/2) + chi passa il turno |
| `Semi-finals` | 2 match slot: risultato esatto 90' + esito (1/X/2) + chi passa il turno |
| `Final` | Finale 3° posto + Finale: risultato, esito e chi passa il turno |
```

(b) Nella tabella delle statistiche (righe ~198-201), sostituisci la riga `Knockout`:

```markdown
| Knockout | uno slot-partita | **chi passa il turno** (1/2) |
```

E nel paragrafo successivo (riga ~210) sostituisci la nota sugli slot con:

```markdown
> Gli slot knockout mostrano l'id (es. `S01`); una volta che l'Admin ha popolato gli accoppiamenti da API, accanto all'id compaiono le squadre reali (es. `S01 — France vs Sweden`). Il consenso knockout misura **chi i partecipanti danno per qualificato**.
```

(c) Nella sezione "Fase a eliminazione diretta — sistema a criteri" (righe ~263-271), sostituisci la
tabella dei criteri e l'ordinamento:

```markdown
| Criterio | Descrizione | Direzione |
|---|---|---|
| **C1 — Passaggio del turno** | Numero di partite in cui hai indovinato chi passa il turno | più alto = meglio |
| **C2 — Esito 90'** | Numero di esiti 1/X/2 a 90' indovinati | più alto = meglio |
| **C3 — Errore diff. reti** | Somma degli scarti tra differenza reti prevista e reale | più basso = meglio |

Ordinamento: C1 decrescente → C2 decrescente → C3 crescente.

> Risultato esatto, esito a 90' e passaggio del turno si pronosticano in modo **indipendente** e non devono per forza concordare (es. pareggio a 90' ma qualificazione ai rigori).
```

- [ ] **Step 3: Verifica**

Run: `streamlit run Home.py` → pagina **Rules**: tabella e esempio mostrano C1=Who advances,
C2=Outcome (90'), C3=Goal-diff error senza errori di rendering.
Rileggi le sezioni modificate del README per coerenza.

- [ ] **Step 4: Commit**

```bash
git add pages/5_Rules.py README.md
git commit -m "docs: aggiorna Rules e README per i nuovi criteri knockout"
```

---

## Task 10: Suite di test completa

**Files:** nessuna modifica (solo esecuzione)

- [ ] **Step 1: Esegui tutti i test**

Run: `python -m pytest -v`
Expected: PASS per `tests/test_models.py`, `tests/test_calculator.py`,
`tests/test_statistics.py`, `tests/test_knockout_bracket.py`.

- [ ] **Step 2: Se tutto verde, nessun commit necessario**

In caso di fallimenti, correggere il task corrispondente prima di considerare completata la feature.

---

## Self-Review (esito)

- **Spec coverage:** modello (Task 1-2), scoring C1/C2/C3 + rimozione "risultati esatti" (Task 3),
  statistiche su passaggio (Task 4 + Task 8), UI Make Predictions manuale (Task 5), Real Results
  advances (Task 6), Leaderboard (Task 7), Rules+README (Task 9), test (Task 1-4, 10). Migrazione:
  coperta dai default `None` e dal test legacy (Task 2).
- **Placeholder scan:** nessun TBD/TODO; ogni step di codice mostra il codice completo.
- **Type consistency:** `correct_advances`/`correct_outcomes`/`goal_diff_error` usati in modo coerente
  tra Task 3 (definizione) e Task 7 (consumo); token `"1"/"X"/"2"` e lato `"home"/"away"` coerenti
  tra modelli (Task 1-2), UI (Task 5-6) e statistiche (Task 4, 8).
