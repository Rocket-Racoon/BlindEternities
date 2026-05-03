from django.contrib import admin

from .models import CardTag, DeckEvaluation


@admin.register(DeckEvaluation)
class DeckEvaluationAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "user", "status", "final_score", "honest_tier", "bracket", "intent_label", "model_name", "created_at")
    list_filter   = ("status", "honest_tier", "bracket", "intent_label", "model_name")
    search_fields = ("commander", "user__username", "deck__name")
    readonly_fields = ("prompt", "raw_response", "card_tags", "combos", "duration_ms", "created_at", "updated_at")


@admin.register(CardTag)
class CardTagAdmin(admin.ModelAdmin):
    list_display    = ("card", "function_tag_count", "theme_tag_count", "model_name", "vocabulary_version", "updated_at")
    list_filter     = ("model_name", "vocabulary_version")
    search_fields   = ("card__name",)
    autocomplete_fields = ("card",) if hasattr(CardTag.card.field.related_model, "_meta") else ()
    readonly_fields = ("created_at", "updated_at")

    def function_tag_count(self, obj):
        return len(obj.function_tags or [])
    function_tag_count.short_description = "func"

    def theme_tag_count(self, obj):
        return len(obj.theme_tags or [])
    theme_tag_count.short_description = "theme"
