from django.contrib import admin
from .models import CreatureType, Mechanic

admin.site.site_header = "Blind Eternities"
admin.site.site_title = "Blind Eternities Admin"
admin.site.index_title = "Admin Panel"

@admin.register(CreatureType)
class CreatureTypeAdmin(admin.ModelAdmin):
    list_display    = ("name", "is_active", "created_at")
    search_fields   = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")
    

@admin.register(Mechanic)
class MechanicAdmin(admin.ModelAdmin):
    list_display    = ("name", "kind", "slug", "synced_at")
    list_filter     = ("kind",)
    search_fields   = ("name",)
    readonly_fields = ("id", "slug", "synced_at", "created_at", "updated_at")