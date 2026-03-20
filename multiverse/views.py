# multiverse/views.py
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from core.utils import paginate_queryset
from core.constants import (
    MagicColor,
    CardRarity,
    CardLayout,
    MagicFormat,
    CardSetType,
)
from .models import Card, CardSet, CardLegality
from .forms import CardSearchForm, SetSearchForm


class CardListView(TemplateView):
    template_name = "multiverse/card_list.html"

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        form = CardSearchForm(self.request.GET or None)
        qs   = Card.objects.filter(is_active=True).order_by("name")

        if form.is_valid():
            qs = form.filter_queryset(qs)

        ctx.update({
            "form":     form,
            "page_obj": paginate_queryset(qs, self.request.GET.get("page"), per_page=40),
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
            "formats":  MagicFormat.choices,
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

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        cardset = get_object_or_404(CardSet, code=self.kwargs["code"].lower())
        prints  = cardset.prints.select_related("card").order_by("collector_number")

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