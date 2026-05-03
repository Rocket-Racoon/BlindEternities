"""
Ollama integration + prompt builder for Conflux deck evaluations.

Flow:
1. Build the system prompt from `rubric.CRITERIA` + `ALGORITHM_COMPONENTS`.
2. POST to Ollama (`/api/chat` with `format=json`).
3. Parse the JSON response into per-axis scores, card tags, combos, narrative.
4. Apply the official weighted formula in Python (`compute_final_score`)
   so the result is reproducible regardless of model drift.
5. Map the final score to a Honest tier and a WotC bracket.
"""
import json
import logging
import threading
import time
from decimal import Decimal
from typing import List, Tuple

import requests
from django.conf import settings
from django.db import close_old_connections

from .models import CardTag, DeckEvaluation, EvaluationStatus
from .rubric import (
    ALGORITHM_COMPONENTS,
    BRACKET_DEFINITIONS,
    CARD_TAGS,
    CRITERIA,
    bracket_for,
    compute_final_score,
    tier_for,
)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Decklist serialization
# ──────────────────────────────────────────────
def serialize_deck(deck) -> Tuple[str, str]:
    """Render a tolarian.Deck as plaintext with zone headers."""
    lines: List[str] = []
    commander_names: List[str] = []

    def block(header: str, qs):
        rows = list(qs.select_related("card"))
        if not rows:
            return
        lines.append(f"// {header}")
        for dc in rows:
            lines.append(f"{dc.quantity} {dc.card.name}")
        lines.append("")

    cmd_qs = deck.commander_cards.select_related("card")
    if cmd_qs.exists():
        commander_names = [dc.card.name for dc in cmd_qs for _ in range(dc.quantity)]
        block("Commander", cmd_qs)
    block("Companion",  deck.companion_cards)
    block("Main",       deck.main_cards)
    block("Sideboard",  deck.sideboard_cards)

    return " // ".join(commander_names), "\n".join(lines).strip()


# ──────────────────────────────────────────────
# Tag enrichment — pull pre-classified tags from the DB and summarize
# ──────────────────────────────────────────────
def _tag_summary_for_deck(deck) -> str:
    """
    Return a compact, LLM-friendly summary of the tagged composition of a Deck:
    counts of each function tag and a short list of theme tags. Empty string
    when no tags are available — the prompt still works, just without the hint.
    """
    if deck is None:
        return ""

    rows = (
        deck.cards
        .filter(is_active=True)
        .select_related("card__conflux_tags")
    )

    func_counts: dict[str, int] = {}
    theme_counts: dict[str, int] = {}
    tagged_cards = 0

    for dc in rows:
        tag = getattr(dc.card, "conflux_tags", None)
        if not tag or tag.error:
            continue
        tagged_cards += 1
        for t in tag.function_tags or []:
            func_counts[t] = func_counts.get(t, 0) + dc.quantity
        for t in tag.theme_tags or []:
            theme_counts[t] = theme_counts.get(t, 0) + dc.quantity

    if tagged_cards == 0:
        return ""

    func_block = ", ".join(
        f"{tag}={count}"
        for tag, count in sorted(func_counts.items(), key=lambda x: -x[1])
    ) or "(none)"
    theme_block = ", ".join(
        f"{tag}={count}"
        for tag, count in sorted(theme_counts.items(), key=lambda x: -x[1])
    ) or "(none)"

    return (
        f"Tag-derived breakdown ({tagged_cards} card(s) tagged):\n"
        f"  Function tags: {func_block}\n"
        f"  Theme tags:    {theme_block}"
    )


# ──────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────
def _criteria_block() -> str:
    parts: List[str] = []
    for crit in CRITERIA:
        weight = f" — peso {crit['weight']}" if crit["weight"] else " — informativo"
        parts.append(
            f"- {crit['key']} ({crit['label']}){weight}\n"
            f"  Pregunta: {crit['question']}\n"
            f"  Interpretación: {crit['interpretation']}"
        )
        for name, desc in crit.get("extra_fields", []):
            parts.append(f"    · {name}: {desc}")
    return "\n".join(parts)


def _components_block() -> str:
    return "\n".join(
        f"- {c['key']} ({c['label']}) — peso {c['weight']}\n  {c['description']}"
        for c in ALGORITHM_COMPONENTS
    )


def _bracket_block() -> str:
    return "\n".join(
        f"  - {tier} ({label}): {desc}"
        for tier, label, desc in BRACKET_DEFINITIONS
    )


def _scores_schema() -> str:
    keys: List[str] = []
    for crit in CRITERIA:
        if crit["key"] == "intent":
            continue  # categorical, separate field below
        extras = "".join(
            f', "{name}": <value>'
            for name, _ in crit.get("extra_fields", [])
        )
        keys.append(f'    "{crit["key"]}": {{"score": <0-10>, "reason": "<text>"{extras}}}')
    for comp in ALGORITHM_COMPONENTS:
        keys.append(f'    "{comp["key"]}": {{"score": <0-10>, "reason": "<text>"}}')
    return ",\n".join(keys)


SYSTEM_TEMPLATE = """Eres un evaluador experto de mazos de Magic: the Gathering Commander (EDH).
Aplicas la rúbrica oficial **Commander Honest Scale** y el sistema **WotC Commander Bracket System**.

# Sistema de Bracket (1–5)
{bracket_block}

# Criterios operativos del Honest Scale
Cada criterio se puntúa 0–10 (mayor = más fuerte) y se justifica en una frase:
{criteria_block}

# Componentes del algoritmo (se puntúan 0–10 también)
{components_block}

# Tags de clasificación de cartas (preprocesamiento)
Para cada carta del mazo, asigna 0..N de estos tags funcionales:
{card_tags}

# Algoritmo
1. Clasifica cada carta con sus tags funcionales.
2. Identifica combos relevantes (piezas, dificultad de interacción, resiliencia).
3. Puntúa cada criterio del Honest Scale 0–10 con una justificación de una frase.
4. Puntúa los componentes del algoritmo (synergy, card_power_avg) 0–10.
5. NO calcules el score final tú: lo calcula el sistema con la fórmula oficial.

# Respuesta
Responde EXCLUSIVAMENTE con JSON válido (sin markdown, sin texto fuera del JSON).
Esquema:
{{
  "scores": {{
{scores_schema}
  }},
  "intent": {{"label": "competitive|optimized|casual|jank", "reason": "<text>"}},
  "card_tags": [
    {{"name": "<card name>", "tags": ["<TAG>", "..."]}}
  ],
  "combos": [
    {{"pieces": ["<card>", "<card>"], "type": "compact|scalable|combat",
      "interactable": "hard|medium|easy", "resilient": <bool>}}
  ],
  "narrative": "<2–4 párrafos: arquetipo, fortalezas, debilidades, sugerencias de upgrade>"
}}
"""

USER_TEMPLATE = """Comandante: {commander}

Decklist:
{decklist}
{tag_summary}"""


def build_messages(*, commander: str, decklist: str, tag_summary: str = "") -> List[dict]:
    system = SYSTEM_TEMPLATE.format(
        bracket_block    = _bracket_block(),
        criteria_block   = _criteria_block(),
        components_block = _components_block(),
        card_tags        = ", ".join(CARD_TAGS),
        scores_schema    = _scores_schema(),
    )
    extra = f"\n\n{tag_summary}\n" if tag_summary else ""
    user = USER_TEMPLATE.format(
        commander   = commander or "(no especificado — infiérelo del decklist si es posible)",
        decklist    = decklist,
        tag_summary = extra,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


# ──────────────────────────────────────────────
# Ollama HTTP call
# ──────────────────────────────────────────────
def _ollama_chat(messages: List[dict]) -> dict:
    url     = getattr(settings, "OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model   = getattr(settings, "OLLAMA_MODEL", "llama3.1")
    timeout = getattr(settings, "OLLAMA_TIMEOUT", 300)

    resp = requests.post(
        f"{url}/api/chat",
        json={
            "model":    model,
            "messages": messages,
            "stream":   False,
            "format":   "json",
            "options":  {"temperature": 0.2},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_llm_payload(raw_content: str) -> dict:
    text = raw_content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    return json.loads(text)


# ──────────────────────────────────────────────
# Background runner
# ──────────────────────────────────────────────
def evaluate_async(eval_id) -> None:
    """Spawn a thread that performs the evaluation. Non-blocking."""
    threading.Thread(target=_run_evaluation, args=(str(eval_id),), daemon=True).start()


def _run_evaluation(eval_id: str) -> None:
    try:
        ev = DeckEvaluation.objects.get(pk=eval_id)
    except DeckEvaluation.DoesNotExist:
        return

    started = time.monotonic()
    ev.status     = EvaluationStatus.RUNNING
    ev.model_name = getattr(settings, "OLLAMA_MODEL", "llama3.1")
    ev.save(update_fields=["status", "model_name", "updated_at"])

    try:
        tag_summary = _tag_summary_for_deck(ev.deck) if ev.deck_id else ""
        messages = build_messages(
            commander   = ev.commander,
            decklist    = ev.decklist_text,
            tag_summary = tag_summary,
        )
        ev.prompt = json.dumps(messages, ensure_ascii=False, indent=2)

        raw = _ollama_chat(messages)
        ev.raw_response = raw

        content = (raw.get("message") or {}).get("content", "")
        parsed  = _parse_llm_payload(content)

        scores = parsed.get("scores") or {}
        ev.honest_scores = scores
        ev.card_tags     = parsed.get("card_tags") or []
        ev.combos        = parsed.get("combos") or []

        intent = parsed.get("intent") or {}
        ev.intent_label  = (intent.get("label") or "")[:20]
        ev.intent_reason = intent.get("reason") or ""

        # Python-side scoring — reproducible regardless of model output.
        final = compute_final_score(scores)
        if final is not None:
            ev.final_score  = final
            ev.honest_tier  = tier_for(final)[0]
            ev.bracket      = bracket_for(final)

        ev.narrative = parsed.get("narrative") or ""

        ev.duration_ms = int((time.monotonic() - started) * 1000)
        ev.status      = EvaluationStatus.COMPLETED
        ev.save()
    except Exception as exc:  # noqa: BLE001 — surface anything to the UI
        log.exception("conflux evaluation %s failed", eval_id)
        ev.duration_ms = int((time.monotonic() - started) * 1000)
        ev.status      = EvaluationStatus.FAILED
        ev.error       = f"{type(exc).__name__}: {exc}"
        ev.save(update_fields=["duration_ms", "status", "error", "updated_at"])
    finally:
        close_old_connections()
