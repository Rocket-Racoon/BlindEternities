# phyrexian/admin.py
from django.contrib import admin
from .models import GameRecord, GamePlayer, GameSession, PlayerSlot, LifeChange


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
