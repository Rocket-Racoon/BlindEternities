import logging
import time
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

import requests
from django.conf import settings

from .base import PriceAdapter, PriceResult


log = logging.getLogger(__name__)

TOKEN_URL = "https://api.tcgplayer.com/token"
PRICE_URL = "https://api.tcgplayer.com/pricing/product/{ids}"

SUBTYPE_TO_FINISH = {
    "Normal":     "nonfoil",
    "Foil":       "foil",
    "Holofoil":   "foil",
    "Rainbow Foil": "foil",
    "Etched Foil": "etched",
}


class TCGPlayerAdapter(PriceAdapter):
    """
    Fetches pricing by product ID. Requires TCGPLAYER_PUBLIC_KEY / TCGPLAYER_PRIVATE_KEY
    in settings. Uses bearer-token auth, cached in-memory.
    """
    source_id = "tcgplayer"

    _token: Optional[str] = None
    _token_expires_at: Optional[datetime] = None

    def is_configured(self) -> bool:
        return bool(getattr(settings, "TCGPLAYER_PUBLIC_KEY", "") and getattr(settings, "TCGPLAYER_PRIVATE_KEY", ""))

    def _get_token(self) -> str:
        now = datetime.utcnow()
        if self._token and self._token_expires_at and self._token_expires_at > now + timedelta(minutes=1):
            return self._token
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     settings.TCGPLAYER_PUBLIC_KEY,
                "client_secret": settings.TCGPLAYER_PRIVATE_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
        return self._token

    def fetch(self, card_print):
        if not self.is_configured():
            return []
        product_ids = [pid for pid in (card_print.tcgplayer_id, card_print.tcgplayer_etched_id) if pid]
        if not product_ids:
            return []
        token = self._get_token()
        url = PRICE_URL.format(ids=",".join(str(pid) for pid in product_ids))
        resp = requests.get(url, headers={"Authorization": f"bearer {token}"}, timeout=15)
        if resp.status_code == 429:
            time.sleep(1)
            resp = requests.get(url, headers={"Authorization": f"bearer {token}"}, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("results", [])
        results = []
        for row in data:
            market = row.get("marketPrice") or row.get("midPrice")
            if market in (None, 0):
                continue
            finish = SUBTYPE_TO_FINISH.get(row.get("subTypeName") or "", "nonfoil")
            results.append(PriceResult(
                price=Decimal(str(market)),
                currency="USD",
                finish=finish,
                raw=row,
            ))
        return results
