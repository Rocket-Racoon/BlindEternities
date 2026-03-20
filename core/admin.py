from django.contrib import admin
from .models import CreatureType

admin.site.site_header = "Blind Eternities"
admin.site.site_title = "Blind Eternities Admin"
admin.site.index_title = "Admin Panel"

@admin.register(CreatureType)
class CreatureTypeAdmin(admin.ModelAdmin):
    list_display    = ("name", "is_active", "created_at")
    search_fields   = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")