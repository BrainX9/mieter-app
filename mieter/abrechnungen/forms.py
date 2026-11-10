"""Formulare der Oberfläche. Dezimalzahlen werden mit Komma eingegeben (localize=True)."""

import datetime
from decimal import Decimal
from functools import partial

from django import forms
from django.contrib.auth import get_user_model

from mieter.kern.templatetags.format import zahl_formatieren
from mieter.kern.zahlen import deutsche_zahl

from .hilfe import VORSCHLAG_BEZEICHNUNG
from .models import (
    Abrechnung,
    Abrechnungsbereich,
    Brennstoffbezug,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Raumverbrauch,
    Vorauszahlung,
    Wohnung,
    Zusatzfeld,
    Zusatzwert,
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
    """Kosten eines Bereichs.

    Im Bereich „Umlage individuell“ ist das eine individuelle Umlage: Name, Art (die
    Kostenart) und Gesamtbetrag der Wohnung. Sonst Kostenart und Gesamtkosten des Hauses.
    """

    class Meta:
        model = Kostenposition
        fields = ["bezeichnung", "kostenart", "betrag", "notiz"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bereich = self.instance.bereich
        # Nur Kostenarten, die zum Verteilerschlüssel des Bereichs passen. Die bisherige
        # Kostenart bleibt wählbar, auch wenn sich der Schlüssel des Bereichs geändert hat.
        passend = Kostenart.objects.filter(aktiv=True).passend_zu(bereich.verteilerschluessel)
        if self.instance.kostenart_id:
            passend = passend | Kostenart.objects.filter(pk=self.instance.kostenart_id)
        kostenart = self.fields["kostenart"]
        kostenart.queryset = passend.distinct()
        if bereich.ist_individuell:
            kostenart.label = "Art"
            kostenart.empty_label = "Art wählen …"
            self.fields["betrag"].label = "Gesamtbetrag (€)"
            self.fields["bezeichnung"].widget.attrs["placeholder"] = "z. B. Heizkostenabrechnung"
            self.fields["bezeichnung"].help_text = "Leer lassen für den Namen der Art."
        else:
            kostenart.empty_label = "Kostenart wählen …"
            del self.fields["bezeichnung"]

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


class BrennstoffbezugForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Brennstoffbezug
        fields = ["bezugsdatum", "menge_kwh", "betrag", "vermieteranteil_co2"]
        widgets = {"bezugsdatum": DatumEingabe()}


class RaumverbrauchForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Raumverbrauch
        fields = ["raum", "geraetenummer", "einheiten"]
        widgets = {
            "raum": forms.TextInput(attrs={"placeholder": "z. B. Wohnzimmer"}),
        }


class VorauszahlungForm(LokalisierteZahlenMixin, forms.ModelForm):
    class Meta:
        model = Vorauszahlung
        fields = ["bezeichnung", "betrag", "bereich"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bereich"].queryset = self.instance.abrechnung.bereiche.all()
        self.fields["bereich"].empty_label = "ohne Bereich"


class MitgliedNeuForm(forms.Form):
    """Mitglied über die E-Mail-Adresse eines vorhandenen Kontos hinzufügen."""

    email = forms.EmailField(
        label="E-Mail-Adresse",
        widget=forms.EmailInput(attrs={"placeholder": "name@example.org", "autocomplete": "off"}),
    )
    rolle = forms.ChoiceField(
        label="Rolle", choices=Mitgliedschaft.Rolle, initial=Mitgliedschaft.Rolle.LESEN
    )

    def __init__(self, *args, wohnung, **kwargs):
        super().__init__(*args, **kwargs)
        self.wohnung = wohnung

    def clean_email(self):
        email = self.cleaned_data["email"]
        nutzer = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
        if nutzer is None:
            raise forms.ValidationError(
                "Zu dieser E-Mail-Adresse gibt es kein Konto. Das Konto muss zuerst angelegt "
                "werden (im Admin oder über die Registrierung)."
            )
        if self.wohnung.mitgliedschaften.filter(nutzer=nutzer).exists():
            raise forms.ValidationError("Diese Person ist schon Mitglied der Wohnung.")
        self.nutzer = nutzer
        return email

    def save(self):
        return Mitgliedschaft.objects.create(
            nutzer=self.nutzer, wohnung=self.wohnung, rolle=self.cleaned_data["rolle"]
        )


class ZusatzfeldForm(forms.ModelForm):
    """Feld einer Wohnung. Der Typ ist fest, sobald es Werte gibt."""

    class Meta:
        model = Zusatzfeld
        fields = ["name", "typ", "einheit", "reihenfolge"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "z. B. Einheiten Wohnzimmer"}),
            "einheit": forms.TextInput(attrs={"placeholder": "z. B. Einheiten, m³, kWh"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.werte.exists():
            self.fields["typ"].disabled = True
            self.fields["typ"].help_text = "Das Feld hat schon Werte, der Typ bleibt deshalb fest."

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        doppelt = (
            Zusatzfeld.objects.filter(wohnung=self.instance.wohnung, name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if doppelt:
            raise forms.ValidationError("Ein Feld mit diesem Namen gibt es schon.")
        return name


class ZusatzwerteForm(forms.Form):
    """Alle Zusatzfelder der Wohnung für eine Abrechnung. Leer heißt: kein Wert."""

    SPALTE = {
        Zusatzfeld.Typ.ZAHL: "wert_zahl",
        Zusatzfeld.Typ.TEXT: "wert_text",
        Zusatzfeld.Typ.DATUM: "wert_datum",
    }

    def __init__(self, *args, abrechnung, **kwargs):
        super().__init__(*args, **kwargs)
        self.abrechnung = abrechnung
        self.felder = list(abrechnung.wohnung.zusatzfelder.all())
        werte = {w.feld_id: w for w in abrechnung.zusatzwerte.select_related("feld")}
        for feld in self.felder:
            name = f"feld_{feld.pk}"
            self.fields[name] = self._formularfeld(feld)
            if feld.pk in werte:
                self.initial[name] = werte[feld.pk].wert

    @staticmethod
    def _formularfeld(feld):
        label = f"{feld.name} ({feld.einheit})" if feld.einheit else feld.name
        if feld.typ == Zusatzfeld.Typ.ZAHL:
            formularfeld = forms.DecimalField(
                label=label, required=False, max_digits=14, decimal_places=4, localize=True
            )
            formularfeld.widget = DezimalEingabe()
            formularfeld.widget.is_localized = True
            formularfeld.to_python = partial(_deutsch_einlesen, formularfeld.to_python)
            return formularfeld
        if feld.typ == Zusatzfeld.Typ.DATUM:
            return forms.DateField(label=label, required=False, widget=DatumEingabe())
        return forms.CharField(label=label, required=False, max_length=2000)

    def zeilen(self):
        """(Zusatzfeld, gebundenes Formularfeld) für das Template."""
        return [(feld, self[f"feld_{feld.pk}"]) for feld in self.felder]

    def save(self):
        for feld in self.felder:
            wert = self.cleaned_data.get(f"feld_{feld.pk}")
            if wert is None or wert == "":
                Zusatzwert.objects.filter(abrechnung=self.abrechnung, feld=feld).delete()
                continue
            daten = {"wert_zahl": None, "wert_text": "", "wert_datum": None}
            daten[self.SPALTE[feld.typ]] = wert
            Zusatzwert.objects.update_or_create(
                abrechnung=self.abrechnung, feld=feld, defaults=daten
            )
