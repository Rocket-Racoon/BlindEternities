# phyrexian/admin.py
from django.contrib import admin
from .models import (
    GameRecord, GamePlayer, GameSession, PlayerSlot, LifeChange,
    Tournament, TournamentParticipant, TournamentRound,
    TournamentMatch, TournamentMatchPlayer, TournamentStats,
    EloRating, EloHistory,
)


class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    extra = 0
    raw_id_fields = ("deck",)
    readonly_fields = ("commanders",)


@admin.register(GameRecord)
class GameRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "deck", "format", "result", "my_placement", "elimination_cause", "date_played", "created_at")
    list_filter = ("result", "format", "elimination_cause", "date_played")
    search_fields = ("opponent_name", "opponent_deck_name", "notes")
    raw_id_fields = ("user", "deck")
    date_hierarchy = "date_played"
    inlines = [GamePlayerInline]


class PlayerSlotInline(admin.TabularInline):
    model = PlayerSlot
    extra = 0
    readonly_fields = ("life", "poison", "energy", "experience", "commander_damage")


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("host", "format", "status", "starting_life", "current_turn", "created_at")
    list_filter = ("status", "format")
    raw_id_fields = ("host", "winner")
    inlines = [PlayerSlotInline]


@admin.register(LifeChange)
class LifeChangeAdmin(admin.ModelAdmin):
    list_display = ("session", "player", "delta", "life_after", "turn", "created_at")
    list_filter = ("turn",)
    raw_id_fields = ("session", "player")


# ── Tournament ──────────────────────────────────────────────────────────────

class TournamentParticipantInline(admin.TabularInline):
    model = TournamentParticipant
    extra = 0
    raw_id_fields = ("user", "deck")
    readonly_fields = ("match_points", "match_wins", "match_losses", "final_standing")


class TournamentRoundInline(admin.TabularInline):
    model = TournamentRound
    extra = 0
    readonly_fields = ("is_complete",)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ("name", "host", "format", "bracket_type", "status", "current_round", "date")
    list_filter = ("status", "bracket_type", "format")
    search_fields = ("name",)
    raw_id_fields = ("host",)
    date_hierarchy = "date"
    inlines = [TournamentParticipantInline, TournamentRoundInline]


class TournamentMatchPlayerInline(admin.TabularInline):
    model = TournamentMatchPlayer
    extra = 0
    raw_id_fields = ("participant",)


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = ("round", "table_number", "is_complete", "is_bye")
    list_filter = ("is_complete", "is_bye")
    inlines = [TournamentMatchPlayerInline]


# ── ELO ─────────────────────────────────────────────────────────────────────

@admin.register(EloRating)
class EloRatingAdmin(admin.ModelAdmin):
    list_display = ("user", "format", "rating", "matches_played", "wins", "losses", "peak_rating")
    list_filter = ("format",)
    search_fields = ("user__username",)
    raw_id_fields = ("user",)


@admin.register(TournamentStats)
class TournamentStatsAdmin(admin.ModelAdmin):
    list_display = (
        "user", "format", "tournaments_played", "tournaments_won",
        "top_4", "best_placement", "match_wins", "match_losses",
    )
    list_filter = ("format",)
    search_fields = ("user__username",)
    raw_id_fields = ("user",)


@admin.register(EloHistory)
class EloHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "format", "old_rating", "new_rating", "change", "created_at")
    list_filter = ("format",)
    search_fields = ("user__username",)
    raw_id_fields = ("user", "game", "tournament_match")
