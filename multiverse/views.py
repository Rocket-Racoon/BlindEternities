# multiverse/views.py
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from core.utils import paginate_queryset
from core.constants import MagicColor, CardRarity, CardLayout, MagicFormat
from .models import Card, CardSet, CardLegality


class CardListView(TemplateView):
    template_name = "multiverse/card_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = Card.objects.filter(is_active=True)

        # Filtros
        q          = self.request.GET.get("q", "").strip()
        color      = self.request.GET.get("color", "")
        layout     = self.request.GET.get("layout", "")
        format_key = self.request.GET.get("format", "")
        rarity     = self.request.GET.get("rarity", "")
        cmc        = self.request.GET.get("cmc", "")
        commander  = self.request.GET.get("commander", "")

        if q:
            qs = qs.filter(name__icontains=q)
        if color:
            qs = qs.filter(color_identity__contains=color)
        if layout:
            qs = qs.filter(layout=layout)
        if format_key:
            qs = qs.filter(legality__data__contains={format_key: "legal"})
        if rarity:
            qs = qs.filter(prints__rarity=rarity).distinct()
        if cmc:
            try:
                qs = qs.filter(cmc=float(cmc))
            except ValueError:
                pass
        if commander == "1":
            qs = qs.filter(can_be_commander=True)

        ctx.update({
            "page_obj":   paginate_queryset(qs, self.request.GET.get("page"), per_page=40),
            "q":          q,
            "color":      color,
            "layout":     layout,
            "format_key": format_key,
            "rarity":     rarity,
            "cmc":        cmc,
            "commander":  commander,
            "colors":   MagicColor.choices,
            "rarities": CardRarity.choices,
            "layouts":  CardLayout.choices,
            "formats":  MagicFormat.choices,
        })
        return ctx


class CardDetailView(TemplateView):
    template_name = "multiverse/card_detail.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        card = get_object_or_404(Card, oracle_id=self.kwargs["oracle_id"])

        try:
            legality = card.legality
        except CardLegality.DoesNotExist:
            legality = None

        ctx.update({
            "card":     card,
            "faces":    card.faces.order_by("face_index"),
            "prints":   card.prints.select_related("cardset").order_by("-cardset__released_at"),
            "legality": legality,
            "rulings":  card.rulings.order_by("published_at"),
        })
        return ctx


class SetListView(TemplateView):
    template_name = "multiverse/set_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = CardSet.objects.filter(is_active=True)

        q        = self.request.GET.get("q", "").strip()
        set_type = self.request.GET.get("type", "")

        if q:
            qs = qs.filter(name__icontains=q)
        if set_type:
            qs = qs.filter(set_type=set_type)

        ctx.update({
            "page_obj": paginate_queryset(qs, self.request.GET.get("page"), per_page=40),
            "q":        q,
            "set_type": set_type,
        })
        return ctx


class SetDetailView(TemplateView):
    template_name = "multiverse/set_detail.html"

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        cardset = get_object_or_404(CardSet, code=self.kwargs["code"].lower())
        prints  = cardset.prints.select_related("card").order_by("collector_number")

        ctx.update({
            "cardset":  cardset,
            "page_obj": paginate_queryset(prints, self.request.GET.get("page"), per_page=40),
        })
        return ctx


# --- Parciales HTMX ---
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