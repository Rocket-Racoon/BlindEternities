from decimal import Decimal, InvalidOperation
from typing import Optional

from .base import PriceAdapter, PriceResult


FINISH_KEYS = {
    "nonfoil": ("usd", "eur"),
    "foil":    ("usd_foil", "eur_foil"),
    "etched":  ("usd_etched", "eur_foil"),
}


def _to_decimal(value) -> Optional[Decimal]:
    if value in (None, "", 0):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


class ScryfallAdapter(PriceAdapter):
    """Reads prices already synced onto CardPrint.prices by the `sync_prices` command."""
    source_id = "scryfall"

    def fetch(self, card_print):
        prices = card_print.prices or {}
        results = []
        for finish, (usd_key, eur_key) in FINISH_KEYS.items():
            if finish not in (card_print.finishes or []):
                continue
            usd = _to_decimal(prices.get(usd_key))
            if usd is not None:
                results.append(PriceResult(price=usd, currency="USD", finish=finish, raw={"key": usd_key}))
            eur = _to_decimal(prices.get(eur_key))
            if eur is not None:
                results.append(PriceResult(price=eur, currency="EUR", finish=finish, raw={"key": eur_key}))
        return results
