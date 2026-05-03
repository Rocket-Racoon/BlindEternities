"""
Commander Honest Scale — operational criteria + the formal scoring algorithm.

This module is the single source of truth for the rubric. The system prompt
in `services.py` is built from `CRITERIA`, `CARD_TAGS`, and `BRACKET_DEFINITIONS`.
The Python-side scoring (`compute_final_score`, `tier_for`, `bracket_for`) is
applied to whatever the LLM returns so the formula is reproducible regardless
of model drift.
"""
from decimal import Decimal
from typing import List, Optional, Tuple


# ──────────────────────────────────────────────
# WotC Commander Bracket System (locked, official rubric)
# ──────────────────────────────────────────────
BRACKET_DEFINITIONS = [
    ("1", "Exhibition", "Ultra-casual, jank, theme decks. No fast mana, no tutors, no Game Changers. Wins are incidental."),
    ("2", "Core",       "Average preconstructed-level power. No Game Changers, no fast mana, no two-card combos before turn 9."),
    ("3", "Upgraded",   "Optimized precon level. Up to 3 Game Changers, no chain tutors, no fast mana, no early infinite combos."),
    ("4", "Optimized",  "High-power. No Game Changer cap, fast mana allowed, but not built explicitly to win as fast as possible."),
    ("5", "cEDH",       "Tournament-tuned. Built to win turn 1–4 against a metagame. Free counterspells, fast mana stacks, redundant wincons."),
]


# ──────────────────────────────────────────────
# Honest Scale — 8 operational criteria
# Each entry produces a JSON key the model must score 0–10 and justify.
# `algorithm_role` flags whether the criterion feeds the weighted final formula.
# ──────────────────────────────────────────────
CRITERIA = [
    {
        "key":   "speed",
        "label": "⚡ Velocidad",
        "question": "¿En qué turno este deck establece presión real y puede cerrar la partida?",
        "interpretation": (
            "Turnos 1–3 = ultra rápido (cEDH); turnos 4–6 = alto poder; "
            "turnos 7–9 = medio; turno 10+ = casual/lento."
        ),
        "extra_fields": [
            ("expected_pressure_turn", "int — turno en que el deck establece presión"),
            ("expected_win_turn",      "int — turno esperado de victoria"),
        ],
        "weight": Decimal("0.20"),
    },
    {
        "key":   "consistency",
        "label": "🔁 Consistencia",
        "question": "¿El deck ejecuta su plan principal en la mayoría de las partidas?",
        "interpretation": (
            "Alta = funciona casi siempre; media = depende del robo; "
            "baja = inconsistente o caótico."
        ),
        "extra_fields": [
            ("redundancy",      "string — high|medium|low"),
            ("critical_pieces", "int — número de cartas únicas indispensables"),
        ],
        "weight": Decimal("0.20"),
    },
    {
        "key":   "access",
        "label": "🔍 Acceso (Card Advantage / Tutores)",
        "question": "¿Qué tan fácil es encontrar las piezas clave (tutores, robo, filtrado)?",
        "interpretation": (
            "Alto = encuentra lo que necesita cuando lo necesita; "
            "medio = depende del robo pero tiene herramientas; bajo = topdeck-dependiente."
        ),
        "extra_fields": [
            ("tutor_count", "int — total de tutores directos"),
            ("draw_quality", "string — efficient|slow|minimal"),
        ],
        "weight": None,  # informational, not in the final formula
    },
    {
        "key":   "mana_efficiency",
        "label": "⚙️ Eficiencia de Maná",
        "question": "¿Qué tan rápido y eficiente desarrolla recursos (curva, ramp, producción)?",
        "interpretation": (
            "Alta = juega más en menos turnos; media = ritmo normal; baja = lento."
        ),
        "extra_fields": [
            ("ramp_fast_count", "int — ramp ≤2 CMC con ≥1 mana neto"),
            ("ramp_slow_count", "int — ramp >2 CMC"),
            ("avg_cmc",         "float — coste de maná medio sin tierras"),
        ],
        "weight": None,  # informational
    },
    {
        "key":   "wincon",
        "label": "🧨 Win Condition",
        "question": "¿Cómo gana el deck (combo compacto, valor escalable, combate)?",
        "interpretation": (
            "Compacta y difícil de interactuar = muy alto poder; "
            "requiere setup largo = poder medio/bajo."
        ),
        "extra_fields": [
            ("type",            "string — compact|scalable|combat"),
            ("pieces_required", "int — cartas mínimas para cerrar"),
            ("interactable",    "string — hard|medium|easy"),
        ],
        "weight": Decimal("0.15"),
    },
    {
        "key":   "interaction",
        "label": "🛡️ Interacción",
        "question": "¿Puede el deck detener a otros jugadores (removal, counters, stax)?",
        "interpretation": (
            "Alta = controla la mesa activamente; media = responde ocasionalmente; "
            "baja = casi no interactúa."
        ),
        "extra_fields": [
            ("removal_count",     "int — removal puntual"),
            ("counterspell_count", "int — counterspells"),
            ("stax_count",        "int — efectos stax/lock"),
        ],
        "weight": Decimal("0.10"),
    },
    {
        "key":   "resilience",
        "label": "🔒 Resiliencia",
        "question": "¿Qué pasa si el deck es interrumpido (recursion, planes B, dependencia del comandante)?",
        "interpretation": (
            "Alta = se recupera fácilmente; media = le cuesta pero sigue; "
            "baja = colapsa si lo frenan."
        ),
        "extra_fields": [
            ("recursion_count",     "int — efectos de recursion"),
            ("protection_count",    "int — protección de piezas clave"),
            ("commander_dependent", "bool — true si depende del comandante"),
        ],
        "weight": Decimal("0.10"),
    },
    {
        "key":   "intent",
        "label": "🎯 Intención",
        "question": "¿Para qué fue construido este deck?",
        "interpretation": (
            "Define cómo deben leerse los demás criterios. "
            "competitive|optimized|casual|jank."
        ),
        "extra_fields": [
            ("label", "string — competitive|optimized|casual|jank"),
        ],
        "weight": None,  # categorical, not numeric
    },
]


# ──────────────────────────────────────────────
# Algorithm components the LLM also scores 0–10
# (these don't appear as criteria in the user-facing rubric,
#  but they feed the weighted final-score formula)
# ──────────────────────────────────────────────
ALGORITHM_COMPONENTS = [
    {
        "key":   "synergy",
        "label": "🔗 Sinergia",
        "description": (
            "Score 0–10 reflejando qué tanto las cartas forman un grafo de "
            "interacciones significativas (combo directo = peso 3, sinergia "
            "fuerte = 2, débil = 1, ninguna = 0). Normalizado al final."
        ),
        "weight": Decimal("0.15"),
    },
    {
        "key":   "card_power_avg",
        "label": "💎 Card Power Score (CPS) promedio",
        "description": (
            "Promedio del Card Power Score = Eficiencia + Flexibilidad + Impacto "
            "para cada carta del mazo, normalizado a 0–10."
        ),
        "weight": Decimal("0.10"),
    },
]


# ──────────────────────────────────────────────
# Card classification tags (preprocessing step from the algorithm)
# ──────────────────────────────────────────────
CARD_TAGS = [
    "RAMP_FAST",        # ≤2 CMC, ≥1 mana neto
    "RAMP_SLOW",        # >2 CMC
    "DRAW_EFFICIENT",   # ≤3 CMC, +2 cartas o engine
    "DRAW_SLOW",
    "TUTOR_DIRECT",     # busca carta específica al battlefield/mano
    "TUTOR_LIMITED",    # condicional o restringido
    "REMOVAL_SINGLE",
    "REMOVAL_MASS",
    "COUNTERSPELL",
    "STAX",
    "PROTECTION",
    "RECURSION",
    "COMBO_PIECE",
    "WINCON",
    "ENABLER",
    "FILLER",
]


# ──────────────────────────────────────────────
# Honest tier — final-score buckets per the spec
# ──────────────────────────────────────────────
HONEST_TIERS = [
    ("cedh",    "cEDH",       Decimal("8.5"), Decimal("10.0")),
    ("high",    "High Power", Decimal("7.0"), Decimal("8.5")),
    ("mid",     "Mid Power",  Decimal("5.0"), Decimal("7.0")),
    ("casual",  "Casual",     Decimal("3.0"), Decimal("5.0")),
    ("jank",    "Jank",       Decimal("0.0"), Decimal("3.0")),
]


def tier_for(final_score) -> Tuple[str, str]:
    """Return (key, label) for the honest tier matching `final_score`."""
    if final_score is None:
        return ("", "")
    score = Decimal(str(final_score))
    for key, label, lo, hi in HONEST_TIERS:
        if lo <= score < hi or (key == "cedh" and score >= lo):
            return (key, label)
    return ("jank", "Jank")


def bracket_for(final_score) -> str:
    """Map the final score to a WotC bracket tier (1–5)."""
    if final_score is None:
        return ""
    score = Decimal(str(final_score))
    if score >= Decimal("8.5"):
        return "5"
    if score >= Decimal("7"):
        return "4"
    if score >= Decimal("5"):
        return "3"
    if score >= Decimal("3"):
        return "2"
    return "1"


# ──────────────────────────────────────────────
# Final score formula
#   FINAL = 0.20·Speed + 0.20·CS + 0.15·SS + 0.15·WCS
#         + 0.10·IS + 0.10·RS + 0.10·CPS_avg
# Weights live on each criterion / component. They sum to 1.0.
# ──────────────────────────────────────────────
def _component_weights() -> List[Tuple[str, Decimal]]:
    pairs: List[Tuple[str, Decimal]] = []
    for crit in CRITERIA:
        if crit["weight"] is not None:
            pairs.append((crit["key"], crit["weight"]))
    for comp in ALGORITHM_COMPONENTS:
        pairs.append((comp["key"], comp["weight"]))
    return pairs


COMPONENT_WEIGHTS: List[Tuple[str, Decimal]] = _component_weights()


def compute_final_score(scores: dict) -> Optional[Decimal]:
    """
    Apply the official weighted formula to the per-axis scores returned by the LLM.
    `scores` is the dict where each key maps to {"score": <0-10>, ...}.
    Returns a Decimal in [0, 10], or None if any required component is missing.
    """
    total = Decimal("0")
    for key, weight in COMPONENT_WEIGHTS:
        entry = scores.get(key) or {}
        raw = entry.get("score")
        if raw is None:
            return None
        try:
            value = Decimal(str(raw))
        except Exception:
            return None
        value = max(Decimal("0"), min(Decimal("10"), value))
        total += value * weight
    return total.quantize(Decimal("0.01"))
