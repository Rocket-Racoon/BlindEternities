# nexus/admin.py
from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = ("user", "name", "preferred_format", "is_public", "created_at")
    list_filter   = ("is_public", "preferred_format")
    search_fields = ("user__username", "user__email", "display_name")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Usuario", {
            "fields": ("user", "display_name", "avatar")
        }),
        ("Perfil", {
            "fields": ("bio", "location", "preferred_format", "is_public")
        }),
        ("Metadata", {
            "fields": ("id", "is_active", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )