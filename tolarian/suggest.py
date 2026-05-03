"""
Tag-based card-suggestion engine for the deck-build modal.

Given a Deck and (optionally) some user-selected tag filters / type filters
/ free-text query, return a ranked list of `Suggestion` objects scored by
tag overlap with the deck. Filters out:

  - cards illegal in the deck's format
  - cards outside the deck's color identity (Commander, Brawl, Oathbreaker)
  - cards already at max copies in the deck

Uses `conflux.CardTag` for the tag data — only cards that have been tagged
participate in suggestions.
"""
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Set

from django.db.models import Q, Sum

from core.constants import MagicFormat
from multiverse.models import Card
from .models import DeckCard


SINGLETON_FORMATS = {
    MagicFormat.COMMANDER,
    MagicFormat.BRAWL,
    MagicFormat.OATHBREAKER,
}
CONSTRUCTED_FORMATS = {
    MagicFormat.STANDARD, MagicFormat.PIONEER, MagicFormat.MODERN,
    MagicFormat.LEGACY, MagicFormat.VINTAGE, MagicFormat.PAUPER,
}

# Card type tokens we expose as filter chips in the modal.
TYPE_FILTERS = [
    "Creature", "Instant", "Sorcery", "Enchantment",
    "Artifact", "Planeswalker", "Battle", "Land",
]

# How many tags we treat as "the deck's profile" when no user filter is set.
AUTO_TOP_TAGS = 8


# ──────────────────────────────────────────────
# Data shapes
# ──────────────────────────────────────────────
@dataclass
class Suggestion:
    card: Card
    score: int
    matched_tags: List[str]
    in_deck_qty: int
    in_deck_rows: List[DeckCard]            # zero or more (one per zone+print combo)
    function_tags: List[str] = field(default_factory=list)
    theme_tags: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Per-deck helpers
# ──────────────────────────────────────────────
def deck_color_identity(deck) -> Optional[Set[str]]:
    """
    Union of color identities of the deck's commander(s). Returns None for
    formats that don't enforce color identity. Returns an empty set for
    colorless commanders (e.g. Kozilek decks).
    """
    if deck.format not in SINGLETON_FORMATS:
        return None
    ident: Set[str] = set()
    rows = deck.commander_cards.select_related("card")
    for dc in rows:
        for color in (dc.card.color_identity or []):
            ident.add(color)
    return ident


def deck_card_qty_map(deck) -> dict:
    """{card_pk: total_qty} across all zones, summed."""
    rows = (
        DeckCard.objects.filter(deck=deck)
        .values("card_id")
        .annotate(total=Sum("quantity"))
    )
    return {r["card_id"]: r["total"] or 0 for r in rows}


def deck_card_rows_map(deck) -> dict:
    """{card_pk: [DeckCard, ...]} — fully fetched rows so the UI can show
    per-zone quantities and decrement."""
    out: dict = {}
    rows = (
        DeckCard.objects.filter(deck=deck)
        .select_related("card", "print__cardset")
    )
    for dc in rows:
        out.setdefault(dc.card_id, []).append(dc)
    return out


def deck_tag_aggregate(deck) -> dict:
    """{tag: weighted_count} across the deck's cards, weighted by quantity."""
    counts: dict = {}
    rows = (
        DeckCard.objects.filter(deck=deck)
        .select_related("card__conflux_tags")
    )
    for dc in rows:
        tag = getattr(dc.card, "conflux_tags", None)
        if not tag or tag.error:
            continue
        for t in (tag.function_tags or []) + (tag.theme_tags or []):
            counts[t] = counts.get(t, 0) + dc.quantity
    return counts


# ──────────────────────────────────────────────
# Filters
# ──────────────────────────────────────────────
def _max_copies(card: Card, deck_format: str) -> Optional[int]:
    """None = unlimited."""
    if card.has_deck_limit and card.max_deck_copies == 0:
        return None
    if card.has_deck_limit and card.max_deck_copies:
        return card.max_deck_copies
    if deck_format in SINGLETON_FORMATS:
        return 1
    if deck_format in CONSTRUCTED_FORMATS:
        return 4
    return None


def _is_format_legal(card: Card, format_key: str) -> bool:
    legality = getattr(card, "legality", None)
    if legality is None:
        return False
    status = legality.data.get(format_key, "not_legal")
    return status in ("legal", "restricted")


def _within_color_identity(card: Card, identity: Set[str]) -> bool:
    return set(card.color_identity or []) <= identity


def _matches_types(card: Card, types: Iterable[str]) -> bool:
    """Type tokens are matched against card.type_line case-insensitively."""
    if not types:
        return True
    line = (card.type_line or "").lower()
    return any(t.lower() in line for t in types)


# ──────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────
def suggest_cards(
    deck,
    *,
    tags: Optional[List[str]] = None,
    types: Optional[List[str]] = None,
    query: str = "",
    limit: int = 40,
) -> List[Suggestion]:
    """
    Rank candidate cards for the suggest modal.

    - `tags` (multi-select chips): if provided, only cards with at least one
       of these tags qualify, and the score = number of selected tags matched.
    - `tags` empty: auto-suggest using the deck's top tags. Score = matches
       weighted by deck-tag frequency.
    - `types`: filter by card type (token in `type_line`).
    - `query`: case-insensitive substring match on `name`.
    """
    fmt           = deck.format
    color_id      = deck_color_identity(deck)
    qty_map       = deck_card_qty_map(deck)
    rows_map      = deck_card_rows_map(deck)
    deck_tag_freq = deck_tag_aggregate(deck)

    # Auto-suggest fallback: top tags by quantity-weighted frequency.
    auto_mode = not tags
    if auto_mode:
        target_tags = [
            t for t, _ in sorted(deck_tag_freq.items(), key=lambda x: -x[1])[:AUTO_TOP_TAGS]
        ]
    else:
        target_tags = list(tags)

    if not target_tags:
        # New empty deck with no tags yet — nothing to score against.
        return []

    qs = (
        Card.objects
        .filter(is_active=True, conflux_tags__isnull=False)
        .exclude(conflux_tags__error__gt="")
        .select_related("conflux_tags", "legality")
        .prefetch_related("prints__cardset")
    )

    if query:
        qs = qs.filter(name__icontains=query)

    if types:
        type_q = Q()
        for t in types:
            type_q |= Q(type_line__icontains=t)
        qs = qs.filter(type_q)

    suggestions: List[Suggestion] = []
    target_set = set(target_tags)

    for card in qs.iterator(chunk_size=500):
        # Format legality
        if not _is_format_legal(card, fmt):
            continue

        # Color identity (singleton formats only)
        if color_id is not None and not _within_color_identity(card, color_id):
            continue

        # At-max filter
        existing = qty_map.get(card.id, 0)
        max_allowed = _max_copies(card, fmt)
        if max_allowed is not None and existing >= max_allowed:
            continue

        tag_obj = card.conflux_tags
        all_tags = list(tag_obj.function_tags or []) + list(tag_obj.theme_tags or [])
        matched = [t for t in all_tags if t in target_set]
        if not matched:
            continue

        # Score: in auto mode weight by deck frequency; in user-tags mode
        # use raw count of matched tags (so 3 matches > 1 match).
        if auto_mode:
            score = sum(deck_tag_freq.get(t, 0) for t in matched)
        else:
            score = len(matched)

        suggestions.append(Suggestion(
            card           = card,
            score          = score,
            matched_tags   = matched,
            in_deck_qty    = existing,
            in_deck_rows   = rows_map.get(card.id, []),
            function_tags  = list(tag_obj.function_tags or []),
            theme_tags     = list(tag_obj.theme_tags or []),
        ))

    # Sort: score desc, then edhrec_rank asc (lower rank = more played).
    suggestions.sort(
        key=lambda s: (-s.score, s.card.edhrec_rank or 10**9, s.card.name.lower())
    )
    return suggestions[:limit]


def default_print_for(card: Card):
    """
    Pick the latest non-digital, non-promo print with a normal image.
    Falls back through digital/promo if no other print qualifies.
    """
    prefetched = list(card.prints.all()) if hasattr(card, "_prefetched_objects_cache") else None
    prints = prefetched if prefetched is not None else list(
        card.prints.select_related("cardset").order_by("-cardset__released_at")
    )
    if not prints:
        return None
    # Pass 1 — pristine
    for p in prints:
        if not p.digital and not p.promo and p.image_normal:
            return p
    # Pass 2 — allow promo
    for p in prints:
        if not p.digital and p.image_normal:
            return p
    # Pass 3 — anything with an image
    for p in prints:
        if p.image_normal:
            return p
    return prints[0]
