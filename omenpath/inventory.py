"""
Inventory checks for omenpath transactions.

A "giver" can only promise cards they actually own (in BINDER or TRADELIST,
excluding the auto-generated Recolect collection) and that aren't already
locked in another non-terminal transaction.

`available_quantity` = `owned_quantity` − `reserved_quantity`.
"""
from collections import defaultdict
from typing import Iterable, Optional

from django.contrib.auth.models import User
from django.db.models import Q, Sum

from core.constants import CardCondition, CardFinish, CollectionType
from multiverse.models import CardPrint
from tolarian.models import CollectionItem

from .models import (
    Listing, ListingStatus, ListingType,
    Transaction, TransactionItem, TransactionSide, TransactionStatus,
)


RECOLECT_NAME = "Recolect"

OWNERSHIP_COLLECTION_TYPES = [CollectionType.BINDER, CollectionType.TRADELIST]

NON_TERMINAL_STATUSES = [
    TransactionStatus.PROPOSED,
    TransactionStatus.COUNTER_PROPOSED,
    TransactionStatus.ACCEPTED,
]


class InsufficientInventoryError(Exception):
    """Raised when a giver has been asked to part with cards they don't have available."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) if self.errors else "Insufficient inventory.")


def owned_quantity(*, user: User, card_print: CardPrint, finish: str,
                   condition: str, language: str) -> int:
    total = (
        CollectionItem.objects.filter(
            collection__user=user,
            collection__is_active=True,
            collection__collection_type__in=OWNERSHIP_COLLECTION_TYPES,
            card=card_print.card,
            print=card_print,
            finish=finish,
            condition=condition,
            language=language,
        )
        .exclude(collection__name=RECOLECT_NAME)
        .aggregate(total=Sum("quantity"))["total"]
    )
    return total or 0


def reserved_quantity(*, user: User, card_print: CardPrint, finish: str,
                      condition: str, language: str,
                      exclude_tx: Optional[Transaction] = None,
                      exclude_listing: Optional[Listing] = None) -> int:
    """
    Sum of quantities locked by:
    1. The user's own OPEN SELL listings (an ad reserves what it claims to offer).
    2. The user's non-terminal transactions where they are the giver
       — i.e. FROM_A and party_a, or FROM_B and party_b.

    Sale-tx items tied to one of the user's own SELL listings are excluded from
    (2) so they don't double-count with (1). The listing already reserves them.
    """
    from django.utils import timezone
    now = timezone.now()
    listings_qs = Listing.objects.filter(
        owner=user,
        is_active=True,
        listing_type=ListingType.SELL,
        status=ListingStatus.OPEN,
        card_print=card_print,
        finish=finish,
        condition=condition,
        language=language,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if exclude_listing is not None:
        listings_qs = listings_qs.exclude(pk=exclude_listing.pk)
    listed_total = listings_qs.aggregate(total=Sum("quantity"))["total"] or 0

    tx_qs = TransactionItem.objects.filter(
        card_print=card_print,
        finish=finish,
        condition=condition,
        language=language,
        transaction__status__in=NON_TERMINAL_STATUSES,
    ).filter(
        Q(side=TransactionSide.FROM_A, transaction__party_a=user)
        | Q(side=TransactionSide.FROM_B, transaction__party_b=user)
    ).exclude(
        # Already counted via the listing itself.
        transaction__kind="sale",
        transaction__listing__owner=user,
        transaction__listing__listing_type=ListingType.SELL,
    )
    if exclude_tx is not None:
        tx_qs = tx_qs.exclude(transaction=exclude_tx)
    tx_total = tx_qs.aggregate(total=Sum("quantity"))["total"] or 0

    return listed_total + tx_total


def available_quantity(*, user: User, card_print: CardPrint, finish: str,
                       condition: str, language: str,
                       exclude_tx: Optional[Transaction] = None,
                       exclude_listing: Optional[Listing] = None) -> int:
    return owned_quantity(
        user=user, card_print=card_print, finish=finish,
        condition=condition, language=language,
    ) - reserved_quantity(
        user=user, card_print=card_print, finish=finish,
        condition=condition, language=language,
        exclude_tx=exclude_tx, exclude_listing=exclude_listing,
    )


def _row_key(row):
    """
    Normalize a row (dict from picker/text-parser, or a TransactionItem)
    into a (card_print, finish, condition, language, quantity) tuple.
    """
    if isinstance(row, TransactionItem):
        return (
            row.card_print, row.finish, row.condition, row.language, row.quantity,
        )
    cp = row["card_print"]
    return (
        cp,
        row.get("finish") or CardFinish.NONFOIL,
        row.get("condition") or CardCondition.NEAR_MINT,
        row.get("language") or "en",
        int(row["quantity"]),
    )


def validate_inventory(*, giver: User, rows: Iterable,
                       exclude_tx: Optional[Transaction] = None,
                       exclude_listing: Optional[Listing] = None) -> None:
    """
    Raise InsufficientInventoryError if `giver` cannot cover all of `rows`.
    `rows` is an iterable of either picker-style dicts or TransactionItems.

    Quantities for the same (print, finish, condition, language) are grouped
    so a request for 2+1 of the same card is checked as 3.
    """
    grouped = defaultdict(int)
    cps = {}
    for row in rows:
        cp, finish, condition, language, qty = _row_key(row)
        if qty < 1:
            continue
        key = (cp.pk, finish, condition, language)
        grouped[key] += qty
        cps[cp.pk] = cp

    errors = []
    for (pid, finish, condition, language), needed in grouped.items():
        cp = cps[pid]
        avail = available_quantity(
            user=giver, card_print=cp, finish=finish,
            condition=condition, language=language,
            exclude_tx=exclude_tx, exclude_listing=exclude_listing,
        )
        if avail < needed:
            errors.append(
                f"@{giver.username} has {avail} available of "
                f"{cp.card.name} [{cp.cardset.code.upper()} #{cp.collector_number}] "
                f"({finish}, {condition}, {language}); needs {needed}."
            )
    if errors:
        raise InsufficientInventoryError(errors)
