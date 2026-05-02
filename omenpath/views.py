import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView,
)

from core.constants import CardCondition, CardFinish, CollectionType
from tolarian.models import CollectionItem
from multiverse.models import CardSet

from core.mixins import OwnerRequiredMixin
from core.utils import paginate_queryset
from multiverse.models import CardPrint

from .forms import ListingForm, TradeProposeForm, SaleProposeForm
from .inventory import InsufficientInventoryError
from .models import (
    Listing, ListingStatus, ListingType, ListingVisibility,
    Transaction, TransactionStatus,
)
from . import services, notifications


def _friend_ids(user):
    if hasattr(user, "profile"):
        return list(user.profile.friends().values_list("id", flat=True))
    return []


SCOPE_CHOICES = [
    ("all",     "All visible"),
    ("public",  "Public only"),
    ("friends", "Friends only"),
    ("mine",    "My listings"),
]

SORT_CHOICES = [
    ("newest",     "Newest"),
    ("oldest",     "Oldest"),
    ("price_asc",  "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("name",       "Card name (A–Z)"),
]


def _decimal_param(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        from decimal import Decimal, InvalidOperation
        val = Decimal(raw)
        return val if val >= 0 else None
    except Exception:
        return None


class ListingListView(LoginRequiredMixin, TemplateView):
    template_name = "omenpath/listing_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        params = self.request.GET

        qs = (
            Listing.objects
            .filter(is_active=True, status=ListingStatus.OPEN)
            .select_related("owner", "card_print__card", "card_print__cardset")
        )

        listing_type = params.get("type")
        if listing_type in dict(ListingType.choices):
            qs = qs.filter(listing_type=listing_type)
        else:
            listing_type = ""

        search = params.get("q", "").strip()
        if search:
            qs = qs.filter(card_print__card__name__icontains=search)

        condition = params.get("condition")
        if condition in dict(CardCondition.choices):
            qs = qs.filter(condition=condition)
        else:
            condition = ""

        finish = params.get("finish")
        if finish in dict(CardFinish.choices):
            qs = qs.filter(finish=finish)
        else:
            finish = ""

        set_code = (params.get("set") or "").strip().lower()
        if set_code:
            qs = qs.filter(card_print__cardset__code__iexact=set_code)

        price_min = _decimal_param(params.get("price_min"))
        price_max = _decimal_param(params.get("price_max"))
        if price_min is not None or price_max is not None:
            qs = qs.exclude(asking_price__isnull=True)
            if price_min is not None:
                qs = qs.filter(asking_price__gte=price_min)
            if price_max is not None:
                qs = qs.filter(asking_price__lte=price_max)

        friend_ids = _friend_ids(user)
        scope = params.get("scope") or "all"
        if scope == "mine":
            visible = qs.filter(owner=user)
        elif scope == "public":
            visible = qs.filter(visibility=ListingVisibility.PUBLIC).exclude(owner=user)
        elif scope == "friends":
            visible = qs.filter(
                visibility=ListingVisibility.FRIENDS, owner_id__in=friend_ids,
            ).exclude(owner=user)
        else:
            scope = "all"
            visible = qs.filter(
                Q(visibility=ListingVisibility.PUBLIC)
                | Q(owner=user)
                | Q(visibility=ListingVisibility.FRIENDS, owner_id__in=friend_ids)
            )

        sort = params.get("sort") or "newest"
        if sort == "oldest":
            visible = visible.order_by("created_at")
        elif sort == "price_asc":
            visible = visible.exclude(asking_price__isnull=True).order_by("asking_price", "-created_at")
        elif sort == "price_desc":
            visible = visible.exclude(asking_price__isnull=True).order_by("-asking_price", "-created_at")
        elif sort == "name":
            visible = visible.order_by("card_print__card__name", "-created_at")
        else:
            sort = "newest"
            visible = visible.order_by("-created_at")

        # Sets that currently have at least one open listing — keeps the dropdown short and useful.
        active_sets = (
            CardSet.objects
            .filter(prints__listings__is_active=True,
                    prints__listings__status=ListingStatus.OPEN)
            .distinct()
            .order_by("name")
        )

        active_filters_count = sum(1 for v in [
            condition, finish, set_code,
            price_min, price_max,
        ] if v not in (None, "", 0))

        ctx.update({
            "listings":             paginate_queryset(visible, params.get("page"), 24),
            "listing_type":         listing_type,
            "q":                    search,
            "condition":            condition,
            "finish":               finish,
            "set_code":             set_code,
            "price_min":            params.get("price_min", "") if price_min is not None else "",
            "price_max":            params.get("price_max", "") if price_max is not None else "",
            "scope":                scope,
            "sort":                 sort,
            "active_filters_count": active_filters_count,
            "active_sets":          active_sets,
            "ListingType":          ListingType,
            "CardCondition":        CardCondition,
            "CardFinish":           CardFinish,
            "SCOPE_CHOICES":        SCOPE_CHOICES,
            "SORT_CHOICES":         SORT_CHOICES,
        })
        return ctx


class ListingDetailView(LoginRequiredMixin, DetailView):
    model = Listing
    template_name = "omenpath/listing_detail.html"
    context_object_name = "listing"

    def get_queryset(self):
        return Listing.objects.select_related(
            "owner", "card_print__card", "card_print__cardset"
        )

    def dispatch(self, request, *args, **kwargs):
        listing = self.get_object()
        if listing.visibility == ListingVisibility.FRIENDS and listing.owner != request.user:
            if listing.owner_id not in _friend_ids(request.user):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .pricing import market_value_for
        cp = self.object.card_print
        ctx["market_value"] = market_value_for(cp, finish=self.object.finish, currency="USD")
        ctx["sale_form"] = SaleProposeForm(initial={
            "quantity": 1,
            "price_agreed": self.object.asking_price,
        })
        return ctx


class ListingCreateView(LoginRequiredMixin, CreateView):
    model = Listing
    form_class = ListingForm
    template_name = "omenpath/listing_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.card_print = None
        cp_id = request.GET.get("print")
        if cp_id:
            self.card_print = get_object_or_404(CardPrint, pk=cp_id)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if self.card_print:
            initial["card_print"] = self.card_print.pk
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["card_print"] = self.card_print
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Listing published.")
        return super().form_valid(form)


class ListingUpdateView(OwnerRequiredMixin, UpdateView):
    model = Listing
    form_class = ListingForm
    template_name = "omenpath/listing_form.html"
    owner_field = "owner"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["card_print"] = self.object.card_print
        return ctx


class ListingDeleteView(OwnerRequiredMixin, DeleteView):
    model = Listing
    template_name = "omenpath/listing_confirm_delete.html"
    success_url = reverse_lazy("omenpath:listing-list")
    owner_field = "owner"


class TransactionInboxView(LoginRequiredMixin, TemplateView):
    template_name = "omenpath/transaction_inbox.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        base = Transaction.objects.filter(Q(party_a=user) | Q(party_b=user)).select_related(
            "party_a", "party_b", "listing__card_print__card"
        ).prefetch_related("items__card_print__card")
        ctx.update({
            "incoming":  base.filter(party_b=user, status=TransactionStatus.PROPOSED),
            "outgoing":  base.filter(party_a=user, status=TransactionStatus.PROPOSED),
            "countered_for_me": base.filter(party_a=user, status=TransactionStatus.COUNTER_PROPOSED),
            "my_counters":      base.filter(party_b=user, status=TransactionStatus.COUNTER_PROPOSED),
            "active":    base.filter(status=TransactionStatus.ACCEPTED),
            "completed": base.filter(status=TransactionStatus.COMPLETED)[:20],
            "rejected":  base.filter(status__in=[TransactionStatus.REJECTED, TransactionStatus.CANCELLED])[:10],
        })
        return ctx


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = "omenpath/transaction_detail.html"
    context_object_name = "tx"

    def get_queryset(self):
        return Transaction.objects.select_related(
            "party_a", "party_b", "listing__card_print__card"
        ).prefetch_related("items__card_print__card", "items__card_print__cardset")

    def dispatch(self, request, *args, **kwargs):
        tx = self.get_object()
        if not tx.is_party(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _tradable_items_for(user):
    """
    Returns CollectionItems the user has explicitly marked as tradable
    (CollectionType.TRADELIST — "For Trade"). Binders are not implicitly tradable.
    Visibility is governed upstream: callers ensure the viewer is the owner or an
    accepted friend before exposing these items.
    """
    return (
        CollectionItem.objects
        .filter(
            collection__user=user,
            collection__is_active=True,
            collection__collection_type=CollectionType.TRADELIST,
        )
        .select_related("card", "print__cardset", "collection")
        .order_by("card__name", "collection__name")
    )


@login_required
def tradable_search_json(request):
    """
    JSON autocomplete for the trade builder.
    Returns up to 15 tradelist items matching `q` for the requested `user_id`.
    - If user_id == current user: all their tradelist items.
    - Otherwise: must be a friend, and only public tradelists count.
    """
    q = (request.GET.get("q") or "").strip()
    user_id = request.GET.get("user_id")
    if not user_id or len(q) < 2:
        return JsonResponse({"results": []})

    try:
        target = User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError):
        return JsonResponse({"results": []})

    if target != request.user:
        friend_ids = _friend_ids(request.user)
        if target.pk not in friend_ids:
            raise PermissionDenied

    qs = _tradable_items_for(target).filter(card__name__icontains=q)[:15]
    return JsonResponse({"results": _serialize_items(qs)})


def _serialize_items(items):
    from .pricing import market_value_for
    out = []
    for i in items:
        if not i.print_id:
            continue
        value = market_value_for(i.print, finish=i.finish, currency="USD")
        out.append({
            "id":         str(i.id),
            "print_id":   str(i.print_id),
            "card_name":  i.card.name,
            "set_code":   (i.print.cardset.code.upper() if i.print and i.print.cardset else ""),
            "cn":         (i.print.collector_number if i.print else ""),
            "image":      (i.print.image_small if i.print else ""),
            "quantity":   i.quantity,
            "finish":     i.finish,
            "condition":  i.condition,
            "language":   i.language,
            "collection": i.collection.name,
            "unit_value": float(value) if value is not None else None,
        })
    return out


class TradeProposeView(LoginRequiredMixin, TemplateView):
    template_name = "omenpath/trade_propose.html"

    def _recipient(self, pk):
        if not pk:
            return None
        try:
            friends_qs = (
                self.request.user.profile.friends()
                if hasattr(self.request.user, "profile")
                else User.objects.exclude(pk=self.request.user.pk)
            )
            return friends_qs.filter(pk=pk).first()
        except (ValueError, TypeError):
            return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        form = kwargs.get("form") or TradeProposeForm(user=user, initial={
            "recipient": self.request.GET.get("to") or None,
        })

        recipient_pk = (
            self.request.POST.get("recipient")
            or self.request.GET.get("to")
            or form.initial.get("recipient")
        )
        recipient = self._recipient(recipient_pk)

        my_cards   = _serialize_items(_tradable_items_for(user))
        their_cards = _serialize_items(_tradable_items_for(recipient)) if recipient else []

        ctx.update({
            "form":          form,
            "parse_errors":  kwargs.get("parse_errors", []),
            "recipient":     recipient,
            "my_cards":      my_cards,
            "their_cards":   their_cards,
        })
        return ctx

    def _resolve_selection(self, payload_str):
        """Parse a JSON list of {print_id, qty, finish} selections into rows."""
        rows = []
        errors = []
        try:
            data = json.loads(payload_str or "[]")
        except json.JSONDecodeError:
            return rows, ["Invalid selection payload."]
        if not isinstance(data, list):
            return rows, ["Invalid selection payload."]
        from core.constants import CardCondition
        for entry in data:
            pid = entry.get("print_id")
            qty = int(entry.get("qty", 1) or 1)
            if not pid or qty < 1:
                continue
            cp = CardPrint.objects.filter(pk=pid).select_related("card").first()
            if not cp:
                errors.append(f"Unknown print id {pid}")
                continue
            finish = entry.get("finish") or "nonfoil"
            if finish not in (cp.finishes or ["nonfoil"]):
                finish = (cp.finishes or ["nonfoil"])[0]
            condition = entry.get("condition") or CardCondition.NEAR_MINT
            if condition not in dict(CardCondition.choices):
                condition = CardCondition.NEAR_MINT
            language = (entry.get("language") or "en").strip() or "en"
            rows.append({
                "card_print": cp,
                "quantity":   qty,
                "finish":     finish,
                "condition":  condition,
                "language":   language,
            })
        return rows, errors

    def post(self, request, *args, **kwargs):
        form = TradeProposeForm(request.POST, user=request.user)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        picker_offered, err_pa = self._resolve_selection(form.cleaned_data.get("offered"))
        picker_requested, err_pb = self._resolve_selection(form.cleaned_data.get("requested"))

        text_offered, err_ta = services.build_items_from_text(form.cleaned_data.get("offered_text") or "")
        text_requested, err_tb = services.build_items_from_text(form.cleaned_data.get("requested_text") or "")

        offered_rows = picker_offered + text_offered
        requested_rows = picker_requested + text_requested
        errors = err_pa + err_pb + err_ta + err_tb

        if errors or (not offered_rows and not requested_rows):
            if not errors:
                errors.append("Add at least one card to either side.")
            return self.render_to_response(self.get_context_data(form=form, parse_errors=errors))

        try:
            tx = services.propose_trade(
                initiator=request.user,
                recipient=form.cleaned_data["recipient"],
                offered_rows=offered_rows,
                requested_rows=requested_rows,
                note=form.cleaned_data.get("note", ""),
            )
        except InsufficientInventoryError as exc:
            return self.render_to_response(self.get_context_data(form=form, parse_errors=exc.errors))
        messages.success(request, "Trade proposed.")
        return redirect(tx.get_absolute_url())


class TradeCounterView(LoginRequiredMixin, TemplateView):
    template_name = "omenpath/trade_counter.html"

    def _get_tx(self, pk, user):
        tx = get_object_or_404(
            Transaction.objects.select_related("party_a", "party_b")
            .prefetch_related("items__card_print__card", "items__card_print__cardset"),
            pk=pk,
        )
        if user != tx.party_b:
            raise PermissionDenied
        if tx.status != TransactionStatus.PROPOSED:
            raise PermissionDenied
        return tx

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tx = self._get_tx(kwargs["pk"], self.request.user)
        ctx.update({
            "tx":          tx,
            "items_a":     tx.items_from_a(),
            "items_b":     tx.items_from_b(),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        tx = self._get_tx(kwargs["pk"], request.user)
        keep_ids = request.POST.getlist("keep_b")
        try:
            services.counter_propose(tx=tx, actor=request.user, keep_from_b_ids=keep_ids)
        except InsufficientInventoryError as exc:
            for err in exc.errors:
                messages.error(request, err)
            return redirect("omenpath:trade-counter", pk=tx.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("omenpath:trade-counter", pk=tx.pk)
        messages.success(request, "Counter-proposal sent.")
        return redirect(tx.get_absolute_url())


@login_required
@require_POST
def sale_propose(request, listing_pk):
    listing = get_object_or_404(Listing, pk=listing_pk, status=ListingStatus.OPEN)
    if listing.owner == request.user:
        return HttpResponseBadRequest("Cannot transact with your own listing.")
    if listing.visibility == ListingVisibility.FRIENDS and listing.owner_id not in _friend_ids(request.user):
        raise PermissionDenied
    form = SaleProposeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid input.")
        return redirect(listing.get_absolute_url())
    try:
        tx = services.propose_sale_from_listing(
            buyer=request.user,
            listing=listing,
            quantity=form.cleaned_data["quantity"],
            price_agreed=form.cleaned_data.get("price_agreed"),
            note=form.cleaned_data.get("note", ""),
        )
    except InsufficientInventoryError as exc:
        for err in exc.errors:
            messages.error(request, err)
        return redirect(listing.get_absolute_url())
    messages.success(request, "Offer sent.")
    return redirect(tx.get_absolute_url())


@login_required
@require_POST
def transaction_action(request, pk, action):
    tx = get_object_or_404(Transaction, pk=pk)
    if not tx.is_party(request.user):
        raise PermissionDenied
    is_a = (request.user == tx.party_a)

    # Who responds depends on the status: B responds to PROPOSED, A responds to COUNTER_PROPOSED.
    expected_responder = {
        TransactionStatus.PROPOSED:         tx.party_b,
        TransactionStatus.COUNTER_PROPOSED: tx.party_a,
    }.get(tx.status)

    if action == "accept":
        if request.user != expected_responder:
            return HttpResponseBadRequest("Cannot accept.")
        tx.status = TransactionStatus.ACCEPTED
        tx.save(update_fields=["status", "updated_at"])
        notifications.notify_accepted(tx)
        messages.success(request, "Accepted.")

    elif action == "reject":
        if request.user != expected_responder:
            return HttpResponseBadRequest("Cannot reject.")
        tx.status = TransactionStatus.REJECTED
        tx.save(update_fields=["status", "updated_at"])
        notifications.notify_rejected(tx)
        messages.info(request, "Rejected.")

    elif action == "cancel":
        # The non-responder (i.e. whoever currently holds the proposal) may withdraw it.
        can_cancel = (
            (tx.status == TransactionStatus.PROPOSED         and request.user == tx.party_a) or
            (tx.status == TransactionStatus.COUNTER_PROPOSED and request.user == tx.party_b)
        )
        if not can_cancel:
            return HttpResponseBadRequest("Cannot cancel.")
        tx.status = TransactionStatus.CANCELLED
        tx.save(update_fields=["status", "updated_at"])
        notifications.notify_cancelled(tx)
        messages.info(request, "Cancelled.")

    elif action == "confirm":
        if tx.status != TransactionStatus.ACCEPTED:
            return HttpResponseBadRequest("Not accepted yet.")
        if is_a:
            tx.confirmed_by_a = True
        else:
            tx.confirmed_by_b = True
        tx.save(update_fields=["confirmed_by_a", "confirmed_by_b", "updated_at"])
        if tx.confirmed_by_a and tx.confirmed_by_b:
            try:
                services.finalize_transaction(tx)
            except InsufficientInventoryError as exc:
                # Roll confirmations back so parties can cancel or re-propose.
                tx.confirmed_by_a = False
                tx.confirmed_by_b = False
                tx.save(update_fields=["confirmed_by_a", "confirmed_by_b", "updated_at"])
                for err in exc.errors:
                    messages.error(request, err)
                messages.error(
                    request,
                    "Inventory shifted since this trade was accepted. "
                    "Confirmations have been reset — cancel or adjust before retrying.",
                )
                return redirect(tx.get_absolute_url())
            messages.success(request, "Transaction complete — cards moved to your Recolect collection.")
        else:
            notifications.notify_confirmed_one_side(tx, request.user)
            messages.success(request, "Confirmed. Waiting for the other party.")

    elif action == "unconfirm":
        if tx.status != TransactionStatus.ACCEPTED:
            return HttpResponseBadRequest("Not accepted yet.")
        if is_a:
            tx.confirmed_by_a = False
        else:
            tx.confirmed_by_b = False
        tx.save(update_fields=["confirmed_by_a", "confirmed_by_b", "updated_at"])

    else:
        return HttpResponseBadRequest("Unknown action.")

    return redirect(tx.get_absolute_url())
