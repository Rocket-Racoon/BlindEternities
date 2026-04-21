from decimal import Decimal
from typing import Optional

from .base import PriceAdapter, PriceResult
from .scryfall import ScryfallAdapter
from .tcgplayer import TCGPlayerAdapter
from .cardmarket import CardmarketAdapter


ADAPTERS = {
    "scryfall":   ScryfallAdapter(),
    "tcgplayer":  TCGPlayerAdapter(),
    "cardmarket": CardmarketAdapter(),
}

USD_PRIORITY = ["user", "tcgplayer", "scryfall"]
EUR_PRIORITY = ["user", "cardmarket", "scryfall"]


def market_value_for(card_print, finish="nonfoil", currency="USD"):
    """
    Returns the best available cached price as Decimal, or None.
    Reads from the PriceQuote cache first (populated by sync_market_prices),
    then falls back to Scryfall data baked into CardPrint.prices.
    """
    from ..models import PriceQuote

    priority = USD_PRIORITY if currency == "USD" else EUR_PRIORITY
    quotes = {
        q.source: q
        for q in PriceQuote.objects.filter(
            card_print=card_print, finish=finish, currency=currency
        )
    }
    for source in priority:
        q = quotes.get(source)
        if q:
            return q.price

    for result in ScryfallAdapter().fetch(card_print):
        if result.finish == finish and result.currency == currency:
            return result.price
    return None


__all__ = [
    "PriceAdapter", "PriceResult",
    "ScryfallAdapter", "TCGPlayerAdapter", "CardmarketAdapter",
    "ADAPTERS", "market_value_for",
]
