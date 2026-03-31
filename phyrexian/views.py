# phyrexian/views.py
from collections import Counter
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q, F, Avg
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView,
)

from core.mixins import OwnerRequiredMixin
from tolarian.models import Collection, CollectionItem, Deck, DeckCard, DeckZone
from multiverse.models import Card, CardPrint
from .models import GameRecord, GameResult
from .forms import GameRecordForm


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Summary counts
        ctx["total_decks"] = Deck.objects.filter(user=user, is_active=True).count()
        ctx["total_collections"] = Collection.objects.filter(user=user, is_active=True).count()
        ctx["total_games"] = GameRecord.objects.filter(user=user, is_active=True).count()

        # Collection value
        collections = Collection.objects.filter(user=user, is_active=True)
        ctx["total_collection_value"] = sum(c.total_value for c in collections)

        # Win rate summary
        games = GameRecord.objects.filter(user=user, is_active=True)
        total = games.count()
        if total:
            wins = games.filter(result=GameResult.WIN).count()
            ctx["win_rate"] = round(wins / total * 100, 1)
            ctx["wins"] = wins
            ctx["losses"] = games.filter(result=GameResult.LOSS).count()
            ctx["draws"] = games.filter(result=GameResult.DRAW).count()
        else:
            ctx["win_rate"] = 0
            ctx["wins"] = ctx["losses"] = ctx["draws"] = 0

        # Recent games
        ctx["recent_games"] = games[:5]

        # Format distribution (decks)
        ctx["format_distribution"] = (
            Deck.objects.filter(user=user, is_active=True)
            .values("format")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return ctx


# ---------------------------------------------------------------------------
# Collection Stats
# ---------------------------------------------------------------------------
class CollectionStatsView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/collection_stats.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        items = CollectionItem.objects.filter(
            collection__user=user,
            collection__is_active=True,
            is_active=True,
        ).select_related("card", "print", "print__cardset")

        # Total cards & value
        ctx["total_cards"] = items.aggregate(total=Sum("quantity"))["total"] or 0
        ctx["total_value"] = sum(
            float(item.print.price_usd or 0) * item.quantity
            for item in items if item.print
        )

        # Rarity distribution
        rarity_counts = Counter()
        for item in items:
            if item.print:
                rarity_counts[item.print.rarity] += item.quantity
        ctx["rarity_distribution"] = dict(rarity_counts.most_common())

        # Color identity spread
        color_counts = Counter()
        for item in items:
            for color in (item.card.color_identity or []):
                color_counts[color] += item.quantity
        ctx["color_distribution"] = dict(color_counts.most_common())

        # Condition breakdown
        condition_counts = Counter()
        for item in items:
            condition_counts[item.get_condition_display()] += item.quantity
        ctx["condition_distribution"] = dict(condition_counts.most_common())

        # Top valuable cards
        valued_items = []
        for item in items:
            if item.print and item.print.price_usd:
                valued_items.append({
                    "card": item.card,
                    "print": item.print,
                    "quantity": item.quantity,
                    "unit_price": float(item.print.price_usd),
                    "total_price": float(item.print.price_usd) * item.quantity,
                })
        valued_items.sort(key=lambda x: x["total_price"], reverse=True)
        ctx["top_valuable"] = valued_items[:10]

        # Creature type breakdown
        type_counts = Counter()
        for item in items:
            for ct in item.card.creature_types.all():
                type_counts[ct.name] += item.quantity
        ctx["creature_types"] = dict(type_counts.most_common(15))

        return ctx


# ---------------------------------------------------------------------------
# Deck Stats
# ---------------------------------------------------------------------------
class DeckStatsView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/deck_stats.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        decks = Deck.objects.filter(user=user, is_active=True)
        ctx["decks"] = decks

        # Aggregate across all decks
        all_entries = DeckCard.objects.filter(
            deck__user=user,
            deck__is_active=True,
            is_active=True,
        ).exclude(
            zone__in=[DeckZone.MAYBEBOARD, DeckZone.RESERVE, DeckZone.EXTRAS]
        ).select_related("card")

        # Most-used cards across decks
        card_usage = Counter()
        for entry in all_entries:
            card_usage[entry.card.name] += 1  # count decks, not quantity
        ctx["most_used_cards"] = card_usage.most_common(15)

        # Format popularity
        ctx["format_popularity"] = (
            decks.values("format")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Average deck value
        values = [d.total_value for d in decks]
        ctx["avg_deck_value"] = round(sum(values) / len(values), 2) if values else 0
        ctx["total_deck_value"] = round(sum(values), 2)

        # Color identity across all decks
        color_counts = Counter()
        for entry in all_entries:
            for color in (entry.card.color_identity or []):
                color_counts[color] += entry.quantity
        ctx["color_distribution"] = dict(color_counts.most_common())

        # Average CMC
        cmcs = [float(e.card.cmc) for e in all_entries if e.card.cmc is not None and "land" not in e.card.type_line.lower()]
        ctx["avg_cmc"] = round(sum(cmcs) / len(cmcs), 2) if cmcs else 0

        # Card type distribution
        type_counts = Counter()
        for entry in all_entries:
            tl = entry.card.type_line.lower()
            for t in ["creature", "instant", "sorcery", "artifact", "enchantment", "planeswalker", "land", "battle"]:
                if t in tl:
                    type_counts[t.capitalize()] += entry.quantity
        ctx["type_distribution"] = dict(type_counts.most_common())

        return ctx


# ---------------------------------------------------------------------------
# Game Records CRUD
# ---------------------------------------------------------------------------
class GameRecordListView(LoginRequiredMixin, ListView):
    model = GameRecord
    template_name = "phyrexian/game_list.html"
    context_object_name = "games"
    paginate_by = 20

    def get_queryset(self):
        return (
            GameRecord.objects.filter(user=self.request.user, is_active=True)
            .select_related("deck")
        )


class GameRecordCreateView(LoginRequiredMixin, CreateView):
    model = GameRecord
    form_class = GameRecordForm
    template_name = "phyrexian/game_form.html"
    success_url = reverse_lazy("phyrexian:game-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class GameRecordUpdateView(OwnerRequiredMixin, UpdateView):
    model = GameRecord
    form_class = GameRecordForm
    template_name = "phyrexian/game_form.html"
    success_url = reverse_lazy("phyrexian:game-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class GameRecordDeleteView(OwnerRequiredMixin, DeleteView):
    model = GameRecord
    template_name = "phyrexian/game_confirm_delete.html"
    success_url = reverse_lazy("phyrexian:game-list")


# ---------------------------------------------------------------------------
# Win Rate Dashboard
# ---------------------------------------------------------------------------
class WinRateView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/win_rate.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        games = GameRecord.objects.filter(user=user, is_active=True).select_related("deck")
        total = games.count()

        if not total:
            ctx["has_data"] = False
            return ctx

        ctx["has_data"] = True
        ctx["total_games"] = total
        ctx["wins"] = games.filter(result=GameResult.WIN).count()
        ctx["losses"] = games.filter(result=GameResult.LOSS).count()
        ctx["draws"] = games.filter(result=GameResult.DRAW).count()
        ctx["win_rate"] = round(ctx["wins"] / total * 100, 1)

        # Win rate by deck
        deck_stats = []
        decks_with_games = (
            games.values("deck__id", "deck__name")
            .annotate(
                total=Count("id"),
                wins=Count("id", filter=Q(result=GameResult.WIN)),
                losses=Count("id", filter=Q(result=GameResult.LOSS)),
                draws=Count("id", filter=Q(result=GameResult.DRAW)),
            )
            .order_by("-total")
        )
        for d in decks_with_games:
            d["win_rate"] = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0
            deck_stats.append(d)
        ctx["deck_stats"] = deck_stats

        # Win rate by format
        format_stats = (
            games.values("format")
            .annotate(
                total=Count("id"),
                wins=Count("id", filter=Q(result=GameResult.WIN)),
            )
            .order_by("-total")
        )
        for f in format_stats:
            f["win_rate"] = round(f["wins"] / f["total"] * 100, 1) if f["total"] else 0
        ctx["format_stats"] = format_stats

        # Win rate by opponent
        opponent_stats = (
            games.exclude(opponent_name="")
            .values("opponent_name")
            .annotate(
                total=Count("id"),
                wins=Count("id", filter=Q(result=GameResult.WIN)),
            )
            .order_by("-total")
        )
        for o in opponent_stats:
            o["win_rate"] = round(o["wins"] / o["total"] * 100, 1) if o["total"] else 0
        ctx["opponent_stats"] = opponent_stats[:10]

        # Current streak
        recent = games.order_by("-date_played", "-created_at")[:20]
        streak_type = None
        streak_count = 0
        for g in recent:
            if streak_type is None:
                streak_type = g.result
                streak_count = 1
            elif g.result == streak_type:
                streak_count += 1
            else:
                break
        ctx["streak_type"] = streak_type
        ctx["streak_count"] = streak_count

        return ctx
