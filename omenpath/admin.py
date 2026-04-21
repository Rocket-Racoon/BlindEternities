from django.contrib import admin
from .models import Listing, Transaction, TransactionItem, PriceQuote


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display    = ("card_print", "owner", "listing_type", "quantity", "asking_price", "status", "visibility")
    list_filter     = ("listing_type", "status", "visibility", "condition", "finish")
    search_fields   = ("card_print__card__name", "owner__username")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("owner", "card_print")


class TransactionItemInline(admin.TabularInline):
    model           = TransactionItem
    extra           = 0
    raw_id_fields   = ("card_print",)
    fields          = ("side", "card_print", "quantity", "condition", "finish", "language", "unit_value")
    readonly_fields = ("id",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display    = ("kind", "party_a", "party_b", "status", "confirmed_by_a", "confirmed_by_b", "created_at")
    list_filter     = ("kind", "status")
    search_fields   = ("party_a__username", "party_b__username")
    readonly_fields = ("id", "created_at", "updated_at", "completed_at")
    raw_id_fields   = ("party_a", "party_b", "listing")
    inlines         = [TransactionItemInline]


@admin.register(TransactionItem)
class TransactionItemAdmin(admin.ModelAdmin):
    list_display    = ("card_print", "transaction", "side", "quantity", "unit_value")
    list_filter     = ("side", "condition", "finish")
    search_fields   = ("card_print__card__name",)
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields   = ("transaction", "card_print")


@admin.register(PriceQuote)
class PriceQuoteAdmin(admin.ModelAdmin):
    list_display    = ("card_print", "source", "finish", "price", "currency", "fetched_at")
    list_filter     = ("source", "finish", "currency")
    search_fields   = ("card_print__card__name",)
    readonly_fields = ("id", "created_at", "updated_at", "fetched_at", "raw")
    raw_id_fields   = ("card_print",)
