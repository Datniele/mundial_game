"""Statistiche di consenso sui pronostici.

Per ogni "evento" (un girone nella fase a gironi, uno slot-partita nelle fasi a
eliminazione) si misura il *consenso* tra i partecipanti come dimensione del gruppo
più numeroso che ha fatto lo stesso identico pronostico (la "moda").

Funzioni pure: nessuna dipendenza da Streamlit, così sono testabili in isolamento.
"""
from collections import Counter
from dataclasses import dataclass
from typing import Any, List, Optional

from src.models.match import Outcome
from src.models.participant import Participant


@dataclass
class EventConsensus:
    """Consenso dei partecipanti su un singolo evento.

    Attributes:
        label: identificativo dell'evento (es. "A" per un girone, "S01" per uno slot).
        total: numero di partecipanti che hanno compilato l'evento (denominatore).
        top_count: dimensione del gruppo più numeroso con lo stesso pronostico.
        top_value: il pronostico più comune (lista di squadre per i gironi,
            esito o tupla di gol per il knockout).
    """

    label: str
    total: int
    top_count: int
    top_value: Any

    @property
    def is_unanimous(self) -> bool:
        """True se tutti i partecipanti (almeno 2) hanno fatto lo stesso pronostico."""
        return self.total >= 2 and self.top_count == self.total


def _consensus(label: str, keys: List[Any], values: List[Any]) -> Optional[EventConsensus]:
    """Costruisce un EventConsensus da chiavi di raggruppamento allineate ai valori.

    Restituisce None se i partecipanti con un pronostico valido sono meno di 2.
    """
    if len(keys) < 2:
        return None
    counts = Counter(keys)
    top_key, top_count = counts.most_common(1)[0]
    # recupera il valore "ricco" (es. lista classifica) associato alla chiave più comune
    top_value = next(v for k, v in zip(keys, values) if k == top_key)
    return EventConsensus(label=label, total=len(keys), top_count=top_count, top_value=top_value)


def group_consensus(participants: List[Participant]) -> List[EventConsensus]:
    """Consenso per ogni girone: classifica completa (1°→4°) identica.

    Considera solo i partecipanti che hanno valorizzato tutte e 4 le posizioni del girone.
    I gironi vengono restituiti in ordine alfabetico.
    """
    groups = sorted({g for p in participants for g in p.group_rankings})
    results: List[EventConsensus] = []
    for g in groups:
        keys: List[tuple] = []
        values: List[list] = []
        for p in participants:
            ranking = p.group_rankings.get(g)
            if ranking and len(ranking) == 4 and all(v is not None for v in ranking):
                keys.append(tuple(ranking))
                values.append(list(ranking))
        ec = _consensus(g, keys, values)
        if ec is not None:
            results.append(ec)
    return results


def _outcome(home_goals: int, away_goals: int) -> Outcome:
    if home_goals > away_goals:
        return Outcome.HOME
    if away_goals > home_goals:
        return Outcome.AWAY
    return Outcome.DRAW


def knockout_consensus(
    participants: List[Participant], match_ids: List[str], metric: str
) -> List[EventConsensus]:
    """Consenso per ogni slot-partita di una fase a eliminazione.

    Args:
        participants: partecipanti da analizzare.
        match_ids: id degli slot della fase (es. ["S01", ..., "S16"]).
        metric: "outcome" per l'esito (1/X/2) o "exact" per il risultato esatto.

    Considera, per ogni slot, solo i partecipanti che lo hanno pronosticato.
    """
    if metric not in ("outcome", "exact"):
        raise ValueError(f"metric sconosciuta: {metric!r}")

    results: List[EventConsensus] = []
    for mid in match_ids:
        keys: List[Any] = []
        values: List[Any] = []
        for p in participants:
            pred = p.match_predictions.get(mid)
            if pred is None:
                continue
            if metric == "outcome":
                outcome = _outcome(pred.home_goals, pred.away_goals)
                keys.append(outcome)
                values.append(outcome)
            else:
                score = (pred.home_goals, pred.away_goals)
                keys.append(score)
                values.append(score)
        ec = _consensus(mid, keys, values)
        if ec is not None:
            results.append(ec)
    return results


def most_shared(events: List[EventConsensus]) -> Optional[EventConsensus]:
    """Evento con il gruppo concorde più numeroso (a parità, il primo in ordine)."""
    return max(events, key=lambda e: e.top_count, default=None)


def least_shared(events: List[EventConsensus]) -> Optional[EventConsensus]:
    """Evento con il gruppo concorde più piccolo (il più diviso)."""
    return min(events, key=lambda e: e.top_count, default=None)


def unanimous_count(events: List[EventConsensus]) -> int:
    """Numero di eventi su cui tutti i partecipanti concordano."""
    return sum(1 for e in events if e.is_unanimous)
