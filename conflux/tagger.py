"""
Per-card classification agent over local Ollama.

`tag_card` runs one LLM call against a single card and returns a dict of
validated tags + reasoning. `tag_cards_concurrent` fans out across a thread
pool — Ollama serves requests serially per model, but threads still help
when the server batches or when network/JSON-decode overhead dominates.

Tokens are free on local Ollama; the only knob worth tuning is concurrency
(usually 1–8 depending on your GPU's VRAM headroom).
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, List, Optional

import requests
from django.conf import settings

from .vocabulary import (
    VOCABULARY_VERSION,
    build_system_prompt,
    sanity_check_against_oracle,
    validate_tags,
)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Card → prompt
# ──────────────────────────────────────────────
def _resolve(card: Any, *names: str) -> str:
    """Return the first non-empty attribute (or dict key) from `names`."""
    for n in names:
        v = getattr(card, n, None) if not isinstance(card, dict) else card.get(n)
        if v not in (None, ""):
            return str(v)
    return ""


def format_card_for_prompt(card: Any) -> str:
    """Render a multiverse.Card (or a plain dict) as a compact, readable block."""
    name        = _resolve(card, "name")
    mana_cost   = _resolve(card, "mana_cost")
    type_line   = _resolve(card, "type_line", "type")
    oracle_text = _resolve(card, "oracle_text", "text")
    power       = _resolve(card, "power")
    toughness   = _resolve(card, "toughness")
    loyalty     = _resolve(card, "loyalty")

    pt = f"{power}/{toughness}" if power and toughness else ""

    fields = [
        ("Name",        name),
        ("Mana cost",   mana_cost),
        ("Type",        type_line),
        ("P/T",         pt),
        ("Loyalty",     loyalty),
        ("Oracle text", oracle_text),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


# ──────────────────────────────────────────────
# Ollama HTTP
# ──────────────────────────────────────────────
class OllamaError(RuntimeError):
    pass


def _ollama_chat(*, model: str, system: str, user: str, url: str, timeout: int) -> dict:
    resp = requests.post(
        f"{url.rstrip('/')}/api/chat",
        json={
            "model":    model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream":   False,
            "format":   "json",
            "options":  {"temperature": 0.1},
        },
        timeout=timeout,
    )
    if not resp.ok:
        raise OllamaError(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def _parse_payload(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


# ──────────────────────────────────────────────
# Single-card tag
# ──────────────────────────────────────────────
def tag_card(
    card: Any,
    *,
    system_prompt: Optional[str] = None,
    model:   Optional[str] = None,
    url:     Optional[str] = None,
    timeout: Optional[int] = None,
) -> dict:
    """
    Classify a single card. Always returns a dict with these keys:

        function_tags: list[str] — validated against the vocabulary
        theme_tags:    list[str] — validated, allows `tribal:<type>`
        reasoning:     str       — short justification, may be blank
        model_name:    str       — the Ollama model that responded
        vocabulary_version: int  — version stamp for downstream invalidation
        error:         str       — empty on success, error class+message on failure
    """
    model   = model   or getattr(settings, "OLLAMA_MODEL", "llama3.1")
    url     = url     or getattr(settings, "OLLAMA_URL",   "http://localhost:11434")
    timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", 300)
    system  = system_prompt or build_system_prompt()
    user    = format_card_for_prompt(card)

    base = {
        "function_tags": [],
        "theme_tags":    [],
        "reasoning":     "",
        "model_name":    model,
        "vocabulary_version": VOCABULARY_VERSION,
        "error":         "",
    }

    if not user.strip():
        return {**base, "error": "card has no usable fields"}

    try:
        raw     = _ollama_chat(model=model, system=system, user=user, url=url, timeout=timeout)
        content = (raw.get("message") or {}).get("content", "")
        parsed  = _parse_payload(content)
    except Exception as exc:  # noqa: BLE001
        log.exception("tag_card failed for %s", _resolve(card, "name"))
        return {**base, "error": f"{type(exc).__name__}: {exc}"}

    func, theme = validate_tags(parsed.get("function_tags"), parsed.get("theme_tags"))

    # Defensive: drop function tags whose required oracle-text phrasing is absent.
    # Catches the common surface-token errors small models make
    # (e.g. tagging "+2 Mace" as ramp because of the "+2" in the name).
    oracle_text = _resolve(card, "oracle_text", "text")
    func, theme, dropped = sanity_check_against_oracle(func, theme, oracle_text)
    if dropped:
        log.info("dropped unsupported tags %s for %s", dropped, _resolve(card, "name"))

    reasoning = (parsed.get("reasoning") or "").strip()
    return {
        **base,
        "function_tags": func,
        "theme_tags":    theme,
        "reasoning":     reasoning[:500],
    }


# ──────────────────────────────────────────────
# Concurrent fan-out
# ──────────────────────────────────────────────
def tag_cards_concurrent(
    cards: Iterable[Any],
    *,
    concurrency: int = 5,
    model: Optional[str] = None,
    on_progress: Optional[Callable[[int, int, Any, dict], None]] = None,
):
    """
    Fan a card iterable out across a thread pool. Yields `(card, result)`
    tuples as each completes. The original ordering is NOT preserved —
    callers should rely on the card object passed back, not its position.
    """
    cards = list(cards)
    total = len(cards)
    system = build_system_prompt()

    if not cards:
        return

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(tag_card, card, system_prompt=system, model=model): card
            for card in cards
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            card = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # noqa: BLE001 — should never happen, tag_card swallows
                result = {
                    "function_tags": [], "theme_tags": [], "reasoning": "",
                    "model_name": model or "", "vocabulary_version": VOCABULARY_VERSION,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            if on_progress:
                on_progress(i, total, card, result)
            yield card, result
