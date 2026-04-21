# multiverse/views.py
import json
from django.db.models import Max, Prefetch
from django.db.models.functions import Length
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from core.utils import paginate_queryset
from core.constants import (
    MagicColor,
    CardRarity,
    CardLayout,
    MagicFormat,
    CardSetType,
    CardType,
    CardSupertype,
)
from core.models import CreatureType
from .models import Card, CardSet, CardLegality, CardPrint
from .forms import CardSearchForm, SetSearchForm, SORT_CHOICES

# Sort mappings per version mode
CARD_SORT_MAP = {
    "name_asc":  "name",
    "name_desc": "-name",
    "date_desc": "-latest_release",
    "date_asc":  "latest_release",
}
PRINT_SORT_MAP = {
    "name_asc":  "card__name",
    "name_desc": "-card__name",
    "date_desc": "-released_at",
    "date_asc":  "released_at",
}


class CardListView(TemplateView):
    template_name = "multiverse/card_list.html"

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["multiverse/partials/card_grid.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        form = CardSearchForm(self.request.GET or None)
        version = self.request.GET.get("version", "all")
        sort = self.request.GET.get("sort", "date_desc")

        # Base Card queryset with filters
        card_qs = Card.objects.filter(is_active=True)
        card_qs = self._apply_defaults(card_qs)

        if self.request.GET and form.is_valid():
            card_qs = form.filter_queryset(card_qs)

        if version == "latest":
            # One entry per card — annotate for date sort
            card_qs = card_qs.annotate(
                latest_release=Max("prints__released_at")
            )
            order = CARD_SORT_MAP.get(sort, "-latest_release")
            card_qs = card_qs.order_by(order).prefetch_related(
                Prefetch(
                    "prints",
                    queryset=CardPrint.objects
                        .select_related("cardset")
                        .order_by("-released_at"),
                    to_attr="all_prints_prefetched",
                ),
                Prefetch("faces", to_attr="faces_prefetched"),
            )
            page_obj = paginate_queryset(
                card_qs, self.request.GET.get("page"), per_page=50,
            )
        else:
            # All printed versions (default)
            order = PRINT_SORT_MAP.get(sort, "-released_at")
            print_qs = (
                CardPrint.objects
                .filter(card__in=card_qs, digital=False)
                .exclude(cardset__set_type__in=self.EXCLUDED_SET_TYPES)
                .select_related("card", "cardset")
                .prefetch_related("card__faces")
                .order_by(order)
            )
            # Apply print-level filters
            if form.is_valid():
                data = form.cleaned_data
                if data.get("artist"):
                    print_qs = print_qs.filter(artist__icontains=data["artist"])
                if data.get("set_code"):
                    print_qs = print_qs.filter(cardset__name__icontains=data["set_code"])
                if data.get("exclude_ub"):
                    print_qs = print_qs.exclude(cardset__is_universe_beyond=True)
            page_obj = paginate_queryset(
                print_qs, self.request.GET.get("page"), per_page=50,
            )

        # Autocomplete data for filters (JSON-serialized for Alpine)
        card_types_list = [l for _, l in CardType.choices]
        supertypes_list = [l for _, l in CardSupertype.choices]
        subtypes_list = list(
            CreatureType.objects.order_by("name").values_list("name", flat=True)
        )
        sets_list = list(
            CardSet.objects.filter(is_active=True)
            .exclude(set_type__in=self.EXCLUDED_SET_TYPES)
            .order_by("-released_at")
            .values_list("name", flat=True)
        )

        ctx.update({
            "form":       form,
            "page_obj":   page_obj,
            "colors":     MagicColor.choices,
            "selected_colors": self.request.GET.getlist("color"),
            "selected_colors_json": mark_safe(json.dumps(self.request.GET.getlist("color"))),
            "selected_rarities_json": mark_safe(json.dumps(self.request.GET.getlist("rarity"))),
            "active_filters": self._build_active_filters(),
            "all_params": [(k, v) for k in self.request.GET for v in self.request.GET.getlist(k)],
            "rarities":   CardRarity.choices,
            "layouts":    CardLayout.choices,
            "formats":    MagicFormat.choices,
            "version":    version,
            "sort":       sort,
            "sort_choices": SORT_CHOICES,
            "card_types_json":  mark_safe(json.dumps(card_types_list)),
            "supertypes_json":  mark_safe(json.dumps(supertypes_list)),
            "subtypes_json":    mark_safe(json.dumps(subtypes_list)),
            "sets_json":        mark_safe(json.dumps(sets_list)),
        })
        return ctx

    # Set types to exclude by default
    EXCLUDED_SET_TYPES = ["un_set", "funny", "minigame", "token"]
    SKIP_PILL_KEYS = {"page", "sort", "cmc_op", "color_identity", "color_exact", "color_exclude"}

    def _build_active_filters(self):
        """Build list of (label, value, remove_url) for active filter pills."""
        pills = []
        seen_keys = set()
        params = self.request.GET
        for key in params:
            if key in self.SKIP_PILL_KEYS:
                continue
            values = params.getlist(key)
            joined = ", ".join(v for v in values if v)
            if not joined:
                continue
            # Build remove URL excluding all values of this key
            other = "&".join(
                f"{k}={v}" for k in params for v in params.getlist(k)
                if k != key and k != "page" and v
            )
            pills.append({"key": key, "value": joined, "remove_url": f"?{other}"})
        return pills

    def _apply_defaults(self, qs):
        """
        Exclusiones que aplican siempre — independiente de los filtros del usuario.
        """
        # Sin type_line — cartas de arte, tokens sin tipo, etc.
        qs = qs.exclude(type_line="")
        qs = qs.exclude(type_line="Card")

        # Layouts que nunca mostramos por defecto
        qs = qs.exclude(layout__in=["art_series", "scheme", "planar",
                                     "vanguard", "emblem", "conspiracy"])

        # Excluir tipos de set no deseados (un-sets, funny, minigame, token)
        qs = qs.exclude(prints__cardset__set_type__in=self.EXCLUDED_SET_TYPES)

        # Sin cartas digitales por defecto
        qs = qs.filter(
            prints__digital=False
        ).distinct()

        return qs

class CardDetailView(TemplateView):
    template_name = "multiverse/card_detail.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        card = get_object_or_404(
            Card.objects.prefetch_related("faces", "prints__cardset", "rulings"),
            oracle_id=self.kwargs["oracle_id"],
        )

        try:
            legality = card.legality
        except CardLegality.DoesNotExist:
            legality = None

        faces      = list(card.faces.order_by("face_index"))
        face_front = faces[0] if len(faces) > 0 else None
        face_back  = faces[1] if len(faces) > 1 else None

        # Resolve related cards: map scryfall_id → oracle_id
        related_parts = []
        if card.all_parts:
            from uuid import UUID
            scryfall_ids = [p["id"] for p in card.all_parts if p.get("id")]
            scryfall_to_oracle = {
                str(sid): str(oid)
                for sid, oid in CardPrint.objects
                .filter(scryfall_id__in=scryfall_ids)
                .values_list("scryfall_id", "card__oracle_id")
            }
            current_oracle = str(card.oracle_id)
            for part in card.all_parts:
                oracle_id = scryfall_to_oracle.get(part.get("id", ""))
                # Skip the current card
                if oracle_id == current_oracle:
                    continue
                related_parts.append({
                    **part,
                    "oracle_id": oracle_id or "",
                })

        ctx.update({
            "card":        card,
            "faces":       faces,
            "face_front":  face_front,
            "face_back":   face_back,
            "prints":      card.prints.select_related("cardset").order_by("-cardset__released_at"),
            "related_parts": related_parts,
            "legality":    legality,
            "rulings":     card.rulings.order_by("published_at"),
            "formats":     MagicFormat.choices,
        })
        return ctx


def _user_owned_card_ids_by_set(user, set_ids):
    """
    Return {set_id: set_of_card_ids} for cards the user owns
    (from any of their collections) within the given set IDs.
    """
    if not user.is_authenticated or not set_ids:
        return {}
    from tolarian.models import CollectionItem
    items = (
        CollectionItem.objects
        .filter(
            collection__user=user,
            collection__is_active=True,
            is_active=True,
            print__cardset_id__in=set_ids,
        )
        .values_list("print__cardset_id", "card_id")
        .distinct()
    )
    result = {}
    for set_id, card_id in items:
        result.setdefault(set_id, set()).add(card_id)
    return result


class SetListView(TemplateView):
    template_name = "multiverse/set_list.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        form = SetSearchForm(self.request.GET or None)
        qs   = CardSet.objects.filter(is_active=True)

        if form.is_valid():
            qs = form.filter_queryset(qs)

        page_obj = paginate_queryset(qs, self.request.GET.get("page"), per_page=40)

        # Attach per-user completion stats to each set on the page
        user = self.request.user
        if user.is_authenticated:
            set_ids = [s.pk for s in page_obj.object_list]
            owned_map = _user_owned_card_ids_by_set(user, set_ids)
            for s in page_obj.object_list:
                owned = len(owned_map.get(s.pk, set()))
                s.owned_count = owned
                s.completion_pct = (owned / s.card_count * 100) if s.card_count else 0

        ctx.update({
            "form":      form,
            "page_obj":  page_obj,
            "set_types": CardSetType.choices,
        })
        return ctx


class SetDetailView(TemplateView):
    template_name = "multiverse/set_detail.html"

    def get_template_names(self):
        if self.request.headers.get("HX-Request") and self.request.GET.get("page"):
            return ["multiverse/partials/prints_grid.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        cardset = get_object_or_404(CardSet, code=self.kwargs["code"].lower())
        prints  = (
            cardset.prints
            .select_related("card")
            .prefetch_related("card__faces")
            .order_by(Length("collector_number"), "collector_number")
        )

        page_obj = paginate_queryset(prints, self.request.GET.get("page"), per_page=40)

        # Per-user ownership data
        user = self.request.user
        owned_card_ids = set()
        total_owned = 0
        user_collections = []
        if user.is_authenticated:
            from tolarian.models import CollectionItem, Collection
            # All owned card IDs in this set (for the whole set — used for header)
            total_owned = (
                CollectionItem.objects
                .filter(
                    collection__user=user,
                    collection__is_active=True,
                    is_active=True,
                    print__cardset=cardset,
                )
                .values("card_id").distinct().count()
            )
            # Just the IDs on this page — for grey-out styling
            owned_card_ids = set(
                CollectionItem.objects
                .filter(
                    collection__user=user,
                    collection__is_active=True,
                    is_active=True,
                    card_id__in=[p.card_id for p in page_obj.object_list],
                )
                .values_list("card_id", flat=True)
                .distinct()
            )
            # User's collections for the quick-add dropdown
            user_collections = list(
                Collection.objects.filter(user=user, is_active=True)
                .order_by("collection_type", "name")
            )

        ctx.update({
            "cardset":  cardset,
            "page_obj": page_obj,
            "rarities": CardRarity.choices,
            "owned_card_ids": owned_card_ids,
            "total_owned_in_set": total_owned,
            "completion_pct": round(total_owned / cardset.card_count * 100, 1) if cardset.card_count else 0,
            "user_collections": user_collections,
        })
        return ctx


class QuickAddToCollectionView(TemplateView):
    """
    Quick-add endpoint used from the Set Detail page.
    POST: collection_id, card_id, print_id
    """

    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from django.http import HttpResponse
        from django.template.loader import render_to_string
        from django.contrib import messages
        from tolarian.models import Collection, CollectionItem

        if not request.user.is_authenticated:
            return redirect("account_login")

        collection_id = request.POST.get("collection_id")
        card_id = request.POST.get("card_id")
        print_id = request.POST.get("print_id")

        collection = get_object_or_404(
            Collection, pk=collection_id, user=request.user, is_active=True,
        )
        card = get_object_or_404(Card, pk=card_id)
        print_obj = (
            CardPrint.objects.filter(pk=print_id)
            .select_related("card", "cardset")
            .prefetch_related("card__faces")
            .first()
        )

        # Create or increment
        existing = CollectionItem.objects.filter(
            collection=collection,
            card=card,
            print=print_obj,
            condition="NM",
            finish="nonfoil",
            language="en",
        ).first()
        if existing:
            existing.quantity += 1
            existing.save(update_fields=["quantity", "updated_at"])
            success_msg = f"{card.name} → {collection.name} (x{existing.quantity})"
        else:
            CollectionItem.objects.create(
                collection=collection,
                card=card,
                print=print_obj,
                quantity=1,
                condition="NM",
                finish="nonfoil",
                language="en",
            )
            success_msg = f"Added {card.name} to {collection.name}"

        # Only enqueue a session message for non-HTMX paths — HTMX swaps the
        # card partial inline, so session toasts would pile up unseen until
        # the next full page load.
        is_htmx = request.headers.get("HX-Request")
        if not is_htmx:
            messages.success(request, success_msg)

        if is_htmx and print_obj:
            cardset = print_obj.cardset
            owned_card_ids = set(
                CollectionItem.objects.filter(
                    collection__user=request.user,
                    collection__is_active=True,
                    is_active=True,
                    print__cardset=cardset,
                ).values_list("card_id", flat=True).distinct()
            )
            user_collections = list(
                Collection.objects.filter(user=request.user, is_active=True)
                .order_by("collection_type", "name")
            )
            total_owned = len(owned_card_ids)
            completion_pct = (
                round(total_owned / cardset.card_count * 100, 1)
                if cardset.card_count else 0
            )
            ctx = {
                "print": print_obj,
                "owned_card_ids": owned_card_ids,
                "user_collections": user_collections,
                "request": request,
                "cardset": cardset,
                "total_owned_in_set": total_owned,
                "completion_pct": completion_pct,
                "hx_oob": True,
            }
            card_html = render_to_string(
                "multiverse/partials/_print_card.html", ctx, request=request,
            )
            progress_html = render_to_string(
                "multiverse/partials/_set_progress.html", ctx, request=request,
            )
            return HttpResponse(card_html + progress_html)

        # Redirect back (non-HTMX fallback)
        back = request.META.get("HTTP_REFERER") or "/"
        return redirect(back)


class CardRulingsPartialView(TemplateView):
    template_name = "multiverse/partials/rulings.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        card = get_object_or_404(Card, oracle_id=self.kwargs["oracle_id"])
        ctx["rulings"] = card.rulings.order_by("published_at")
        ctx["card"]    = card
        return ctx


class CardPrintsPartialView(TemplateView):
    template_name = "multiverse/partials/prints.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        card = get_object_or_404(Card, oracle_id=self.kwargs["oracle_id"])
        ctx["prints"] = card.prints.select_related("cardset").order_by("-cardset__released_at")
        ctx["card"]   = card
        return ctx


class CardLegalityPartialView(TemplateView):
    template_name = "multiverse/partials/legality.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        card = get_object_or_404(Card, oracle_id=self.kwargs["oracle_id"])
        try:
            legality = card.legality
        except CardLegality.DoesNotExist:
            legality = None
        ctx["legality"] = legality
        ctx["card"]     = card
        return ctx
    
