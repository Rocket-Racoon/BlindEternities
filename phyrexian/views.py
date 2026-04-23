# phyrexian/views.py
import json
from collections import Counter
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q, F, Avg
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView,
)

from core.mixins import OwnerRequiredMixin
from tolarian.models import Collection, CollectionItem, Deck, DeckCard, DeckZone
from multiverse.models import Card, CardPrint
from .models import (
    GameRecord, GameResult, GamePlayer, GameSession, PlayerSlot, LifeChange,
    SessionStatus, EliminationCause, FORMAT_STARTING_LIFE,
    Tournament, TournamentParticipant, TournamentRound,
    TournamentMatch, TournamentMatchPlayer, TournamentStatus, BracketType,
    TournamentStats,
    EloRating, EloHistory,
)
from .forms import GameRecordForm, SessionSetupForm, TournamentForm, PLAYER_COLORS

# Color config shared by all chart views
COLOR_LABELS = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green", "C": "Colorless"}
COLOR_HEX = {"W": "#F9E076", "U": "#0E68AB", "B": "#150B00", "R": "#D3202A", "G": "#00733E", "C": "#CBC2BF"}
RARITY_HEX = {
    "common": "#6B7280", "uncommon": "#9CA3AF", "rare": "#EAB308",
    "mythic": "#F97316", "special": "#8B5CF6", "bonus": "#A855F7",
}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # ── Filters ──
        filter_format = self.request.GET.get("format", "")
        filter_deck = self.request.GET.get("deck", "")
        filter_period = self.request.GET.get("period", "all")  # all, 30d, 90d, 1y
        ctx["filter_format"] = filter_format
        ctx["filter_deck"] = filter_deck
        ctx["filter_period"] = filter_period
        from core.constants import MagicFormat
        ctx["format_choices"] = MagicFormat.choices
        ctx["user_decks"] = Deck.objects.filter(user=user, is_active=True).order_by("name")

        # Summary counts
        ctx["total_decks"] = Deck.objects.filter(user=user, is_active=True).count()
        ctx["total_collections"] = Collection.objects.filter(user=user, is_active=True).count()
        ctx["total_games"] = GameRecord.objects.filter(user=user, is_active=True).count()

        # Collection value
        collections = Collection.objects.filter(user=user, is_active=True)
        ctx["total_collection_value"] = sum(c.total_value for c in collections)

        # Win rate summary (filtered)
        games = GameRecord.objects.filter(user=user, is_active=True)
        if filter_format:
            games = games.filter(format=filter_format)
        if filter_deck:
            games = games.filter(deck_id=filter_deck)
        if filter_period != "all":
            from datetime import timedelta
            days_map = {"30d": 30, "90d": 90, "1y": 365}
            days = days_map.get(filter_period)
            if days:
                cutoff = timezone.now().date() - timedelta(days=days)
                games = games.filter(date_played__gte=cutoff)

        total = games.count()
        if total:
            wins = games.filter(result=GameResult.WIN).count()
            losses = games.filter(result=GameResult.LOSS).count()
            draws = games.filter(result=GameResult.DRAW).count()
            ctx["win_rate"] = round(wins / total * 100, 1)
            ctx["wins"] = wins
            ctx["losses"] = losses
            ctx["draws"] = draws
            # Chart data for donut
            ctx["winrate_chart_json"] = json.dumps({
                "labels": ["Wins", "Losses", "Draws"],
                "data": [wins, losses, draws],
                "colors": ["#22C55E", "#EF4444", "#EAB308"],
            })
        else:
            ctx["win_rate"] = 0
            ctx["wins"] = ctx["losses"] = ctx["draws"] = 0
            ctx["winrate_chart_json"] = "null"

        # Recent games
        ctx["recent_games"] = games[:5]

        # Format distribution (decks)
        format_dist = list(
            Deck.objects.filter(user=user, is_active=True)
            .values("format")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        ctx["format_distribution"] = format_dist
        ctx["format_chart_json"] = json.dumps({
            "labels": [f["format"].title() for f in format_dist],
            "data": [f["count"] for f in format_dist],
        })

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
        # Rarity chart
        rarity_labels = list(ctx["rarity_distribution"].keys())
        ctx["rarity_chart_json"] = json.dumps({
            "labels": [r.capitalize() for r in rarity_labels],
            "data": [ctx["rarity_distribution"][r] for r in rarity_labels],
            "colors": [RARITY_HEX.get(r, "#6B7280") for r in rarity_labels],
        })

        # Color identity spread
        color_counts = Counter()
        for item in items:
            for color in (item.card.color_identity or []):
                color_counts[color] += item.quantity
        ctx["color_distribution"] = dict(color_counts.most_common())
        # Color chart
        color_keys = list(ctx["color_distribution"].keys())
        ctx["color_chart_json"] = json.dumps({
            "labels": [COLOR_LABELS.get(c, c) for c in color_keys],
            "data": [ctx["color_distribution"][c] for c in color_keys],
            "colors": [COLOR_HEX.get(c, "#6B7280") for c in color_keys],
        })

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

        # ── Playset completion ──
        # Aggregate quantity per card across all collections.
        # Skip basic lands (unlimited in decks).
        card_totals = {}  # {card_id: {'card': Card, 'print': CardPrint, 'qty': int}}
        for item in items:
            if not item.card:
                continue
            type_line = (item.card.type_line or "").lower()
            if "basic" in type_line and "land" in type_line:
                continue
            cid = item.card_id
            if cid not in card_totals:
                card_totals[cid] = {
                    "card": item.card,
                    "print": item.print,
                    "qty": 0,
                    "rarity": item.print.rarity if item.print else "",
                    "price": float(item.print.price_usd or 0) if item.print else 0,
                }
            card_totals[cid]["qty"] += item.quantity

        unique_cards = len(card_totals)
        full_playsets = sum(1 for v in card_totals.values() if v["qty"] >= 4)

        # Playsets by rarity
        playsets_by_rarity = Counter()
        unique_by_rarity = Counter()
        for v in card_totals.values():
            r = v["rarity"] or "common"
            unique_by_rarity[r] += 1
            if v["qty"] >= 4:
                playsets_by_rarity[r] += 1

        # Near-complete playsets (qty 1-3), sorted by (qty desc, price desc)
        near_playsets = [
            {
                "card": v["card"],
                "print": v["print"],
                "qty": v["qty"],
                "missing": 4 - v["qty"],
                "rarity": v["rarity"],
                "price": v["price"],
                "cost_to_complete": v["price"] * (4 - v["qty"]),
            }
            for v in card_totals.values()
            if 1 <= v["qty"] <= 3
        ]
        near_playsets.sort(key=lambda x: (-x["qty"], -x["price"]))

        ctx["playset_unique_cards"] = unique_cards
        ctx["playset_full_count"] = full_playsets
        ctx["playset_completion_pct"] = (
            round(full_playsets / unique_cards * 100, 1) if unique_cards else 0
        )
        ctx["playset_by_rarity"] = [
            {
                "rarity": r,
                "full": playsets_by_rarity.get(r, 0),
                "unique": unique_by_rarity[r],
                "pct": round(playsets_by_rarity.get(r, 0) / unique_by_rarity[r] * 100, 1) if unique_by_rarity[r] else 0,
            }
            for r in ["common", "uncommon", "rare", "mythic"]
            if unique_by_rarity[r] > 0
        ]
        ctx["near_playsets"] = near_playsets[:20]
        ctx["near_playsets_total_cost"] = sum(
            p["cost_to_complete"] for p in near_playsets
        )

        # Playset chart data
        ctx["playset_chart_json"] = json.dumps({
            "labels": [r["rarity"].title() for r in ctx["playset_by_rarity"]],
            "full": [r["full"] for r in ctx["playset_by_rarity"]],
            "remaining": [r["unique"] - r["full"] for r in ctx["playset_by_rarity"]],
            "colors": [RARITY_HEX.get(r["rarity"], "#6B7280") for r in ctx["playset_by_rarity"]],
        })

        # ── Format coverage ──
        from multiverse.models import CardLegality
        from core.constants import MagicFormat

        # Map each format to a minimum deck size. Draft/Sealed skipped.
        FORMAT_DECK_MIN = {
            MagicFormat.STANDARD:    60,
            MagicFormat.PIONEER:     60,
            MagicFormat.MODERN:      60,
            MagicFormat.LEGACY:      60,
            MagicFormat.VINTAGE:     60,
            MagicFormat.PAUPER:      60,
            MagicFormat.COMMANDER:   100,
            MagicFormat.OATHBREAKER: 60,
            MagicFormat.BRAWL:       60,
        }

        owned_card_ids = list(card_totals.keys())
        legalities = (
            CardLegality.objects
            .filter(card_id__in=owned_card_ids)
            .values_list("card_id", "data")
        )
        legal_by_format = Counter()
        for _cid, data in legalities:
            if not isinstance(data, dict):
                continue
            for fmt_key in FORMAT_DECK_MIN.keys():
                if data.get(fmt_key) == "legal":
                    legal_by_format[fmt_key] += 1

        format_coverage = []
        for fmt_key, minimum in FORMAT_DECK_MIN.items():
            legal_count = legal_by_format.get(fmt_key, 0)
            pct = round(min(100, legal_count / minimum * 100), 1) if minimum else 0
            status = (
                "ready" if legal_count >= minimum * 1.5
                else "buildable" if legal_count >= minimum
                else "close" if legal_count >= minimum * 0.5
                else "low"
            )
            format_coverage.append({
                "format": fmt_key,
                "display": dict(MagicFormat.choices).get(fmt_key, fmt_key),
                "owned_legal": legal_count,
                "minimum": minimum,
                "pct": pct,
                "status": status,
            })
        format_coverage.sort(key=lambda x: -x["owned_legal"])
        ctx["format_coverage"] = format_coverage

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
        format_pop = list(
            decks.values("format")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        ctx["format_popularity"] = format_pop

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
        # Color chart
        color_keys = list(ctx["color_distribution"].keys())
        ctx["color_chart_json"] = json.dumps({
            "labels": [COLOR_LABELS.get(c, c) for c in color_keys],
            "data": [ctx["color_distribution"][c] for c in color_keys],
            "colors": [COLOR_HEX.get(c, "#6B7280") for c in color_keys],
        })

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
        # Type chart
        type_labels = list(ctx["type_distribution"].keys())
        ctx["type_chart_json"] = json.dumps({
            "labels": type_labels,
            "data": [ctx["type_distribution"][t] for t in type_labels],
        })

        # Aggregate mana curve across all decks
        curve = Counter()
        for entry in all_entries:
            if "land" not in entry.card.type_line.lower() and entry.card.cmc is not None:
                cmc = int(entry.card.cmc)
                curve[cmc] += entry.quantity
        curve_sorted = dict(sorted(curve.items()))
        ctx["aggregate_curve"] = curve_sorted
        ctx["curve_chart_json"] = json.dumps({
            "labels": [str(k) for k in curve_sorted.keys()],
            "data": list(curve_sorted.values()),
        })

        return ctx


# ---------------------------------------------------------------------------
# Game Records CRUD (with filtering)
# ---------------------------------------------------------------------------
class GameRecordListView(LoginRequiredMixin, ListView):
    model = GameRecord
    template_name = "phyrexian/game_list.html"
    context_object_name = "games"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            GameRecord.objects.filter(user=self.request.user, is_active=True)
            .select_related("deck")
            .prefetch_related("opponents")
        )
        # Filters
        result = self.request.GET.get("result")
        if result in dict(GameResult.choices):
            qs = qs.filter(result=result)

        fmt = self.request.GET.get("format")
        if fmt:
            qs = qs.filter(format=fmt)

        deck_id = self.request.GET.get("deck")
        if deck_id:
            qs = qs.filter(deck_id=deck_id)

        date_from = self.request.GET.get("from")
        if date_from:
            qs = qs.filter(date_played__gte=date_from)

        date_to = self.request.GET.get("to")
        if date_to:
            qs = qs.filter(date_played__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_result"] = self.request.GET.get("result", "")
        ctx["filter_format"] = self.request.GET.get("format", "")
        ctx["filter_deck"] = self.request.GET.get("deck", "")
        ctx["filter_from"] = self.request.GET.get("from", "")
        ctx["filter_to"] = self.request.GET.get("to", "")
        ctx["user_decks"] = Deck.objects.filter(
            user=self.request.user, is_active=True
        ).order_by("name")
        ctx["result_choices"] = GameResult.choices
        from core.constants import MagicFormat
        ctx["format_choices"] = MagicFormat.choices

        # ── Mini trend chart for filtered games ──
        filtered = self.get_queryset()
        total = filtered.count()
        wins = filtered.filter(result=GameResult.WIN).count()
        losses = filtered.filter(result=GameResult.LOSS).count()
        draws = filtered.filter(result=GameResult.DRAW).count()
        ctx["summary_total"] = total
        ctx["summary_wins"] = wins
        ctx["summary_losses"] = losses
        ctx["summary_draws"] = draws
        ctx["summary_win_rate"] = round(wins / total * 100, 1) if total else 0

        # Monthly trend
        from django.db.models.functions import TruncMonth
        trend_qs = (
            filtered.annotate(period=TruncMonth("date_played"))
            .values("period")
            .annotate(
                total=Count("id"),
                wins=Count("id", filter=Q(result=GameResult.WIN)),
            )
            .order_by("period")
        )
        trend_labels = []
        trend_win_rate = []
        trend_game_count = []
        for e in trend_qs:
            trend_labels.append(e["period"].strftime("%Y-%m"))
            wr = (e["wins"] / e["total"] * 100) if e["total"] else 0
            trend_win_rate.append(round(wr, 1))
            trend_game_count.append(e["total"])
        ctx["trend_chart_json"] = json.dumps({
            "labels": trend_labels,
            "win_rate": trend_win_rate,
            "games": trend_game_count,
        })
        ctx["trend_has_data"] = len(trend_labels) > 1
        return ctx


class GameRecordCreateView(LoginRequiredMixin, CreateView):
    model = GameRecord
    form_class = GameRecordForm
    template_name = "phyrexian/game_form.html"
    success_url = reverse_lazy("phyrexian:game-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["elimination_choices"] = EliminationCause.choices
        ctx["existing_opponents_json"] = "[]"
        return ctx

    def form_valid(self, form):
        form.instance.user = self.request.user
        # my_commanders from Alpine-managed hidden input
        raw = self.request.POST.get("my_commanders", "[]")
        try:
            form.instance.my_commanders = json.loads(raw)
        except (ValueError, TypeError):
            form.instance.my_commanders = []
        response = super().form_valid(form)
        self._save_opponents(form, self.object)
        return response

    def _save_opponents(self, form, game):
        opponents_raw = form.cleaned_data.get("opponents_json", "")
        if not opponents_raw:
            return
        try:
            opponents = json.loads(opponents_raw)
        except (ValueError, TypeError):
            return
        for opp in opponents:
            if not opp.get("name", "").strip():
                continue
            deck_id = opp.get("deck_id") or None
            commanders = opp.get("commanders", [])
            if isinstance(commanders, str):
                commanders = [c.strip() for c in commanders.split(",") if c.strip()]
            GamePlayer.objects.create(
                game=game,
                name=opp["name"].strip(),
                deck_id=deck_id if deck_id else None,
                deck_name=opp.get("deck_name", "").strip(),
                commanders=commanders,
                placement=int(opp.get("placement", 0) or 0),
                elimination_cause=opp.get("elimination_cause", ""),
                is_winner=int(opp.get("placement", 0) or 0) == 1,
            )


class GameRecordUpdateView(OwnerRequiredMixin, UpdateView):
    model = GameRecord
    form_class = GameRecordForm
    template_name = "phyrexian/game_form.html"
    success_url = reverse_lazy("phyrexian:game-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["elimination_choices"] = EliminationCause.choices
        existing = list(self.object.opponents.all())
        ctx["existing_opponents_json"] = json.dumps([
            {
                "name": o.name,
                "deck_id": str(o.deck_id) if o.deck_id else "",
                "deck_name": o.deck_name,
                "commanders": o.commanders or [],
                "placement": o.placement,
                "elimination_cause": o.elimination_cause,
            }
            for o in existing
        ])
        return ctx

    def form_valid(self, form):
        # my_commanders from Alpine-managed hidden input
        raw = self.request.POST.get("my_commanders", "[]")
        try:
            form.instance.my_commanders = json.loads(raw)
        except (ValueError, TypeError):
            form.instance.my_commanders = []
        response = super().form_valid(form)
        self.object.opponents.all().delete()
        GameRecordCreateView._save_opponents(None, form, self.object)
        return response


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

        # ── Filters (apply to all stats below) ──
        filter_deck = self.request.GET.get("deck", "")
        filter_commander = self.request.GET.get("commander", "").strip()
        filter_color = self.request.GET.get("color", "")
        filter_format = self.request.GET.get("format", "")
        filter_granularity = self.request.GET.get("granularity", "month")

        if filter_deck:
            games = games.filter(deck_id=filter_deck)
        if filter_format:
            games = games.filter(format=filter_format)
        if filter_commander:
            games = games.filter(my_commanders__icontains=filter_commander)
        if filter_color:
            games = games.filter(deck__cards__card__color_identity__contains=[filter_color]).distinct()

        ctx["filter_deck"] = filter_deck
        ctx["filter_commander"] = filter_commander
        ctx["filter_color"] = filter_color
        ctx["filter_format"] = filter_format
        ctx["filter_granularity"] = filter_granularity
        ctx["user_decks"] = Deck.objects.filter(user=user, is_active=True).order_by("name")
        from core.constants import MagicFormat
        ctx["format_choices"] = MagicFormat.choices
        ctx["color_choices"] = [("W", "White"), ("U", "Blue"), ("B", "Black"), ("R", "Red"), ("G", "Green"), ("C", "Colorless")]

        total = games.count()

        if not total:
            ctx["has_data"] = False
            return ctx

        ctx["has_data"] = True
        ctx["total_games"] = total
        wins = games.filter(result=GameResult.WIN).count()
        losses = games.filter(result=GameResult.LOSS).count()
        draws = games.filter(result=GameResult.DRAW).count()
        ctx["wins"] = wins
        ctx["losses"] = losses
        ctx["draws"] = draws
        ctx["win_rate"] = round(wins / total * 100, 1)

        # Donut chart
        ctx["winrate_chart_json"] = json.dumps({
            "labels": ["Wins", "Losses", "Draws"],
            "data": [wins, losses, draws],
            "colors": ["#22C55E", "#EF4444", "#EAB308"],
        })

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
        format_stats = list(
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
        opponent_stats = list(
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

        # ── Elimination cause breakdown (losses only) ──
        elim_counts = Counter()
        for g in games.filter(result=GameResult.LOSS).exclude(elimination_cause=""):
            elim_counts[g.elimination_cause] += 1
        elim_labels_map = {
            "life": "Life (0 or less)",
            "poison": "Poison",
            "commander_damage": "Cmdr Damage",
            "alt_wincon": "Alt Wincon",
            "forfeit": "Forfeit",
            "alt_losecon": "Alt Losecon",
        }
        elim_colors = {
            "life": "#EF4444", "poison": "#22C55E", "commander_damage": "#A855F7",
            "alt_wincon": "#EAB308", "forfeit": "#6B7280", "alt_losecon": "#EC4899",
        }
        elim_ordered = elim_counts.most_common()
        ctx["elim_chart_json"] = json.dumps({
            "labels": [elim_labels_map.get(k, k) for k, _ in elim_ordered],
            "data": [v for _, v in elim_ordered],
            "colors": [elim_colors.get(k, "#6B7280") for k, _ in elim_ordered],
        })
        ctx["elim_has_data"] = len(elim_ordered) > 0

        # ── Placement distribution (multiplayer games) ──
        placement_counts = Counter()
        for g in games.exclude(my_placement=0):
            placement_counts[g.my_placement] += 1
        placement_sorted = sorted(placement_counts.items())
        placement_colors_map = {
            1: "#EAB308", 2: "#A3A3A3", 3: "#B45309", 4: "#6B7280",
            5: "#6B7280", 6: "#6B7280",
        }
        ctx["placement_chart_json"] = json.dumps({
            "labels": [f"#{p}" for p, _ in placement_sorted],
            "data": [c for _, c in placement_sorted],
            "colors": [placement_colors_map.get(p, "#6B7280") for p, _ in placement_sorted],
        })
        ctx["placement_has_data"] = len(placement_sorted) > 0

        # ── Turn duration stats ──
        wins_turns = [g.turns for g in games.filter(result=GameResult.WIN) if g.turns]
        losses_turns = [g.turns for g in games.filter(result=GameResult.LOSS) if g.turns]
        all_turns = [g.turns for g in games if g.turns]
        ctx["avg_turns_overall"] = round(sum(all_turns) / len(all_turns), 1) if all_turns else 0
        ctx["avg_turns_wins"] = round(sum(wins_turns) / len(wins_turns), 1) if wins_turns else 0
        ctx["avg_turns_losses"] = round(sum(losses_turns) / len(losses_turns), 1) if losses_turns else 0
        ctx["min_turns"] = min(all_turns) if all_turns else 0
        ctx["max_turns"] = max(all_turns) if all_turns else 0

        # ── Commander performance ──
        cmdr_stats = {}
        for g in games:
            for cmdr in (g.my_commanders or []):
                if cmdr not in cmdr_stats:
                    cmdr_stats[cmdr] = {"total": 0, "wins": 0, "losses": 0, "draws": 0}
                cmdr_stats[cmdr]["total"] += 1
                if g.result == GameResult.WIN:
                    cmdr_stats[cmdr]["wins"] += 1
                elif g.result == GameResult.LOSS:
                    cmdr_stats[cmdr]["losses"] += 1
                else:
                    cmdr_stats[cmdr]["draws"] += 1
        cmdr_list = []
        for name, s in cmdr_stats.items():
            s["name"] = name
            s["win_rate"] = round(s["wins"] / s["total"] * 100, 1) if s["total"] else 0
            cmdr_list.append(s)
        cmdr_list.sort(key=lambda x: (-x["total"], -x["win_rate"]))
        ctx["commander_stats"] = cmdr_list[:15]

        # ── Kill graph (who eliminated you most) ──
        eliminator_counts = Counter()
        for g in games.filter(result=GameResult.LOSS).exclude(eliminator_name=""):
            eliminator_counts[g.eliminator_name] += 1
        ctx["eliminator_stats"] = eliminator_counts.most_common(10)

        # ── Win rate trend (monthly/yearly) ──
        from django.db.models.functions import TruncMonth, TruncYear
        trunc_fn = TruncYear if filter_granularity == "year" else TruncMonth
        trend_qs = (
            games.annotate(period=trunc_fn("date_played"))
            .values("period")
            .annotate(
                total=Count("id"),
                wins=Count("id", filter=Q(result=GameResult.WIN)),
                losses=Count("id", filter=Q(result=GameResult.LOSS)),
                draws=Count("id", filter=Q(result=GameResult.DRAW)),
            )
            .order_by("period")
        )
        trend_periods = []
        trend_win_rate = []
        trend_wins = []
        trend_losses = []
        trend_draws = []
        for entry in trend_qs:
            period_str = (
                entry["period"].strftime("%Y") if filter_granularity == "year"
                else entry["period"].strftime("%Y-%m")
            )
            trend_periods.append(period_str)
            wr = (entry["wins"] / entry["total"] * 100) if entry["total"] else 0
            trend_win_rate.append(round(wr, 1))
            trend_wins.append(entry["wins"])
            trend_losses.append(entry["losses"])
            trend_draws.append(entry["draws"])
        ctx["trend_chart_json"] = json.dumps({
            "labels": trend_periods,
            "win_rate": trend_win_rate,
            "wins": trend_wins,
            "losses": trend_losses,
            "draws": trend_draws,
        })
        ctx["trend_has_data"] = len(trend_periods) > 0

        return ctx


# ---------------------------------------------------------------------------
# Price Analytics
# ---------------------------------------------------------------------------
class PriceAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/price_analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        items = CollectionItem.objects.filter(
            collection__user=user,
            collection__is_active=True,
            is_active=True,
        ).select_related("card", "print", "print__cardset")

        # Total value
        total = 0
        nonfoil_value = 0
        foil_value = 0
        valued_items = []
        set_values = Counter()

        for item in items:
            if not item.print or not item.print.price_usd:
                continue
            price = float(item.print.price_usd)
            item_total = price * item.quantity
            total += item_total
            valued_items.append({
                "card": item.card,
                "print": item.print,
                "quantity": item.quantity,
                "unit_price": price,
                "total_price": item_total,
                "finish": item.get_finish_display(),
            })
            if item.finish == "nonfoil":
                nonfoil_value += item_total
            else:
                foil_value += item_total
            if item.print.cardset:
                set_values[item.print.cardset.code.upper()] += item_total

        ctx["total_value"] = round(total, 2)
        ctx["nonfoil_value"] = round(nonfoil_value, 2)
        ctx["foil_value"] = round(foil_value, 2)
        ctx["foil_premium_pct"] = round(foil_value / total * 100, 1) if total else 0

        # Top valuable
        valued_items.sort(key=lambda x: x["total_price"], reverse=True)
        ctx["top_valuable"] = valued_items[:20]

        # Value by set (top 15)
        top_sets = set_values.most_common(15)
        ctx["set_values"] = top_sets
        ctx["set_chart_json"] = json.dumps({
            "labels": [s[0] for s in top_sets],
            "data": [round(s[1], 2) for s in top_sets],
        })

        # Foil vs nonfoil chart
        ctx["foil_chart_json"] = json.dumps({
            "labels": ["Non-Foil", "Foil / Special"],
            "data": [round(nonfoil_value, 2), round(foil_value, 2)],
            "colors": ["#6B7280", "#EAB308"],
        })

        return ctx


# ---------------------------------------------------------------------------
# HTMX Partials
# ---------------------------------------------------------------------------
class DashboardStatsPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: returns just the summary stats cards."""
    template_name = "phyrexian/partials/dashboard_stats.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["total_decks"] = Deck.objects.filter(user=user, is_active=True).count()
        ctx["total_collections"] = Collection.objects.filter(user=user, is_active=True).count()
        ctx["total_games"] = GameRecord.objects.filter(user=user, is_active=True).count()
        collections = Collection.objects.filter(user=user, is_active=True)
        ctx["total_collection_value"] = sum(c.total_value for c in collections)
        return ctx


# ---------------------------------------------------------------------------
# Live Game Session
# ---------------------------------------------------------------------------
class SessionSetupView(LoginRequiredMixin, TemplateView):
    """Step 1: Configure format, player count, and starting life."""
    template_name = "phyrexian/session_setup.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = SessionSetupForm()
        ctx["player_colors"] = PLAYER_COLORS
        ctx["format_life_map"] = json.dumps(FORMAT_STARTING_LIFE)
        user = self.request.user
        profile = user.profile if hasattr(user, "profile") else None
        ctx["current_user_json"] = json.dumps({
            "id": user.pk,
            "name": profile.name if profile else user.username,
            "avatar": profile.avatar.url if profile and profile.avatar else "",
        })
        ctx["current_user_decks_json"] = json.dumps([
            {"id": str(d.pk), "name": d.name, "format": d.get_format_display()}
            for d in Deck.objects.filter(user=user, is_active=True).order_by("name")
        ])
        return ctx

    def post(self, request, *args, **kwargs):
        form = SessionSetupForm(request.POST)
        if not form.is_valid():
            return self.render_to_response({"form": form, "player_colors": PLAYER_COLORS, "format_life_map": json.dumps(FORMAT_STARTING_LIFE)})

        fmt = form.cleaned_data["format"]
        player_count = form.cleaned_data["player_count"]
        starting_life = form.cleaned_data["starting_life"]

        # Create session
        session = GameSession.objects.create(
            host=request.user,
            format=fmt,
            starting_life=starting_life,
        )

        # Create player slots from POST data
        from django.contrib.auth.models import User as AuthUser

        for i in range(player_count):
            name = request.POST.get(f"player_{i}_name", f"Player {i + 1}").strip()
            color = request.POST.get(f"player_{i}_color", PLAYER_COLORS[i % len(PLAYER_COLORS)])
            bg_image = request.POST.get(f"player_{i}_bg", "")
            deck_id = request.POST.get(f"player_{i}_deck", "")
            user_id = request.POST.get(f"player_{i}_user", "")
            if not name:
                name = f"Player {i + 1}"
            slot = PlayerSlot(
                session=session,
                name=name,
                position=i,
                life=starting_life,
                color=color,
                background_image=bg_image,
            )
            if user_id:
                try:
                    slot.user = AuthUser.objects.get(pk=int(user_id))
                except (AuthUser.DoesNotExist, ValueError):
                    pass
            if deck_id:
                slot.deck_id = deck_id
            # Custom commanders (used when no deck is linked)
            if not deck_id:
                c1 = request.POST.get(f"player_{i}_commander_1", "").strip()
                c2 = request.POST.get(f"player_{i}_commander_2", "").strip()
                slot.commanders = [c for c in (c1, c2) if c]
            slot.save()

        from django.shortcuts import redirect
        return redirect("phyrexian:session-live", pk=session.pk)


class SessionLiveView(LoginRequiredMixin, TemplateView):
    """The full-screen live game tracker."""
    template_name = "phyrexian/session_live.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        players = list(session.players.all())

        ctx["session"] = session
        ctx["players"] = players
        # Pre-fetch commander names for each player's deck
        player_commanders = {}
        for p in players:
            if p.deck_id:
                cmdr_cards = p.deck.commander_cards.select_related("card")
                player_commanders[p.pk] = [dc.card.name for dc in cmdr_cards]
            elif p.commanders:
                player_commanders[p.pk] = list(p.commanders)
            else:
                player_commanders[p.pk] = []

        # Map commander name → art_crop URL (first available print) and type_line.
        # type_line is used to filter non-combat commanders (Planeswalker /
        # Enchantment/Background) out of the commander-damage lists.
        all_cmdr_names = {n for names in player_commanders.values() for n in names}
        commander_art = {}
        commander_types = {}
        if all_cmdr_names:
            cards = Card.objects.filter(name__in=all_cmdr_names).prefetch_related("prints")
            for c in cards:
                commander_types[c.name] = c.type_line or ""
                for pr in c.prints.all():
                    art = (pr.image_uris or {}).get("art_crop")
                    if art:
                        commander_art[c.name] = art
                        break

        ctx["players_json"] = json.dumps([
            {
                "pk": str(p.pk),
                "name": p.name,
                "life": p.life,
                "poison": p.poison,
                "energy": p.energy,
                "experience": p.experience,
                "commander_tax": p.commander_tax,
                "treasure": p.treasure,
                "rad": p.rad,
                "storm_count": p.storm_count,
                "is_monarch": p.is_monarch,
                "has_initiative": p.has_initiative,
                "has_citys_blessing": p.has_citys_blessing,
                "is_day": p.is_day,
                "speed": p.speed,
                "the_ring": p.the_ring,
                "commander_damage": p.commander_damage,
                "color": p.color,
                "background_image": p.background_image,
                "is_dead": p.is_dead,
                "placement": p.placement,
                "elimination_turn": p.elimination_turn,
                "eliminator_pk": str(p.eliminator_id) if p.eliminator_id else "",
                "elimination_cause": p.elimination_cause,
                "commanders": player_commanders.get(p.pk, []),
                "commander_art": {n: commander_art.get(n, "") for n in player_commanders.get(p.pk, [])},
                "commander_types": {n: commander_types.get(n, "") for n in player_commanders.get(p.pk, [])},
                "commander_taxes": p.commander_taxes or {},
            }
            for p in players
        ])
        ctx["recent_changes"] = session.life_changes.order_by("-created_at")[:20]
        return ctx


class SessionLifeChangeView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: apply a life change and return updated player panel."""
    template_name = "phyrexian/partials/player_panel.html"

    def post(self, request, *args, **kwargs):
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        session = player.session

        if session.status != SessionStatus.ACTIVE:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest("Session is not active.")

        delta = int(request.POST.get("delta", 0))
        if delta == 0:
            from django.http import HttpResponseBadRequest
            return HttpResponseBadRequest("Delta cannot be zero.")

        player.life += delta
        player.save(update_fields=["life", "updated_at"])

        return self.render_to_response({"player": player, "session": session})


class SessionCounterChangeView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: change a counter (poison, energy, experience) on a player."""
    template_name = "phyrexian/partials/player_panel.html"

    COUNTER_LABELS = {
        "poison": "Poison", "energy": "Energy", "experience": "Experience",
        "commander_tax": "Commander Tax", "treasure": "Treasure",
        "rad": "Rad", "storm_count": "Storm", "speed": "Speed", "the_ring": "The Ring",
    }

    def post(self, request, *args, **kwargs):
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])

        counter = request.POST.get("counter", "")
        delta = int(request.POST.get("delta", 0))

        valid_counters = ["poison", "energy", "experience", "commander_tax", "treasure", "rad", "storm_count", "speed", "the_ring"]
        if counter in valid_counters and delta != 0:
            current = getattr(player, counter)
            new_val = max(0, current + delta)
            if counter in ("speed", "the_ring"):
                new_val = min(4, new_val)
            setattr(player, counter, new_val)
            player.save(update_fields=[counter, "updated_at"])

        return self.render_to_response({"player": player, "session": player.session})


class SessionCommanderTaxView(LoginRequiredMixin, View):
    """Update per-commander tax for a player."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        commander = request.POST.get("commander", "")
        if commander:
            taxes = player.commander_taxes or {}
            taxes[commander] = taxes.get(commander, 0) + 1
            player.commander_taxes = taxes
            player.save(update_fields=["commander_taxes", "updated_at"])
        return JsonResponse({"ok": True, "taxes": player.commander_taxes})


class SessionToggleStatusView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: toggle monarch, initiative, city's blessing, day/night."""
    template_name = "phyrexian/partials/player_panel.html"

    def post(self, request, *args, **kwargs):
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        flag = request.POST.get("flag", "")

        session = player.session
        if flag == "monarch":
            session.players.update(is_monarch=False)
            player.is_monarch = True
            player.save(update_fields=["is_monarch", "updated_at"])
            LifeChange.objects.create(session=session, player=player, delta=0, life_after=player.life, turn=session.current_turn, source="Monarch")
        elif flag == "initiative":
            session.players.update(has_initiative=False)
            player.has_initiative = True
            player.save(update_fields=["has_initiative", "updated_at"])
            LifeChange.objects.create(session=session, player=player, delta=0, life_after=player.life, turn=session.current_turn, source="Initiative")
        elif flag == "citys_blessing":
            player.has_citys_blessing = not player.has_citys_blessing
            player.save(update_fields=["has_citys_blessing", "updated_at"])
            if player.has_citys_blessing:
                LifeChange.objects.create(session=session, player=player, delta=0, life_after=player.life, turn=session.current_turn, source="Ascend")
        elif flag == "day_night":
            new_state = not player.is_day
            session.players.update(is_day=new_state)
            LifeChange.objects.create(session=session, player=player, delta=0, life_after=player.life, turn=session.current_turn, source="Day" if new_state else "Night")

        from django.shortcuts import render
        players = list(player.session.players.all())
        return render(request, "phyrexian/partials/all_players.html", {
            "players": players, "session": player.session,
        })


class SessionCommanderDamageView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: apply commander damage from one player to another."""
    template_name = "phyrexian/partials/player_panel.html"

    def post(self, request, *args, **kwargs):
        target = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        source_pk = request.POST.get("source_pk", "")
        delta = int(request.POST.get("delta", 0))
        also_lose_life = request.POST.get("lose_life", "true") == "true"

        dmg = target.commander_damage or {}
        current = dmg.get(source_pk, 0)
        new_val = max(0, current + delta)
        applied = new_val - current
        dmg[source_pk] = new_val
        target.commander_damage = dmg

        if also_lose_life and applied != 0:
            target.life -= applied

        target.save(update_fields=["commander_damage", "life", "updated_at"])

        from django.http import JsonResponse
        return JsonResponse({
            "life": target.life,
            "commander_damage": target.commander_damage,
            "is_dead": target.is_dead,
        })


class SessionNextTurnView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: advance the turn counter."""
    template_name = "phyrexian/partials/turn_counter.html"

    def post(self, request, *args, **kwargs):
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        session.current_turn += 1
        session.save(update_fields=["current_turn", "updated_at"])
        return self.render_to_response({"session": session})


class SessionLogTurnView(LoginRequiredMixin, View):
    """Batch-log life changes and commander damage at end of turn."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse
        import json as _json

        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        try:
            data = _json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({"ok": False})

        turn = data.get("turn", session.current_turn)
        entries = data.get("entries", [])
        # entries: [{pk, delta, life_after, source}, ...]
        for entry in entries:
            player = session.players.filter(pk=entry.get("pk")).first()
            if not player:
                continue
            LifeChange.objects.create(
                session=session,
                player=player,
                delta=entry.get("delta", 0),
                life_after=entry.get("life_after", player.life),
                turn=turn,
                source=entry.get("source", ""),
            )
        return JsonResponse({"ok": True})


def _get_slot_commanders(slot):
    """Get commander names from a PlayerSlot (deck-linked or custom)."""
    if slot.deck_id:
        cmdr_cards = slot.deck.commander_cards.select_related("card")
        return [dc.card.name for dc in cmdr_cards]
    return list(slot.commanders or [])


def _apply_elo_for_session(session):
    """Apply ELO rating changes for all players in a finished session."""
    from .elo import PlayerResult, apply_elo_changes, DEFAULT_RATING
    slots = list(session.players.filter(user__isnull=False))
    if len(slots) < 2:
        return
    results = []
    for s in slots:
        rating_obj = EloRating.objects.filter(
            user=s.user, format=session.format,
        ).first()
        r = rating_obj.rating if rating_obj else DEFAULT_RATING
        m = rating_obj.matches_played if rating_obj else 0
        results.append(PlayerResult(
            user_id=s.user_id,
            rating=r,
            matches_played=m,
            placement=s.placement or 99,
        ))
    apply_elo_changes(session.format, results)


def _create_game_record_from_session(session, slot, winner_pk):
    """Create a GameRecord with GamePlayer opponents for a session participant."""
    if winner_pk and str(slot.pk) == str(winner_pk):
        result = GameResult.WIN
    elif winner_pk:
        result = GameResult.LOSS
    else:
        result = GameResult.DRAW

    all_players = list(session.players.all())
    opponents = [p for p in all_players if p.pk != slot.pk]
    opponent_names = ", ".join(p.name for p in opponents)

    slot_eliminator_name = ""
    if slot.eliminator_id:
        slot_eliminator_name = (
            slot.name if slot.eliminator_id == slot.pk else slot.eliminator.name
        )

    record = GameRecord.objects.create(
        user=slot.user,
        deck=slot.deck,
        format=session.format,
        result=result,
        opponent_name=opponent_names,
        my_commanders=_get_slot_commanders(slot),
        my_placement=slot.placement or 0,
        elimination_cause=slot.elimination_cause,
        elimination_turn=slot.elimination_turn,
        eliminator_name=slot_eliminator_name,
        turns=session.current_turn,
        date_played=timezone.now().date(),
        session=session,
        notes=f"Live session — {session.player_count} players"
              + (f" — #{slot.placement} place" if slot.placement else ""),
    )

    # Create GamePlayer records for each opponent
    for opp in opponents:
        opp_eliminator_name = ""
        if opp.eliminator_id:
            opp_eliminator_name = (
                opp.name if opp.eliminator_id == opp.pk else opp.eliminator.name
            )
        GamePlayer.objects.create(
            game=record,
            name=opp.name,
            deck=opp.deck,
            deck_name=opp.deck.name if opp.deck else "",
            commanders=_get_slot_commanders(opp),
            placement=opp.placement or 0,
            elimination_cause=opp.elimination_cause,
            elimination_turn=opp.elimination_turn,
            eliminator_name=opp_eliminator_name,
            is_winner=bool(winner_pk and str(opp.pk) == str(winner_pk)),
        )

    return record


class SessionEndView(LoginRequiredMixin, TemplateView):
    """End the session and optionally create GameRecords."""
    template_name = "phyrexian/session_end.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        ctx["session"] = session
        ctx["players"] = list(session.players.all())
        return ctx

    def post(self, request, *args, **kwargs):
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        winner_pk = request.POST.get("winner")

        if winner_pk:
            winner = get_object_or_404(PlayerSlot, pk=winner_pk, session=session)
            session.winner = winner
        session.status = SessionStatus.FINISHED
        session.save(update_fields=["status", "winner", "updated_at"])

        # Auto-create a GameRecord for the host if they played
        host_slot = session.players.filter(user=request.user).first()
        if host_slot:
            _create_game_record_from_session(session, host_slot, winner_pk)

        _apply_elo_for_session(session)

        from django.shortcuts import redirect
        return redirect("phyrexian:session-summary", pk=session.pk)


class SessionSummaryView(LoginRequiredMixin, TemplateView):
    """Post-game summary with life change history."""
    template_name = "phyrexian/session_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        ctx["session"] = session
        ctx["players"] = list(session.players.all())
        ctx["life_changes"] = session.life_changes.select_related("player").order_by("created_at")
        ctx["total_changes"] = session.life_changes.count()
        return ctx


class SessionResetView(LoginRequiredMixin, TemplateView):
    """Reset life totals for a new game within the same session."""
    template_name = "phyrexian/partials/all_players.html"

    def post(self, request, *args, **kwargs):
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        session.life_changes.all().delete()
        session.players.update(placement=0)
        session.reset_life()
        players = list(session.players.all())
        return self.render_to_response({"players": players, "session": session})


class SessionAutoFinishView(LoginRequiredMixin, View):
    """Auto-finish game: assign placements and save winner."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse

        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        if session.status == SessionStatus.FINISHED:
            return JsonResponse({"ok": False, "error": "already finished"})

        # Parse placements from JSON body or form data
        import json as _json
        try:
            data = _json.loads(request.body)
        except (ValueError, TypeError):
            data = {}

        placements = data.get("placements", {})  # {player_pk: placement_number}
        winner_pk = data.get("winner")

        for slot in session.players.all():
            pk_str = str(slot.pk)
            if pk_str in placements:
                slot.placement = placements[pk_str]
                slot.save(update_fields=["placement", "updated_at"])

        if winner_pk:
            winner = get_object_or_404(PlayerSlot, pk=winner_pk, session=session)
            session.winner = winner
        session.status = SessionStatus.FINISHED
        session.save(update_fields=["status", "winner", "updated_at"])

        # Auto-create GameRecords for all linked users
        for slot in session.players.filter(user__isnull=False):
            _create_game_record_from_session(session, slot, winner_pk)

        _apply_elo_for_session(session)

        return JsonResponse({"ok": True})


class SessionLogPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: return recent life change log entries."""
    template_name = "phyrexian/partials/life_log.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        ctx["recent_changes"] = session.life_changes.select_related("player").order_by("-created_at")[:50]
        return ctx


# ---------------------------------------------------------------------------
# API — Deck search (for opponent deck linking)
# ---------------------------------------------------------------------------
class DeckSearchJSON(LoginRequiredMixin, View):
    """Return up to 10 decks matching a name query."""

    def get(self, request):
        from django.http import JsonResponse
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse([], safe=False)
        decks = (
            Deck.objects.filter(is_active=True, name__icontains=q)
            .filter(Q(is_public=True) | Q(user=request.user))
            .select_related("user")
            .prefetch_related("cards__card")
            .order_by("name")[:10]
        )
        results = []
        for d in decks:
            cmdr_cards = d.cards.filter(zone="commander").select_related("card")
            commanders = [dc.card.name for dc in cmdr_cards]
            results.append({
                "id": str(d.pk),
                "name": d.name,
                "format": d.get_format_display(),
                "user": d.user.username,
                "commanders": commanders,
            })
        return JsonResponse(results, safe=False)


class UserSearchJSON(LoginRequiredMixin, View):
    """Return up to 10 users matching a query (for tournament player adding)."""

    def get(self, request):
        from django.http import JsonResponse
        from django.contrib.auth.models import User as AuthUser
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse([], safe=False)
        users = (
            AuthUser.objects
            .filter(
                Q(username__icontains=q) | Q(profile__display_name__icontains=q),
                is_active=True,
            )
            .select_related("profile")[:10]
        )
        results = []
        for u in users:
            profile = getattr(u, "profile", None)
            results.append({
                "id": u.pk,
                "username": u.username,
                "display_name": profile.name if profile else u.username,
                "avatar": profile.avatar.url if profile and profile.avatar else "",
            })
        return JsonResponse(results, safe=False)


class UserDecksJSON(LoginRequiredMixin, View):
    """Return decks for a specific user (with commanders).

    Own decks always; friend's decks in full; otherwise public only.
    """

    def get(self, request, user_pk):
        from django.http import JsonResponse
        from django.contrib.auth.models import User as AuthUser
        decks = (
            Deck.objects.filter(user_id=user_pk, is_active=True)
            .order_by("name")
        )
        if int(user_pk) != request.user.pk:
            target = get_object_or_404(AuthUser, pk=user_pk)
            state, _ = request.user.profile.friendship_with(target)
            if state != "friends":
                decks = decks.filter(is_public=True)
        results = []
        for d in decks:
            cmdr_cards = d.commander_cards.select_related("card")
            results.append({
                "id": str(d.pk),
                "name": d.name,
                "format": d.get_format_display(),
                "commanders": [dc.card.name for dc in cmdr_cards],
            })
        return JsonResponse(results, safe=False)


class PlayerEliminateView(LoginRequiredMixin, View):
    """HTMX endpoint: directly eliminate a player in a session."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        cause = request.POST.get("cause", "forfeit")
        turn = request.POST.get("turn")
        eliminator_pk = request.POST.get("eliminator_pk")

        fields = []
        if cause in dict(EliminationCause.choices):
            player.elimination_cause = cause
            fields.append("elimination_cause")
        if turn:
            try:
                player.elimination_turn = int(turn)
                fields.append("elimination_turn")
            except (TypeError, ValueError):
                pass
        if eliminator_pk:
            try:
                player.eliminator = PlayerSlot.objects.get(
                    pk=eliminator_pk, session=player.session,
                )
                fields.append("eliminator")
            except (PlayerSlot.DoesNotExist, ValueError):
                pass
        if fields:
            fields.append("updated_at")
            player.save(update_fields=fields)
        return JsonResponse({"ok": True, "cause": player.elimination_cause})


# ═══════════════════════════════════════════════════════════════════════════
# Tournaments
# ═══════════════════════════════════════════════════════════════════════════

class TournamentListView(LoginRequiredMixin, ListView):
    model = Tournament
    template_name = "phyrexian/tournament_list.html"
    context_object_name = "tournaments"
    paginate_by = 20

    def get_queryset(self):
        return Tournament.objects.filter(
            host=self.request.user, is_active=True,
        ).prefetch_related("participants")


class TournamentCreateView(LoginRequiredMixin, CreateView):
    model = Tournament
    form_class = TournamentForm
    template_name = "phyrexian/tournament_form.html"

    def form_valid(self, form):
        form.instance.host = self.request.user
        return super().form_valid(form)


class TournamentDetailView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/tournament_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        t = get_object_or_404(Tournament, pk=kwargs["pk"])
        ctx["tournament"] = t
        ctx["participants"] = list(
            t.participants.order_by("-match_points", "-opp_match_win_pct", "seed")
        )
        ctx["rounds"] = list(
            t.rounds.prefetch_related("matches__players__participant").order_by("round_number")
        )
        ctx["can_generate_round"] = (
            t.status != TournamentStatus.FINISHED
            and (t.current_round == 0 or t.rounds.filter(
                round_number=t.current_round, is_complete=True
            ).exists())
        )
        CMDR_FORMATS = {"commander", "oathbreaker", "brawl", "other"}
        ctx["needs_commander"] = t.format in CMDR_FORMATS
        ctx["is_1v1"] = t.pod_size == 2
        ctx["is_bo3"] = t.best_of == 3
        return ctx


class TournamentAddParticipantView(LoginRequiredMixin, View):
    """HTMX / POST: add a participant to a tournament."""

    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        t = get_object_or_404(Tournament, pk=kwargs["pk"], host=request.user)
        name = request.POST.get("name", "").strip()
        if not name:
            return redirect("phyrexian:tournament-detail", pk=t.pk)

        deck_id = request.POST.get("deck_id") or None
        commanders_raw = request.POST.get("commanders", "")
        commanders = [c.strip() for c in commanders_raw.split(",") if c.strip()]
        seed = t.participants.count() + 1

        TournamentParticipant.objects.create(
            tournament=t, name=name, seed=seed,
            deck_id=deck_id if deck_id else None,
            deck_name=request.POST.get("deck_name", "").strip(),
            commanders=commanders,
            user_id=request.POST.get("user_id") or None,
        )
        return redirect("phyrexian:tournament-detail", pk=t.pk)


class TournamentDropParticipantView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        t = get_object_or_404(Tournament, pk=kwargs["pk"], host=request.user)
        p = get_object_or_404(TournamentParticipant, pk=kwargs["participant_pk"], tournament=t)
        if t.status == TournamentStatus.SETUP:
            p.delete()
        else:
            p.dropped = True
            p.save(update_fields=["dropped", "updated_at"])
        return redirect("phyrexian:tournament-detail", pk=t.pk)


class TournamentGenerateRoundView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from .tournament import generate_next_round
        t = get_object_or_404(Tournament, pk=kwargs["pk"], host=request.user)
        generate_next_round(t)
        return redirect("phyrexian:tournament-detail", pk=t.pk)


class TournamentRecordResultView(LoginRequiredMixin, View):
    """Record the result of a single-game match (best_of=1)."""

    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from .tournament import record_match_result
        match = get_object_or_404(
            TournamentMatch, pk=kwargs["match_pk"],
            round__tournament__host=request.user,
        )
        placements = {}
        for key, val in request.POST.items():
            if key.startswith("placement_"):
                try:
                    participant_pk = key.split("_", 1)[1]
                    placement = int(val)
                    if placement > 0:
                        placements[participant_pk] = placement
                except (ValueError, IndexError):
                    pass
        if placements:
            record_match_result(match, placements)
        return redirect(
            "phyrexian:tournament-detail",
            pk=match.round.tournament.pk,
        )


class TournamentRecordGameView(LoginRequiredMixin, View):
    """Record one game within a best-of-N match."""

    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from .tournament import record_match_result
        match = get_object_or_404(
            TournamentMatch, pk=kwargs["match_pk"],
            round__tournament__host=request.user,
        )
        if match.is_complete:
            return redirect("phyrexian:tournament-detail", pk=match.round.tournament.pk)

        best_of = match.round.tournament.best_of
        wins_needed = (best_of // 2) + 1

        # Parse game placements (same format as single-game)
        placements = {}
        for key, val in request.POST.items():
            if key.startswith("placement_"):
                try:
                    ppk = key.split("_", 1)[1]
                    p = int(val)
                    if p > 0:
                        placements[ppk] = p
                except (ValueError, IndexError):
                    pass

        if not placements:
            return redirect("phyrexian:tournament-detail", pk=match.round.tournament.pk)

        # Detect tie (all same placement)
        is_tie = len(set(placements.values())) == 1 and len(placements) == match.players.count()

        # Award game wins
        for mp in match.players.all():
            pk_str = str(mp.participant_id)
            place = placements.get(pk_str, 0)
            if is_tie:
                pass  # ties don't award game wins
            elif place == 1:
                mp.game_wins += 1
                mp.save(update_fields=["game_wins", "updated_at"])

        match.current_game += 1
        match.save(update_fields=["current_game", "updated_at"])

        # Check if anyone reached the win threshold
        leader = match.players.order_by("-game_wins").first()
        all_games_played = (match.current_game - 1) >= best_of

        if leader and leader.game_wins >= wins_needed:
            # Match decided — build final placements by game_wins desc
            final = {}
            players_sorted = list(match.players.order_by("-game_wins"))
            for i, mp in enumerate(players_sorted, start=1):
                final[str(mp.participant_id)] = i
            record_match_result(match, final)
        elif all_games_played:
            # All games played — resolve by game_wins
            final = {}
            players_sorted = list(match.players.order_by("-game_wins"))
            # Handle ties in game_wins
            prev_gw = None
            prev_place = 0
            for i, mp in enumerate(players_sorted, start=1):
                if mp.game_wins == prev_gw:
                    final[str(mp.participant_id)] = prev_place
                else:
                    final[str(mp.participant_id)] = i
                    prev_place = i
                prev_gw = mp.game_wins
            record_match_result(match, final)

        return redirect("phyrexian:tournament-detail", pk=match.round.tournament.pk)


# ═══════════════════════════════════════════════════════════════════════════
# ELO Leaderboard & Profile
# ═══════════════════════════════════════════════════════════════════════════

class EloLeaderboardView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/elo_leaderboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from core.constants import MagicFormat
        fmt = self.request.GET.get("format", MagicFormat.COMMANDER)
        ctx["selected_format"] = fmt
        ctx["format_choices"] = MagicFormat.choices
        ctx["ratings"] = (
            EloRating.objects
            .filter(format=fmt, matches_played__gt=0)
            .select_related("user")
            .order_by("-rating")[:50]
        )
        # Current user rating
        ctx["my_rating"] = EloRating.objects.filter(
            user=self.request.user, format=fmt,
        ).first()
        return ctx


class EloProfileView(LoginRequiredMixin, TemplateView):
    template_name = "phyrexian/elo_profile.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.contrib.auth.models import User as AuthUser
        user = get_object_or_404(AuthUser, pk=kwargs.get("user_pk", self.request.user.pk))
        ctx["profile_user"] = user
        ctx["ratings"] = list(
            EloRating.objects.filter(user=user, matches_played__gt=0).order_by("-rating")
        )
        ctx["history"] = list(
            EloHistory.objects.filter(user=user)
            .select_related("game")
            .order_by("-created_at")[:50]
        )
        # Chart data: rating over time per format
        chart_data = {}
        for entry in EloHistory.objects.filter(user=user).order_by("created_at"):
            fmt = entry.format
            if fmt not in chart_data:
                chart_data[fmt] = []
            chart_data[fmt].append({
                "date": entry.created_at.isoformat(),
                "rating": entry.new_rating,
            })
        # Tournament stats
        ctx["tournament_stats"] = list(
            TournamentStats.objects
            .filter(user=user, tournaments_played__gt=0)
            .order_by("-tournaments_won", "-match_wins")
        )
        ctx["recent_tournaments"] = list(
            TournamentParticipant.objects
            .filter(user=user, tournament__status=TournamentStatus.FINISHED)
            .select_related("tournament")
            .order_by("-tournament__date")[:10]
        )

        # ── Tournament match-by-match trend ──
        match_history = []
        tmps = (
            TournamentMatchPlayer.objects
            .filter(
                participant__user=user,
                match__is_complete=True,
                match__is_bye=False,
            )
            .select_related("match__round__tournament", "participant")
            .order_by("match__round__tournament__date", "match__round__round_number", "match__table_number")
        )
        cumulative_wins = 0
        cumulative_losses = 0
        cumulative_draws = 0
        for mp in tmps:
            if mp.result == GameResult.WIN:
                cumulative_wins += 1
            elif mp.result == GameResult.LOSS:
                cumulative_losses += 1
            elif mp.result == GameResult.DRAW:
                cumulative_draws += 1
            total_m = cumulative_wins + cumulative_losses + cumulative_draws
            wr = (cumulative_wins / total_m * 100) if total_m else 0
            match_history.append({
                "tournament": mp.match.round.tournament.name,
                "round": mp.match.round.round_number,
                "date": mp.match.round.tournament.date.isoformat(),
                "result": mp.result,
                "win_rate": round(wr, 1),
            })
        ctx["tournament_trend_json"] = json.dumps({
            "labels": [f"{h['tournament']} R{h['round']}" for h in match_history],
            "win_rate": [h["win_rate"] for h in match_history],
            "results": [h["result"] for h in match_history],
        })
        ctx["tournament_trend_has_data"] = len(match_history) > 1
        ctx["chart_data_json"] = json.dumps(chart_data)
        return ctx
