"""
Business logic for omenpath transactions:
- Parsing offered/requested card lines into TransactionItems
- Completing transactions → moving cards into the recipient's "Recolect" collection
"""
import re
from decimal import Decimal
from typing import Iterable

from django.contrib.auth.models import User
from django.db import transaction as db_transaction
from django.utils import timezone

from multiverse.models import Card, CardPrint
from core.constants import CollectionType
from tolarian.models import Collection, CollectionItem

from .models import (
    Transaction, TransactionItem, TransactionSide, TransactionStatus,
    Listing, ListingStatus,
)
from .pricing import market_value_for
from .inventory import InsufficientInventoryError, validate_inventory
from . import notifications


RECOLECT_NAME = "Recolect"

LINE_RE = re.compile(
    r"""^\s*
        (?P<qty>\d+)\s*[xX]?\s+
        (?P<name>[^\[\#\(]+?)
        (?:\s*\[(?P<setcode>[^\]]+)\])?
        (?:\s*\#(?P<cn>\S+))?
        (?:\s*\((?P<finish>foil|etched|nonfoil)\))?
        \s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_card_line(line: str):
    m = LINE_RE.match(line)
    if not m:
        return None
    return {
        "quantity": int(m.group("qty")),
        "name":     m.group("name").strip(),
        "setcode":  (m.group("setcode") or "").strip().lower() or None,
        "cn":       (m.group("cn") or "").strip() or None,
        "finish":   (m.group("finish") or "nonfoil").lower(),
    }


def resolve_print(parsed: dict):
    """Resolve a parsed line to a CardPrint, preferring setcode/collector_number hints."""
    try:
        card = Card.objects.filter(name__iexact=parsed["name"]).first()
    except Card.DoesNotExist:
        return None
    if not card:
        return None
    prints_qs = card.prints.select_related("cardset")
    if parsed["setcode"]:
        prints_qs = prints_qs.filter(cardset__code__iexact=parsed["setcode"])
    if parsed["cn"]:
        prints_qs = prints_qs.filter(collector_number__iexact=parsed["cn"])
    return prints_qs.order_by("-cardset__released_at").first()


def build_items_from_text(text: str):
    """Returns (rows, errors). Each row is dict with CardPrint, quantity, finish."""
    rows, errors = [], []
    for idx, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        parsed = parse_card_line(raw)
        if not parsed:
            errors.append(f"Line {idx}: could not parse '{raw}'")
            continue
        card_print = resolve_print(parsed)
        if not card_print:
            errors.append(f"Line {idx}: no matching card for '{parsed['name']}'")
            continue
        finish = parsed["finish"] if parsed["finish"] in (card_print.finishes or []) else (
            (card_print.finishes or ["nonfoil"])[0]
        )
        rows.append({
            "card_print": card_print,
            "quantity":   parsed["quantity"],
            "finish":     finish,
        })
    return rows, errors


def _create_items(tx: Transaction, rows: Iterable[dict], side: str) -> None:
    from core.constants import CardCondition
    for row in rows:
        cp = row["card_print"]
        TransactionItem.objects.create(
            transaction=tx,
            side=side,
            card_print=cp,
            quantity=row["quantity"],
            finish=row["finish"],
            condition=row.get("condition") or CardCondition.NEAR_MINT,
            language=(row.get("language") or "en"),
            unit_value=market_value_for(cp, finish=row["finish"], currency="USD"),
        )


@db_transaction.atomic
def propose_trade(*, initiator: User, recipient: User, offered_rows, requested_rows, note: str = "") -> Transaction:
    if offered_rows:
        validate_inventory(giver=initiator, rows=offered_rows)
    if requested_rows:
        validate_inventory(giver=recipient, rows=requested_rows)
    tx = Transaction.objects.create(
        kind="trade",
        party_a=initiator,
        party_b=recipient,
        status=TransactionStatus.PROPOSED,
        note=note,
    )
    _create_items(tx, offered_rows, TransactionSide.FROM_A)
    _create_items(tx, requested_rows, TransactionSide.FROM_B)
    db_transaction.on_commit(lambda: notifications.notify_proposed(tx))
    return tx


@db_transaction.atomic
def propose_sale_from_listing(*, buyer: User, listing: Listing, quantity: int, price_agreed=None, note: str = "") -> Transaction:
    """
    Creates a sale Transaction:
    - If listing is type SELL: seller = listing.owner, buyer = buyer, items flow from seller.
    - If listing is type BUY_WANTED: buyer = listing.owner (wants), seller = `buyer` arg (fulfills), items flow from seller.
    """
    if not listing.is_offerable():
        raise ValueError("This listing has expired or is no longer open to offers.")
    if listing.listing_type == "sell":
        seller, buying = listing.owner, buyer
    else:
        seller, buying = buyer, listing.owner
    seller_row = {
        "card_print": listing.card_print,
        "quantity":   min(quantity, listing.quantity),
        "finish":     listing.finish,
        "condition":  listing.condition,
        "language":   listing.language,
    }
    validate_inventory(giver=seller, rows=[seller_row])
    tx = Transaction.objects.create(
        kind="sale",
        party_a=buying,
        party_b=seller,
        listing=listing,
        price_agreed=price_agreed if price_agreed is not None else listing.asking_price,
        status=TransactionStatus.PROPOSED,
        note=note,
    )
    TransactionItem.objects.create(
        transaction=tx,
        side=TransactionSide.FROM_B,
        card_print=listing.card_print,
        condition=listing.condition,
        finish=listing.finish,
        language=listing.language,
        quantity=seller_row["quantity"],
        unit_value=market_value_for(listing.card_print, finish=listing.finish, currency="USD"),
    )
    db_transaction.on_commit(lambda: notifications.notify_proposed(tx))
    return tx


@db_transaction.atomic
def counter_propose(*, tx: Transaction, actor: User, keep_from_b_ids) -> Transaction:
    """
    User B narrows their own side of a PROPOSED trade by removing items.
    `keep_from_b_ids` is the set of TransactionItem IDs (side=FROM_B) B wants to keep.
    Transitions the tx to COUNTER_PROPOSED; party_a then gets to accept or reject.
    """
    if tx.status != TransactionStatus.PROPOSED:
        raise ValueError("Only proposed transactions can be countered.")
    if actor != tx.party_b:
        raise ValueError("Only the recipient can counter.")

    keep_ids = {str(i) for i in (keep_from_b_ids or [])}
    existing_b = list(tx.items_from_b())
    if not existing_b:
        raise ValueError("No items to counter.")
    to_remove = [it for it in existing_b if str(it.id) not in keep_ids]
    kept = [it for it in existing_b if str(it.id) in keep_ids]

    # Don't let the counter empty both sides — that's just a rejection.
    if not kept and not tx.items_from_a().exists():
        raise ValueError("Counter would leave nothing on the table; reject instead.")

    if kept:
        validate_inventory(giver=tx.party_b, rows=kept, exclude_tx=tx)

    for it in to_remove:
        it.delete()

    tx.status = TransactionStatus.COUNTER_PROPOSED
    tx.save(update_fields=["status", "updated_at"])
    db_transaction.on_commit(lambda: notifications.notify_countered(tx))
    return tx


def get_or_create_recolect(user: User) -> Collection:
    col, _ = Collection.objects.get_or_create(
        user=user,
        name=RECOLECT_NAME,
        defaults={
            "description":     "Auto-generated collection receiving cards from completed trades and sales.",
            "collection_type": CollectionType.BINDER,
        },
    )
    return col


def _deposit_items(tx: Transaction, items, giver: User, receiver: User) -> None:
    recolect = get_or_create_recolect(receiver)
    for item in items:
        entry, created = CollectionItem.objects.get_or_create(
            collection=recolect,
            card=item.card_print.card,
            print=item.card_print,
            condition=item.condition,
            finish=item.finish,
            language=item.language,
            defaults={
                "quantity":      item.quantity,
                "acquired_from": giver,
                "acquired_via":  tx,
            },
        )
        if not created:
            entry.quantity = (entry.quantity or 0) + item.quantity
            entry.acquired_from = giver
            entry.acquired_via = tx
            entry.save(update_fields=["quantity", "acquired_from", "acquired_via", "updated_at"])


def _withdraw_items(items, giver: User) -> None:
    """Decrement matching collection entries owned by the giver.

    Pre-validated by `validate_inventory` at finalize time, so a remaining
    shortfall after the loop indicates a race or a data-integrity bug — raise.
    """
    shortfalls = []
    for item in items:
        qs = CollectionItem.objects.filter(
            collection__user=giver,
            collection__collection_type__in=[
                CollectionType.BINDER,
                CollectionType.TRADELIST,
            ],
            card=item.card_print.card,
            print=item.card_print,
            condition=item.condition,
            finish=item.finish,
            language=item.language,
        ).exclude(collection__name=RECOLECT_NAME).order_by("-quantity")
        remaining = item.quantity
        for entry in qs:
            if remaining <= 0:
                break
            take = min(entry.quantity, remaining)
            entry.quantity -= take
            remaining -= take
            if entry.quantity == 0:
                entry.delete()
            else:
                entry.save(update_fields=["quantity", "updated_at"])
        if remaining > 0:
            shortfalls.append(
                f"@{giver.username} short {remaining} of {item.card_print.card.name} "
                f"({item.finish}, {item.condition}, {item.language})."
            )
    if shortfalls:
        raise InsufficientInventoryError(shortfalls)


@db_transaction.atomic
def finalize_transaction(tx: Transaction) -> None:
    """Move cards, close listing. Idempotency protected by status check at call site."""
    if tx.status != TransactionStatus.ACCEPTED:
        raise ValueError("Only accepted transactions can be finalized.")
    if not (tx.confirmed_by_a and tx.confirmed_by_b):
        raise ValueError("Both parties must confirm before finalizing.")

    items_a = list(tx.items_from_a().select_related("card_print__card", "card_print__cardset"))
    items_b = list(tx.items_from_b().select_related("card_print__card", "card_print__cardset"))

    if items_a:
        validate_inventory(giver=tx.party_a, rows=items_a, exclude_tx=tx)
    if items_b:
        validate_inventory(giver=tx.party_b, rows=items_b, exclude_tx=tx)

    _withdraw_items(items_a, tx.party_a)
    _withdraw_items(items_b, tx.party_b)
    _deposit_items(tx, items_a, giver=tx.party_a, receiver=tx.party_b)
    _deposit_items(tx, items_b, giver=tx.party_b, receiver=tx.party_a)

    tx.status = TransactionStatus.COMPLETED
    tx.completed_at = timezone.now()
    tx.save(update_fields=["status", "completed_at", "updated_at"])
    db_transaction.on_commit(lambda: notifications.notify_completed(tx))

    if tx.listing:
        total_moved = sum(i.quantity for i in items_b if tx.listing.card_print_id == i.card_print_id)
        remaining = max(tx.listing.quantity - total_moved, 0)
        tx.listing.quantity = remaining
        if remaining == 0:
            tx.listing.status = ListingStatus.COMPLETED
        tx.listing.save(update_fields=["quantity", "status", "updated_at"])
