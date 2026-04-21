from django.db.models import Q

from .models import Transaction, TransactionStatus


def pending_trades(request):
    """Count trades awaiting the current user's action, for the navbar badge."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    count = Transaction.objects.filter(
        Q(party_b=user, status=TransactionStatus.PROPOSED) |
        Q(party_a=user, status=TransactionStatus.COUNTER_PROPOSED),
        is_active=True,
    ).count()
    return {"pending_trade_count": count}
