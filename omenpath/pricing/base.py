from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional


@dataclass
class PriceResult:
    price: Decimal
    currency: str = "USD"
    finish: str = "nonfoil"
    raw: dict = field(default_factory=dict)


class PriceAdapter:
    source_id: str = ""

    def is_configured(self) -> bool:
        return True

    def fetch(self, card_print) -> List[PriceResult]:
        """Return a list of PriceResults (one per finish) for this print, or []."""
        raise NotImplementedError
