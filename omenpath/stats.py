"""
Per-user trade reputation: completed-transaction count and last-completed date.

Trades and sales both count — a "completed trade" here means any transaction
that fully finalized (status=COMPLETED) with the user as a party.
"""
from django.contrib.auth.models import User
from django.db.models import Count, Max, Q

from .models import Transaction, TransactionStatus


def trade_stats_for(user) -> dict:
    """Returns {'count': int, 'last_at': datetime|None} for a single user."""
    if not user or not getattr(user, "id", None):
        return {"count": 0, "last_at": None}
    agg = (
        Transaction.objects
        .filter(status=TransactionStatus.COMPLETED)
        .filter(Q(party_a=user) | Q(party_b=user))
        .aggregate(count=Count("id"), last_at=Max("completed_at"))
    )
    return {"count": agg["count"] or 0, "last_at": agg["last_at"]}


def trade_stats_for_users(users) -> dict:
    """
    Bulk helper. `users` is an iterable of User instances or user IDs.
    Returns {user_id: {'count': int, 'last_at': datetime|None}}.
    """
    user_ids = [u.id if hasattr(u, "id") else u for u in users]
    user_ids = [uid for uid in user_ids if uid is not None]
    if not user_ids:
        return {}

    out = {uid: {"count": 0, "last_at": None} for uid in user_ids}

    a_rows = (
        Transaction.objects
        .filter(status=TransactionStatus.COMPLETED, party_a_id__in=user_ids)
        .values("party_a_id")
        .annotate(count=Count("id"), last_at=Max("completed_at"))
    )
    for row in a_rows:
        cur = out[row["party_a_id"]]
        cur["count"] += row["count"] or 0
        cur["last_at"] = _max_dt(cur["last_at"], row["last_at"])

    b_rows = (
        Transaction.objects
        .filter(status=TransactionStatus.COMPLETED, party_b_id__in=user_ids)
        .values("party_b_id")
        .annotate(count=Count("id"), last_at=Max("completed_at"))
    )
    for row in b_rows:
        cur = out[row["party_b_id"]]
        cur["count"] += row["count"] or 0
        cur["last_at"] = _max_dt(cur["last_at"], row["last_at"])
    return out


def _max_dt(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b
