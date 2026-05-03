"""
Views for the deck-build "Suggest" modal.

GET  /decks/<pk>/suggest/                       — full modal HTML
GET  /decks/<pk>/suggest/results/               — result list partial (filter swap)
GET  /decks/<pk>/suggest/row/<card_pk>/         — single row partial
GET  /decks/<pk>/suggest/prints/<card_pk>/      — print picker popover
POST /decks/<pk>/suggest/add/<card_pk>/         — +1 to deck, returns row
POST /decks/<pk>/suggest/dec/<card_pk>/         — −1 from deck, returns row
"""
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import View

from core.constants import DeckZone
from multiverse.models import Card, CardPrint

from .mixins import DeckOwnerMixin
from .models import Deck, DeckCard
from .suggest import (
    AUTO_TOP_TAGS,
    SINGLETON_FORMATS,
    TYPE_FILTERS,
    deck_color_identity,
    deck_tag_aggregate,
    default_print_for,
    suggest_cards,
    _max_copies,
)


def _suggest_filters_from_request(request):
    raw_tags  = request.GET.get("tags", "")
    raw_types = request.GET.get("types", "")
    tags  = [t.strip() for t in raw_tags.split(",") if t.strip()]
    types = [t.strip() for t in raw_types.split(",") if t.strip()]
    query = (request.GET.get("q") or "").strip()
    return tags, types, query


def _zones_for_deck(deck):
    zones = [(DeckZone.MAIN, "Main"), (DeckZone.SIDEBOARD, "Sideboard")]
    if deck.format in SINGLETON_FORMATS:
        zones.insert(0, (DeckZone.COMMANDER, "Commander"))
    zones.append((DeckZone.MAYBEBOARD, "Maybeboard"))
    return zones


def _row_context(deck, card, request):
    print_pk = request.GET.get("print") or request.POST.get("print")
    chosen_print = None
    if print_pk:
        chosen_print = (
            card.prints.filter(pk=print_pk)
            .select_related("cardset")
            .first()
        )
    if chosen_print is None:
        chosen_print = default_print_for(card)

    rows = list(
        DeckCard.objects.filter(deck=deck, card=card)
        .select_related("print__cardset")
    )
    total_qty = sum(r.quantity for r in rows)
    tag_obj = getattr(card, "conflux_tags", None)
    return {
        "deck":          deck,
        "card":          card,
        "default_print": chosen_print,
        "in_deck_qty":   total_qty,
        "in_deck_rows":  rows,
        "function_tags": list(tag_obj.function_tags or []) if tag_obj else [],
        "theme_tags":    list(tag_obj.theme_tags or []) if tag_obj else [],
        "matched_tags":  [],
        "zones":         _zones_for_deck(deck),
    }


class DeckSuggestModalView(DeckOwnerMixin, View):
    def get(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        tags, types, query = _suggest_filters_from_request(request)

        deck_tags = deck_tag_aggregate(deck)
        tag_chips = sorted(deck_tags.items(), key=lambda x: (-x[1], x[0]))

        suggestions = suggest_cards(
            deck, tags=tags or None, types=types or None, query=query, limit=40,
        )
        for s in suggestions:
            s.default_print = default_print_for(s.card)

        return render(request, "tolarian/partials/suggest_modal.html", {
            "deck":           deck,
            "tag_chips":      tag_chips,
            "type_filters":   TYPE_FILTERS,
            "selected_tags":  tags,
            "selected_types": types,
            "query":          query,
            "suggestions":    suggestions,
            "color_identity": sorted(deck_color_identity(deck) or []),
            "zones":          _zones_for_deck(deck),
            "auto_mode":      not tags,
            "top_n":          AUTO_TOP_TAGS,
        })


class DeckSuggestResultsView(DeckOwnerMixin, View):
    def get(self, request, pk):
        deck = get_object_or_404(Deck, pk=pk)
        tags, types, query = _suggest_filters_from_request(request)
        suggestions = suggest_cards(
            deck, tags=tags or None, types=types or None, query=query, limit=40,
        )
        for s in suggestions:
            s.default_print = default_print_for(s.card)
        return render(request, "tolarian/partials/suggest_results.html", {
            "deck":        deck,
            "suggestions": suggestions,
            "zones":       _zones_for_deck(deck),
            "auto_mode":   not tags,
        })


class DeckSuggestRowView(DeckOwnerMixin, View):
    def get(self, request, pk, card_pk):
        deck = get_object_or_404(Deck, pk=pk)
        card = get_object_or_404(Card, pk=card_pk)
        return render(request, "tolarian/partials/suggest_row.html",
                      _row_context(deck, card, request))


class DeckSuggestPrintsView(DeckOwnerMixin, View):
    def get(self, request, pk, card_pk):
        deck = get_object_or_404(Deck, pk=pk)
        card = get_object_or_404(Card, pk=card_pk)
        prints = (
            card.prints
            .select_related("cardset")
            .order_by("-cardset__released_at", "collector_number")[:80]
        )
        return render(request, "tolarian/partials/suggest_prints.html", {
            "deck":   deck,
            "card":   card,
            "prints": prints,
        })


class DeckSuggestAddView(DeckOwnerMixin, View):
    def post(self, request, pk, card_pk):
        deck = get_object_or_404(Deck, pk=pk)
        card = get_object_or_404(Card, pk=card_pk)
        zone = request.POST.get("zone") or DeckZone.MAIN
        print_pk = request.POST.get("print")

        current_qty = (
            DeckCard.objects.filter(deck=deck, card=card)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        max_copies = _max_copies(card, deck.format)
        if max_copies is not None and current_qty >= max_copies:
            return HttpResponse(
                f"<div class='px-2 py-1 text-xs text-red-600'>"
                f"Already at max copies ({max_copies}) of {card.name}."
                f"</div>",
                status=409,
            )

        chosen_print = None
        if print_pk:
            chosen_print = CardPrint.objects.filter(pk=print_pk, card=card).first()
        if chosen_print is None:
            chosen_print = default_print_for(card)

        existing = DeckCard.objects.filter(
            deck=deck, card=card, zone=zone, print=chosen_print,
        ).first()
        if existing:
            existing.quantity += 1
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            DeckCard.objects.create(
                deck=deck, card=card, zone=zone, print=chosen_print, quantity=1,
            )

        return render(request, "tolarian/partials/suggest_row.html",
                      _row_context(deck, card, request))


class DeckSuggestDecView(DeckOwnerMixin, View):
    def post(self, request, pk, card_pk):
        deck = get_object_or_404(Deck, pk=pk)
        card = get_object_or_404(Card, pk=card_pk)

        print_pk = request.POST.get("print")
        rows = list(
            DeckCard.objects.filter(deck=deck, card=card)
            .order_by("-updated_at")
        )
        target = None
        if print_pk:
            for r in rows:
                if str(r.print_id) == str(print_pk):
                    target = r
                    break
        if target is None and rows:
            target = rows[0]

        if target:
            target.quantity = max(0, target.quantity - 1)
            if target.quantity <= 0:
                target.delete()
            else:
                target.save(update_fields=["quantity", "updated_at"])

        return render(request, "tolarian/partials/suggest_row.html",
                      _row_context(deck, card, request))
