"""Formulare der Oberfläche. Dezimalzahlen werden mit Komma eingegeben (localize=True)."""

import datetime
from functools import partial

from django import forms

from mieter.kern.zahlen import deutsche_zahl

from .models import (
    Abrechnung,
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Vorauszahlung,
    Wohnung,
)


class DatumEingabe(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


def _deutsch_einlesen(to_python, wert):
    return to_python(deutsche_zahl(wert))


class LokalisierteZahlenMixin:
    """Dezimalfelder akzeptieren 1.234,56 und zeigen deutsche Schreibweise."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for feld in self.fields.values():
            if isinstance(feld, forms.DecimalField):
                feld.localize = True
                feld.widget.is_localized = True
                feld.widget.attrs.setdefault("inputmode", "decimal")
                feld.to_python = partial(_deutsch_einlesen, feld.to_python)


class WohnungForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Wohnung
        fields = ["bezeichnung", "adresse", "wohnflaeche"]
        widgets = {"adresse": forms.Textarea(attrs={"rows": 2})}


class AbrechnungForm(forms.ModelForm):
    class Meta:
        model = Abrechnung
        fields = ["abrechnungsjahr", "zeitraum_von", "zeitraum_bis", "vermieter", "notiz"]
        widgets = {
            "zeitraum_von": DatumEingabe(),
            "zeitraum_bis": DatumEingabe(),
            "notiz": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "zeitraum_von": "Leer lassen für den 1. Januar des Abrechnungsjahres.",
            "zeitraum_bis": "Leer lassen für den 31. Dezember des Abrechnungsjahres.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["zeitraum_von"].required = False
        self.fields["zeitraum_bis"].required = False

    def clean(self):
        daten = super().clean()
        jahr = daten.get("abrechnungsjahr")
        if jahr:
            if not daten.get("zeitraum_von"):
                daten["zeitraum_von"] = datetime.date(jahr, 1, 1)
            if not daten.get("zeitraum_bis"):
                daten["zeitraum_bis"] = datetime.date(jahr, 12, 31)
        return daten


class AbrechnungsbereichForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Abrechnungsbereich
        fields = [
            "bezeichnung",
            "verteilerschluessel",
            "gesamtmenge",
            "anteil_menge",
            "rundungsregel",
            "nachkommastellen",
            "reihenfolge",
        ]


class KostenpositionForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Kostenposition
        fields = ["kostenart", "betrag", "notiz"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Nur Kostenarten, die zum Verteilerschlüssel des Bereichs passen.
        self.fields["kostenart"].queryset = Kostenart.objects.filter(aktiv=True).passend_zu(
            self.instance.bereich.verteilerschluessel
        )
        self.fields["kostenart"].empty_label = "Kostenart wählen …"

    def clean_kostenart(self):
        kostenart = self.cleaned_data["kostenart"]
        doppelt = (
            Kostenposition.objects.filter(bereich=self.instance.bereich, kostenart=kostenart)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if doppelt:
            raise forms.ValidationError("Diese Kostenart gibt es in dem Bereich schon.")
        return kostenart


class VorauszahlungForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Vorauszahlung
        fields = ["bezeichnung", "betrag", "bereich"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bereich"].queryset = self.instance.abrechnung.bereiche.all()
        self.fields["bereich"].empty_label = "ohne Bereich"
