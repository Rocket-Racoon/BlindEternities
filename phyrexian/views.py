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
    GameRecord, GameResult, GameSession, PlayerSlot, LifeChange,
    SessionStatus, FORMAT_STARTING_LIFE,
)
from .forms import GameRecordForm, SessionSetupForm, PLAYER_COLORS

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
            else:
                player_commanders[p.pk] = []

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
                "commanders": player_commanders.get(p.pk, []),
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

        LifeChange.objects.create(
            session=session,
            player=player,
            delta=delta,
            life_after=player.life,
            turn=session.current_turn,
        )

        return self.render_to_response({"player": player, "session": session})


class SessionCounterChangeView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: change a counter (poison, energy, experience) on a player."""
    template_name = "phyrexian/partials/player_panel.html"

    def post(self, request, *args, **kwargs):
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])

        counter = request.POST.get("counter", "")
        delta = int(request.POST.get("delta", 0))

        valid_counters = ["poison", "energy", "experience", "commander_tax", "treasure", "rad", "storm_count", "speed", "the_ring"]
        if counter in valid_counters:
            current = getattr(player, counter)
            new_val = max(0, current + delta)
            if counter in ("speed", "the_ring"):
                new_val = min(4, new_val)
            setattr(player, counter, new_val)
            player.save(update_fields=[counter, "updated_at"])

        return self.render_to_response({"player": player, "session": player.session})


class SessionToggleStatusView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint: toggle monarch, initiative, city's blessing, day/night."""
    template_name = "phyrexian/partials/player_panel.html"

    def post(self, request, *args, **kwargs):
        player = get_object_or_404(PlayerSlot, pk=kwargs["player_pk"])
        flag = request.POST.get("flag", "")

        if flag == "monarch":
            player.session.players.update(is_monarch=False)
            player.is_monarch = True
            player.save(update_fields=["is_monarch", "updated_at"])
        elif flag == "initiative":
            player.session.players.update(has_initiative=False)
            player.has_initiative = True
            player.save(update_fields=["has_initiative", "updated_at"])
        elif flag == "citys_blessing":
            player.has_citys_blessing = not player.has_citys_blessing
            player.save(update_fields=["has_citys_blessing", "updated_at"])
        elif flag == "day_night":
            # Day/Night is global — toggle for all players
            new_state = not player.is_day
            player.session.players.update(is_day=new_state)

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
        dmg[source_pk] = max(0, current + delta)
        target.commander_damage = dmg

        if also_lose_life and delta != 0:
            target.life -= delta

        target.save(update_fields=["commander_damage", "life", "updated_at"])

        if delta != 0:
            LifeChange.objects.create(
                session=target.session,
                player=target,
                delta=-delta if also_lose_life else 0,
                life_after=target.life,
                turn=target.session.current_turn,
                source="commander damage",
            )

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
            if winner_pk and str(host_slot.pk) == winner_pk:
                result = GameResult.WIN
            elif winner_pk:
                result = GameResult.LOSS
            else:
                result = GameResult.DRAW

            opponents = session.players.exclude(pk=host_slot.pk)
            opponent_names = ", ".join(p.name for p in opponents)

            GameRecord.objects.create(
                user=request.user,
                deck=host_slot.deck,
                format=session.format,
                result=result,
                opponent_name=opponent_names,
                turns=session.current_turn,
                date_played=timezone.now().date(),
                session=session,
                notes=f"Live session — {session.player_count} players",
            )

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
            if winner_pk and str(slot.pk) == str(winner_pk):
                result = GameResult.WIN
            elif winner_pk:
                result = GameResult.LOSS
            else:
                result = GameResult.DRAW

            opponents = session.players.exclude(pk=slot.pk)
            opponent_names = ", ".join(p.name for p in opponents)

            GameRecord.objects.create(
                user=slot.user,
                deck=slot.deck,
                format=session.format,
                result=result,
                opponent_name=opponent_names,
                turns=session.current_turn,
                date_played=timezone.now().date(),
                session=session,
                notes=f"Live session — {session.player_count} players — #{slot.placement} place",
            )

        return JsonResponse({"ok": True})


class SessionLogPartialView(LoginRequiredMixin, TemplateView):
    """HTMX partial: return recent life change log entries."""
    template_name = "phyrexian/partials/life_log.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        session = get_object_or_404(GameSession, pk=kwargs["pk"])
        ctx["recent_changes"] = session.life_changes.select_related("player").order_by("-created_at")[:20]
        return ctx
