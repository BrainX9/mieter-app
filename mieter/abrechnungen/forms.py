"""Formulare der Oberfläche. Dezimalzahlen werden mit Komma eingegeben (localize=True)."""

import datetime
from decimal import Decimal
from functools import partial

from django import forms

from mieter.kern.templatetags.format import zahl_formatieren
from mieter.kern.zahlen import deutsche_zahl

from .hilfe import VORSCHLAG_BEZEICHNUNG
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


class DezimalEingabe(forms.TextInput):
    """Textfeld für deutsche Zahlen.

    Kein type="number": Browser verwerfen dort Komma und Tausenderpunkte. Gespeicherte
    Werte erscheinen deutsch, Geld mit zwei Stellen, Mengen ohne Nullen am Ende.
    """

    def __init__(self, stellen=None, attrs=None):
        super().__init__(attrs={"inputmode": "decimal", "autocomplete": "off", **(attrs or {})})
        self.stellen = stellen

    def format_value(self, value):
        if isinstance(value, Decimal):
            return zahl_formatieren(value, self.stellen)
        return super().format_value(value)


class LokalisierteZahlenMixin:
    """Dezimalfelder akzeptieren 1.234,56 und zeigen deutsche Schreibweise."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for feld in self.fields.values():
            if isinstance(feld, forms.DecimalField):
                feld.localize = True
                feld.widget = DezimalEingabe(stellen=2 if feld.decimal_places == 2 else None)
                feld.widget.is_localized = True
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
    """Bezeichnung darf leer bleiben, dann gilt der ausgegraute Vorschlag."""

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
        labels = {
            "gesamtmenge": "Gesamtmenge (alle Wohnungen)",
            "anteil_menge": "Anteil deiner Wohnung",
        }
        widgets = {"rundungsregel": forms.RadioSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bezeichnung = self.fields["bezeichnung"]
        bezeichnung.required = False
        bezeichnung.widget.attrs["placeholder"] = VORSCHLAG_BEZEICHNUNG
        bezeichnung.help_text = f"Leer lassen für „{VORSCHLAG_BEZEICHNUNG}“."
        # Die Hilfe zu den Mengen steht je Verteilerschlüssel im Template.
        self.fields["gesamtmenge"].help_text = ""
        self.fields["anteil_menge"].help_text = ""

    def clean_bezeichnung(self):
        return self.cleaned_data["bezeichnung"].strip() or VORSCHLAG_BEZEICHNUNG


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
