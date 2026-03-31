# phyrexian/admin.py
from django.contrib import admin
from .models import GameRecord


@admin.register(GameRecord)
class GameRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "deck", "format", "result", "opponent_name", "date_played", "created_at")
    list_filter = ("result", "format", "date_played")
    search_fields = ("opponent_name", "opponent_deck_name", "notes")
    raw_id_fields = ("user", "deck")
    date_hierarchy = "date_played"
