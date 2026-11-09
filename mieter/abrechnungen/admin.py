"""Admin für Wohnungen und Abrechnungen.

Superuser sehen alles. Alle anderen Mitarbeiter (is_staff) sehen nur Wohnungsdaten,
in denen sie Mitglied sind.
"""

from django.contrib import admin

from .models import (
    Abrechnung,
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Verteilerschluessel,
    Vorauszahlung,
    Wohnung,
    Zusatzfeld,
    Zusatzwert,
)


class NurEigeneWohnungenMixin:
    """Filtert Listen und Auswahlfelder über die Mitgliedschaft (außer für Superuser)."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.fuer_nutzer(request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        ziel = db_field.related_model
        if hasattr(ziel, "WOHNUNG_PFAD") and not request.user.is_superuser:
            kwargs["queryset"] = ziel.objects.fuer_nutzer(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MitgliedschaftInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Mitgliedschaft
    extra = 0
    autocomplete_fields = ["nutzer"]


class ZusatzfeldInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Zusatzfeld
    extra = 0


@admin.register(Wohnung)
class WohnungAdmin(NurEigeneWohnungenMixin, admin.ModelAdmin):
    list_display = ["bezeichnung", "wohnflaeche"]
    search_fields = ["bezeichnung", "adresse"]
    inlines = [MitgliedschaftInline, ZusatzfeldInline]


@admin.register(Kostenart)
class KostenartAdmin(admin.ModelAdmin):
    list_display = ["name", "betrkv_nummer", "schluessel", "aktiv"]
    list_filter = ["aktiv"]
    search_fields = ["name"]

    @admin.display(description="Verteilerschlüssel")
    def schluessel(self, obj):
        namen = dict(Verteilerschluessel.choices)
        return ", ".join(namen.get(s, s) for s in obj.verteilerschluessel) or "alle"


class AbrechnungsbereichInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Abrechnungsbereich
    extra = 0
    show_change_link = True


class VorauszahlungInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Vorauszahlung
    extra = 0


class ZusatzwertInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Zusatzwert
    extra = 0


@admin.register(Abrechnung)
class AbrechnungAdmin(NurEigeneWohnungenMixin, admin.ModelAdmin):
    list_display = ["wohnung", "abrechnungsjahr", "zeitraum_von", "zeitraum_bis", "vermieter"]
    list_filter = ["abrechnungsjahr", "wohnung"]
    inlines = [AbrechnungsbereichInline, VorauszahlungInline, ZusatzwertInline]


class KostenpositionInline(NurEigeneWohnungenMixin, admin.TabularInline):
    model = Kostenposition
    extra = 0
    autocomplete_fields = ["kostenart"]


@admin.register(Abrechnungsbereich)
class AbrechnungsbereichAdmin(NurEigeneWohnungenMixin, admin.ModelAdmin):
    list_display = ["bezeichnung", "abrechnung", "verteilerschluessel", "rundungsregel"]
    list_filter = ["verteilerschluessel", "rundungsregel"]
    inlines = [KostenpositionInline]
