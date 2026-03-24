from django.contrib import admin
from .models import Collection, CollectionItem, Deck, DeckCard

class CollectionItemInline(admin.TabularInline):
    model         = CollectionItem
    extra         = 0
    raw_id_fields = ("card", "print")
    fields        = ("card", "print", "quantity", "condition", "finish", "language", "purchase_price")
    readonly_fields = ("id",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display    = ("name", "user", "collection_type", "is_public", "card_count")
    list_filter     = ("collection_type", "is_public")
    search_fields   = ("name", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("user", "cover_card")
    inlines         = [CollectionItemInline]


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display    = ("card", "collection", "quantity", "condition", "finish", "language")
    list_filter     = ("condition", "finish")
    search_fields   = ("card__name", "collection__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("collection", "card", "print")


class DeckCardInline(admin.TabularInline):
    model         = DeckCard
    extra         = 0
    raw_id_fields = ("card", "print")
    fields        = ("card", "zone", "quantity", "owned", "print")
    readonly_fields = ("id",)


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display    = ("name", "user", "format", "is_public", "featured", "main_count")
    list_filter     = ("format", "is_public", "featured")
    search_fields   = ("name", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("user", "cover_card")
    inlines         = [DeckCardInline]
    fieldsets = (
        ("Info", {
            "fields": ("user", "name", "description", "format", "cover_card"),
        }),
        ("Visibilidad", {
            "fields": ("is_public", "featured"),
        }),
        ("Notas", {
            "fields": ("notes",),
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(DeckCard)
class DeckCardAdmin(admin.ModelAdmin):
    list_display    = ("card", "deck", "zone", "quantity", "owned")
    list_filter     = ("zone", "owned")
    search_fields   = ("card__name", "deck__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("deck", "card", "print")