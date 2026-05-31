"""
Scraper risultati reali - da completare quando il sito sorgente sarà comunicato.

Interfaccia attesa:
    scrape_results() -> dict[str, dict]

Il dizionario restituito deve avere questa struttura:
{
    "A1": {"home_goals": 2, "away_goals": 1, "played": True},
    "A2": {"home_goals": 0, "away_goals": 0, "played": False},
    ...
}

Le chiavi corrispondono agli ID partita in data/fixtures/fixtures.json.
"""

from typing import Dict


def scrape_results(url: str = "") -> Dict[str, dict]:
    """
    Scarica i risultati reali dal sito indicato e li restituisce
    nel formato atteso dallo storage.

    Args:
        url: URL del sito da cui fare scraping (verrà comunicato dall'utente).

    Returns:
        Dizionario match_id -> {home_goals, away_goals, played}.
    """
    raise NotImplementedError(
        "Scraper non ancora implementato. "
        "Comunicare il sito sorgente per completare questa funzione."
    )


def scrape_group_rankings(url: str = "") -> Dict[str, list]:
    """
    Scarica le classifiche finali dei gironi.

    Returns:
        Dizionario girone -> [1° posto, 2° posto]
    """
    raise NotImplementedError(
        "Scraper non ancora implementato."
    )
