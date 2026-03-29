# multiverse/views.py
import json
from django.db.models import Max, Prefetch
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
    SKIP_PILL_KEYS = {"page", "sort", "cmc_op", "color_identity", "color_exact"}

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


class SetListView(TemplateView):
    template_name = "multiverse/set_list.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        form = SetSearchForm(self.request.GET or None)
        qs   = CardSet.objects.filter(is_active=True)

        if form.is_valid():
            qs = form.filter_queryset(qs)

        ctx.update({
            "form":      form,
            "page_obj":  paginate_queryset(qs, self.request.GET.get("page"), per_page=40),
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
            .order_by("collector_number")
        )

        ctx.update({
            "cardset":  cardset,
            "page_obj": paginate_queryset(prints, self.request.GET.get("page"), per_page=40),
            "rarities": CardRarity.choices,
        })
        return ctx


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
    
