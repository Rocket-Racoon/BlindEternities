import base64
import hashlib
import hmac
import logging
import secrets
import time
from decimal import Decimal
from typing import Optional
from urllib.parse import quote, urlparse

import requests
from django.conf import settings

from .base import PriceAdapter, PriceResult


log = logging.getLogger(__name__)

BASE_URL = "https://api.cardmarket.com/ws/v2.0/output.json"


def _percent_encode(value: str) -> str:
    return quote(str(value), safe="~")


class CardmarketAdapter(PriceAdapter):
    """
    Cardmarket uses OAuth 1.0a HMAC-SHA1 request signing. Credentials from settings:
      CARDMARKET_APP_TOKEN, CARDMARKET_APP_SECRET,
      CARDMARKET_ACCESS_TOKEN, CARDMARKET_ACCESS_TOKEN_SECRET
    Returns the 'trend' price as the primary quote.
    """
    source_id = "cardmarket"

    def is_configured(self) -> bool:
        return all([
            getattr(settings, "CARDMARKET_APP_TOKEN", ""),
            getattr(settings, "CARDMARKET_APP_SECRET", ""),
            getattr(settings, "CARDMARKET_ACCESS_TOKEN", ""),
            getattr(settings, "CARDMARKET_ACCESS_TOKEN_SECRET", ""),
        ])

    def _sign(self, method: str, url: str) -> str:
        parsed = urlparse(url)
        realm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        params = {
            "oauth_consumer_key":     settings.CARDMARKET_APP_TOKEN,
            "oauth_token":            settings.CARDMARKET_ACCESS_TOKEN,
            "oauth_nonce":            secrets.token_hex(16),
            "oauth_timestamp":        str(int(time.time())),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_version":          "1.0",
        }
        if parsed.query:
            for pair in parsed.query.split("&"):
                k, _, v = pair.partition("=")
                params[k] = v
        sorted_params = "&".join(
            f"{_percent_encode(k)}={_percent_encode(v)}"
            for k, v in sorted(params.items())
        )
        base_string = "&".join([
            method.upper(),
            _percent_encode(realm),
            _percent_encode(sorted_params),
        ])
        signing_key = f"{_percent_encode(settings.CARDMARKET_APP_SECRET)}&{_percent_encode(settings.CARDMARKET_ACCESS_TOKEN_SECRET)}"
        signature = base64.b64encode(
            hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        ).decode()
        params["oauth_signature"] = signature
        header_params = {k: v for k, v in params.items() if k.startswith("oauth_")}
        header_params["realm"] = realm
        header = "OAuth " + ", ".join(
            f'{k}="{_percent_encode(v)}"' for k, v in header_params.items()
        )
        return header

    def fetch(self, card_print):
        if not self.is_configured():
            return []
        if not card_print.cardmarket_id:
            return []
        url = f"{BASE_URL}/products/{card_print.cardmarket_id}"
        headers = {"Authorization": self._sign("GET", url)}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 429:
            time.sleep(2)
            headers = {"Authorization": self._sign("GET", url)}
            resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        product = resp.json().get("product", {})
        guide = product.get("priceGuide") or {}
        trend = guide.get("TREND") or guide.get("AVG") or guide.get("LOW")
        if trend in (None, 0):
            return []
        return [PriceResult(
            price=Decimal(str(trend)),
            currency="EUR",
            finish="nonfoil",
            raw=guide,
        )]
