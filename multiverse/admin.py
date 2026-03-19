# multiverse/admin.py
from django.contrib import admin
from .models import CardSet, Card, CardFace, CardPrint, CardLegality, Ruling


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    list_display    = ("code", "name", "set_type", "released_at", "card_count", "digital", "foil_only")
    list_filter     = ("set_type", "digital", "foil_only", "nonfoil_only")
    search_fields   = ("code", "name", "block", "arena_code", "mtgo_code")
    readonly_fields = ("id", "scryfall_id", "created_at", "updated_at")
    fieldsets = (
        ("Identificadores", {
            "fields": ("scryfall_id", "code", "mtgo_code", "arena_code", "tcgplayer_id", "cardmarket_id"),
        }),
        ("Info", {
            "fields": ("name", "set_type", "released_at", "block_code", "block", "parent_set_code"),
        }),
        ("Conteos", {
            "fields": ("card_count", "printed_size"),
        }),
        ("Flags", {
            "fields": ("digital", "foil_only", "nonfoil_only"),
        }),
        ("URIs", {
            "fields": ("icon_svg_uri", "search_uri", "scryfall_uri"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


class CardFaceInline(admin.TabularInline):
    model           = CardFace
    extra           = 0
    readonly_fields = ("id", "created_at", "updated_at")
    fields          = ("face_index", "name", "type_line", "mana_cost", "oracle_text", "power", "toughness", "loyalty")


class CardPrintInline(admin.TabularInline):
    model           = CardPrint
    extra           = 0
    readonly_fields = ("id", "scryfall_id", "created_at", "updated_at")
    fields          = ("cardset", "collector_number", "rarity", "artist", "digital", "promo")
    raw_id_fields   = ("cardset",)


class CardLegalityInline(admin.StackedInline):
    model           = CardLegality
    extra           = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display    = ("name", "type_line", "mana_cost", "cmc", "layout", "can_be_commander", "has_deck_limit")
    list_filter     = ("layout", "reserved", "can_be_commander", "has_deck_limit", "banned_as_companion")
    search_fields   = ("name", "oracle_text", "type_line")
    readonly_fields = ("id", "oracle_id", "created_at", "updated_at")
    inlines         = [CardFaceInline, CardPrintInline, CardLegalityInline]
    fieldsets = (
        ("Identidad", {
            "fields": ("oracle_id", "name", "lang", "layout"),
        }),
        ("Oracle", {
            "fields": ("type_line", "oracle_text", "mana_cost", "cmc",
                       "colors", "color_identity", "color_indicator"),
        }),
        ("Stats", {
            "fields": ("power", "toughness", "loyalty", "defense",
                       "hand_modifier", "life_modifier"),
        }),
        ("Extras", {
            "fields": ("keywords", "produced_mana", "all_parts",
                       "edhrec_rank", "penny_rank"),
        }),
        ("Deck building", {
            "fields": ("can_be_commander", "has_deck_limit", "max_deck_copies", "banned_as_companion"),
        }),
        ("Identificadores externos", {
            "fields": ("multiverse_ids", "mtgo_id", "mtgo_foil_id",
                       "arena_id", "tcgplayer_id", "cardmarket_id"),
            "classes": ("collapse",),
        }),
        ("Flags", {
            "fields": ("reserved", "foil", "nonfoil", "oversized"),
            "classes": ("collapse",),
        }),
        ("URIs", {
            "fields": ("scryfall_uri", "rulings_uri", "prints_search_uri"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(CardFace)
class CardFaceAdmin(admin.ModelAdmin):
    list_display    = ("card", "face_index", "name", "type_line", "mana_cost")
    list_filter     = ("face_index",)
    search_fields   = ("name", "oracle_text", "card__name")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("card",)
    fieldsets = (
        ("Identidad", {
            "fields": ("card", "face_index", "name", "printed_name", "flavor_name", "layout", "oracle_id"),
        }),
        ("Oracle", {
            "fields": ("type_line", "printed_type_line", "oracle_text", "printed_text",
                       "mana_cost", "cmc", "colors", "color_indicator"),
        }),
        ("Stats", {
            "fields": ("power", "toughness", "loyalty", "defense"),
        }),
        ("Print", {
            "fields": ("artist", "artist_id", "illustration_id",
                       "image_uris", "flavor_text", "watermark"),
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(CardPrint)
class CardPrintAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "rarity", "lang", "artist", "digital", "promo", "full_art")
    list_filter     = ("rarity", "digital", "promo", "full_art", "textless",
                       "booster", "reprint", "lang")
    search_fields   = ("card__name", "artist", "collector_number", "flavor_text")
    readonly_fields = ("id", "scryfall_id", "created_at", "updated_at")
    raw_id_fields   = ("card", "cardset")
    fieldsets = (
        ("Identidad", {
            "fields": ("scryfall_id", "card", "cardset", "collector_number", "lang"),
        }),
        ("Identificadores externos", {
            "fields": ("multiverse_ids", "mtgo_id", "mtgo_foil_id", "arena_id",
                       "tcgplayer_id", "tcgplayer_etched_id", "cardmarket_id",
                       "illustration_id", "variation_of"),
            "classes": ("collapse",),
        }),
        ("Print", {
            "fields": ("rarity", "artist", "artist_id", "flavor_text", "flavor_name",
                       "printed_name", "printed_type_line", "printed_text",
                       "border_color", "frame", "frame_effects",
                       "security_stamp", "watermark", "set_type"),
        }),
        ("Imágenes", {
            "fields": ("image_uris", "image_status"),
            "classes": ("collapse",),
        }),
        ("Finishes", {
            "fields": ("finishes", "foil", "nonfoil"),
        }),
        ("Flags", {
            "fields": ("full_art", "textless", "booster", "digital", "promo",
                       "reprint", "variation", "oversized", "story_spotlight",
                       "content_warning", "reserved", "promo_types", "games"),
        }),
        ("Precios", {
            "fields": ("prices", "purchase_uris", "related_uris"),
        }),
        ("Fechas", {
            "fields": ("released_at", "preview"),
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(Ruling)
class RulingAdmin(admin.ModelAdmin):
    list_display    = ("card", "source", "published_at")
    list_filter     = ("source",)
    search_fields   = ("card__name", "comment")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("card",)


@admin.register(CardLegality)
class CardLegalityAdmin(admin.ModelAdmin):
    list_display    = ("card",)
    search_fields   = ("card__name",)
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("card",)