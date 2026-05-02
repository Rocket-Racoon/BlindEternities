"""
Email notifications for omenpath transactions.
Uses Django's configured EMAIL_BACKEND (console in dev, SMTP in prod).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

log = logging.getLogger(__name__)


def _build_url(path: str) -> str:
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{base}{path}" if base else path


def _safe_send(recipient_email: str, subject: str, body: str) -> None:
    if not recipient_email:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@blindeternities.local"),
            recipient_list=[recipient_email],
            fail_silently=True,
        )
    except Exception as exc:
        log.warning("omenpath email send failed: %s", exc)


def _tx_link(tx) -> str:
    return _build_url(reverse("omenpath:transaction-detail", kwargs={"pk": tx.pk}))


def notify_proposed(tx):
    url = _tx_link(tx)
    _safe_send(
        tx.party_b.email,
        subject=f"[Blind Eternities] New {tx.get_kind_display().lower()} proposal from @{tx.party_a.username}",
        body=(
            f"@{tx.party_a.username} has proposed a {tx.get_kind_display().lower()} with you.\n\n"
            f"Review it here: {url}\n"
        ),
    )


def notify_accepted(tx):
    url = _tx_link(tx)
    _safe_send(
        tx.party_a.email,
        subject=f"[Blind Eternities] @{tx.party_b.username} accepted your {tx.get_kind_display().lower()}",
        body=(
            f"@{tx.party_b.username} has accepted your proposal.\n"
            f"Both parties still need to confirm completion once the exchange happens.\n\n"
            f"Details: {url}\n"
        ),
    )


def notify_rejected(tx):
    url = _tx_link(tx)
    _safe_send(
        tx.party_a.email,
        subject=f"[Blind Eternities] @{tx.party_b.username} rejected your {tx.get_kind_display().lower()}",
        body=(
            f"Your proposal was rejected.\n\n"
            f"Details: {url}\n"
        ),
    )


def notify_countered(tx, actor=None):
    """Notify whichever party now has to respond.

    The post-counter status determines the responder:
      - COUNTER_PROPOSED → party_a responds (B just countered)
      - PROPOSED         → party_b responds (A just countered back)
    """
    from .models import TransactionStatus
    if tx.status == TransactionStatus.COUNTER_PROPOSED:
        responder, mover = tx.party_a, tx.party_b
    else:
        responder, mover = tx.party_b, tx.party_a
    url = _tx_link(tx)
    _safe_send(
        responder.email,
        subject=f"[Blind Eternities] @{mover.username} countered your {tx.get_kind_display().lower()} proposal",
        body=(
            f"@{mover.username} adjusted which of their cards they'll include.\n"
            f"Review the updated proposal and accept, reject, or counter back.\n\n"
            f"Details: {url}\n"
        ),
    )


def notify_cancelled(tx):
    url = _tx_link(tx)
    _safe_send(
        tx.party_b.email,
        subject=f"[Blind Eternities] @{tx.party_a.username} cancelled the {tx.get_kind_display().lower()} proposal",
        body=(
            f"The proposal was cancelled by the initiator.\n\n"
            f"Details: {url}\n"
        ),
    )


def notify_completed(tx):
    url = _tx_link(tx)
    body = (
        f"The {tx.get_kind_display().lower()} between @{tx.party_a.username} and "
        f"@{tx.party_b.username} is complete.\nCards have been moved into each party's "
        f"Recolect collection.\n\nDetails: {url}\n"
    )
    subject = f"[Blind Eternities] {tx.get_kind_display()} completed"
    _safe_send(tx.party_a.email, subject, body)
    _safe_send(tx.party_b.email, subject, body)


def notify_confirmed_one_side(tx, confirmer):
    other = tx.other_party(confirmer)
    url = _tx_link(tx)
    _safe_send(
        other.email,
        subject=f"[Blind Eternities] @{confirmer.username} confirmed receipt",
        body=(
            f"@{confirmer.username} has confirmed their side of the exchange.\n"
            f"Once you also confirm, the cards will move to Recolect.\n\n"
            f"Details: {url}\n"
        ),
    )
