from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Nutzer


@admin.register(Nutzer)
class NutzerAdmin(UserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Persönliche Daten", {"fields": ["first_name", "last_name"]}),
        (
            "Berechtigungen",
            {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]},
        ),
        ("Wichtige Daten", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "password1", "password2"]}),
    ]
