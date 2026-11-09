"""Datenmodell für Wohnungen und Betriebskostenabrechnungen.

Kostenarten und Zusatzfelder sind Daten, keine Spalten: Neue Kostenarten oder Felder
brauchen keine Migration.
"""

from django import forms
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

GELD = {"max_digits": 12, "decimal_places": 2}
MENGE = {"max_digits": 14, "decimal_places": 4}


class Verteilerschluessel(models.TextChoices):
    """Wie Kosten auf die Wohnungen umgelegt werden."""

    WOHNFLAECHE = "wohnflaeche", "Umlage nach Fläche (m²)"
    WOHNEINHEITEN = "wohneinheiten", "Umlage pro Wohnung"
    PERSONEN_PUNKTE = "personen_punkte", "Umlage nach Personen / Punkten"
    INDIVIDUELL = "individuell", "Umlage individuell"


class MehrfachauswahlFeld(ArrayField):
    """Liste von Auswahlwerten, im Formular als Ankreuzfelder."""

    def formfield(self, **kwargs):
        return forms.TypedMultipleChoiceField(
            choices=self.base_field.choices,
            widget=forms.CheckboxSelectMultiple,
            required=not self.blank,
            label=self.verbose_name,
            help_text=self.help_text,
        )


class WohnungsdatenQuerySet(models.QuerySet):
    """Filtert über die Mitgliedschaft des Nutzers in der Wohnung.

    Jedes Modell legt in WOHNUNG_PFAD fest, wie es zur Wohnung kommt.
    """

    def _pfad(self, feld):
        pfad = self.model.WOHNUNG_PFAD
        return f"{pfad}__{feld}" if pfad else feld

    def fuer_nutzer(self, nutzer):
        """Alles, was der Nutzer sehen darf."""
        if not getattr(nutzer, "is_authenticated", False):
            return self.none()
        return self.filter(**{self._pfad("mitgliedschaften__nutzer"): nutzer})

    def verwaltbar_fuer(self, nutzer):
        """Alles, was der Nutzer ändern darf."""
        if not getattr(nutzer, "is_authenticated", False):
            return self.none()
        return self.filter(
            **{
                self._pfad("mitgliedschaften__nutzer"): nutzer,
                self._pfad("mitgliedschaften__rolle"): Mitgliedschaft.Rolle.VERWALTEN,
            }
        )


class Wohnung(models.Model):
    WOHNUNG_PFAD = ""

    bezeichnung = models.CharField("Bezeichnung", max_length=200)
    adresse = models.TextField("Adresse", blank=True)
    wohnflaeche = models.DecimalField(
        "Wohnfläche (m²)", null=True, blank=True, validators=[MinValueValidator(0)], **MENGE
    )
    mitglieder = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Mitgliedschaft",
        related_name="wohnungen",
        verbose_name="Mitglieder",
    )

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Wohnung"
        verbose_name_plural = "Wohnungen"
        ordering = ["bezeichnung"]

    def __str__(self):
        return self.bezeichnung

    def get_absolute_url(self):
        return reverse("wohnung_detail", args=[self.pk])


class Mitgliedschaft(models.Model):
    WOHNUNG_PFAD = "wohnung"

    class Rolle(models.TextChoices):
        VERWALTEN = "verwalten", "Verwalten"
        LESEN = "lesen", "Nur lesen"

    nutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mitgliedschaften",
        verbose_name="Nutzer",
    )
    wohnung = models.ForeignKey(
        Wohnung, on_delete=models.CASCADE, related_name="mitgliedschaften", verbose_name="Wohnung"
    )
    rolle = models.CharField("Rolle", max_length=20, choices=Rolle, default=Rolle.VERWALTEN)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Mitgliedschaft"
        verbose_name_plural = "Mitgliedschaften"
        constraints = [
            models.UniqueConstraint(fields=["nutzer", "wohnung"], name="mitgliedschaft_eindeutig"),
        ]

    def __str__(self):
        return f"{self.nutzer} – {self.wohnung} ({self.get_rolle_display()})"


class KostenartQuerySet(models.QuerySet):
    def passend_zu(self, verteilerschluessel):
        """Kostenarten für einen Bereich. Ohne hinterlegten Schlüssel passt eine Kostenart immer."""
        return self.filter(
            Q(verteilerschluessel__contains=[verteilerschluessel]) | Q(verteilerschluessel=[])
        )


class Kostenart(models.Model):
    """Katalog der Kostenarten, z. B. nach § 2 BetrKV. Gilt für alle Wohnungen."""

    name = models.CharField("Name", max_length=200, unique=True)
    beschreibung = models.TextField("Beschreibung", blank=True)
    verteilerschluessel = MehrfachauswahlFeld(
        models.CharField(max_length=20, choices=Verteilerschluessel),
        verbose_name="Passende Verteilerschlüssel",
        default=list,
        blank=True,
        help_text="Nur in Bereichen mit diesen Schlüsseln wählbar. Ohne Auswahl: überall.",
    )
    hinweis = models.TextField(
        "Hinweis",
        blank=True,
        help_text="Wird bei der Kostenart angezeigt, z. B. was zu prüfen ist.",
    )
    betrkv_nummer = models.PositiveSmallIntegerField(
        "Nr. nach § 2 BetrKV",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(17)],
    )
    brennstoffangaben = models.BooleanField(
        "Mit Brennstoff-/Energiekosten",
        default=False,
        help_text="Bei individueller Umlage lassen sich Brennstoff-Bezüge mit CO₂-Kosten erfassen.",
    )
    aktiv = models.BooleanField("Aktiv", default=True)

    objects = KostenartQuerySet.as_manager()

    class Meta:
        verbose_name = "Kostenart"
        verbose_name_plural = "Kostenarten"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Abrechnung(models.Model):
    WOHNUNG_PFAD = "wohnung"

    wohnung = models.ForeignKey(
        Wohnung, on_delete=models.CASCADE, related_name="abrechnungen", verbose_name="Wohnung"
    )
    abrechnungsjahr = models.PositiveSmallIntegerField(
        "Abrechnungsjahr", validators=[MinValueValidator(1990), MaxValueValidator(2100)]
    )
    zeitraum_von = models.DateField("Abrechnungszeitraum von")
    zeitraum_bis = models.DateField("Abrechnungszeitraum bis")
    vermieter = models.CharField("Vermieter", max_length=200, blank=True)
    notiz = models.TextField("Notiz", blank=True)
    erstellt_am = models.DateTimeField("Erstellt am", auto_now_add=True)
    geaendert_am = models.DateTimeField("Geändert am", auto_now=True)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Abrechnung"
        verbose_name_plural = "Abrechnungen"
        ordering = ["-abrechnungsjahr", "-zeitraum_von", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(zeitraum_bis__gte=F("zeitraum_von")),
                name="abrechnung_zeitraum_gueltig",
                violation_error_message="Das Ende des Zeitraums liegt vor dem Beginn.",
            ),
        ]

    def __str__(self):
        return f"{self.wohnung} – {self.abrechnungsjahr}"

    def get_absolute_url(self):
        return reverse("abrechnung_detail", args=[self.pk])

    def berechnen(self):
        """Rechnet die Abrechnung nach. Siehe mieter.abrechnungen.berechnung."""
        from .berechnung import abrechnung_berechnen

        return abrechnung_berechnen(self)


class Abrechnungsbereich(models.Model):
    """Ein Block der Abrechnung mit eigenem Verteilerschlüssel und eigener Rundungsregel."""

    WOHNUNG_PFAD = "abrechnung__wohnung"

    Verteilerschluessel = Verteilerschluessel

    class Rundungsregel(models.TextChoices):
        WIE_VERMIETER = "wie_vermieter", "Wie Vermieter: Preis je Einheit auf Cent gerundet"
        N_STELLEN = "n_stellen", "Preis je Einheit auf eigene Stellenzahl gerundet"
        EXAKT = "exakt", "Exakt: nur der Endbetrag wird gerundet"

    abrechnung = models.ForeignKey(
        Abrechnung, on_delete=models.CASCADE, related_name="bereiche", verbose_name="Abrechnung"
    )
    bezeichnung = models.CharField("Bezeichnung", max_length=200)
    verteilerschluessel = models.CharField(
        "Verteilerschlüssel",
        max_length=20,
        choices=Verteilerschluessel,
        default=Verteilerschluessel.WOHNFLAECHE,
    )
    gesamtmenge = models.DecimalField(
        "Gesamtmenge",
        null=True,
        blank=True,
        help_text="Summe des Verteilerschlüssels im Haus, z. B. Gesamtwohnfläche.",
        **MENGE,
    )
    anteil_menge = models.DecimalField(
        "Anteil der Wohnung",
        null=True,
        blank=True,
        help_text="Wert der Wohnung im Verteilerschlüssel, z. B. ihre Wohnfläche.",
        **MENGE,
    )
    rundungsregel = models.CharField(
        "Rundungsregel",
        max_length=20,
        choices=Rundungsregel,
        default=Rundungsregel.WIE_VERMIETER,
    )
    nachkommastellen = models.PositiveSmallIntegerField(
        "Nachkommastellen",
        default=2,
        validators=[MaxValueValidator(6)],
        help_text="Nur für „Preis je Einheit auf eigene Stellenzahl gerundet“.",
    )
    reihenfolge = models.PositiveSmallIntegerField("Reihenfolge", default=0)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Abrechnungsbereich"
        verbose_name_plural = "Abrechnungsbereiche"
        ordering = ["reihenfolge", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(gesamtmenge__isnull=True) | Q(gesamtmenge__gt=0),
                name="bereich_gesamtmenge_positiv",
                violation_error_message="Die Gesamtmenge muss größer als 0 sein.",
            ),
            models.CheckConstraint(
                condition=Q(anteil_menge__isnull=True) | Q(anteil_menge__gte=0),
                name="bereich_anteil_nicht_negativ",
                violation_error_message="Der Anteil darf nicht negativ sein.",
            ),
            models.CheckConstraint(
                condition=Q(nachkommastellen__lte=6),
                name="bereich_nachkommastellen_max_6",
                violation_error_message="Höchstens 6 Nachkommastellen.",
            ),
        ]

    def __str__(self):
        return self.bezeichnung

    @property
    def ist_individuell(self):
        return self.verteilerschluessel == Verteilerschluessel.INDIVIDUELL

    def clean(self):
        if self.ist_individuell:
            return
        fehler = {}
        if self.gesamtmenge is None:
            fehler["gesamtmenge"] = "Für diesen Verteilerschlüssel ist eine Gesamtmenge nötig."
        if self.anteil_menge is None:
            fehler["anteil_menge"] = "Für diesen Verteilerschlüssel ist der Anteil nötig."
        if (
            self.gesamtmenge is not None
            and self.anteil_menge is not None
            and self.anteil_menge > self.gesamtmenge
        ):
            fehler["anteil_menge"] = "Der Anteil ist größer als die Gesamtmenge."
        if fehler:
            raise ValidationError(fehler)


class Kostenposition(models.Model):
    """Kosten einer Kostenart in einem Bereich.

    Bei „Umlage individuell“ ist das der Betrag der Wohnung, sonst die
    Gesamtkosten des Hauses.
    """

    WOHNUNG_PFAD = "bereich__abrechnung__wohnung"

    bereich = models.ForeignKey(
        Abrechnungsbereich,
        on_delete=models.CASCADE,
        related_name="positionen",
        verbose_name="Bereich",
    )
    kostenart = models.ForeignKey(
        Kostenart, on_delete=models.PROTECT, related_name="positionen", verbose_name="Kostenart"
    )
    bezeichnung = models.CharField(
        "Name",
        max_length=200,
        blank=True,
        help_text="Für individuelle Umlagen, z. B. „Heizkostenabrechnung Messdienst“.",
    )
    betrag = models.DecimalField("Betrag (€)", **GELD)
    notiz = models.CharField("Notiz", max_length=500, blank=True)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Kostenposition"
        verbose_name_plural = "Kostenpositionen"
        ordering = ["kostenart__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["bereich", "kostenart"],
                name="kostenposition_eindeutig",
                violation_error_message="Diese Kostenart gibt es in dem Bereich schon.",
            ),
        ]

    def __str__(self):
        return f"{self.name}: {self.betrag} €"

    def get_absolute_url(self):
        return reverse("position_detail", args=[self.pk])

    @property
    def name(self):
        """Eigener Name, sonst die Kostenart."""
        return self.bezeichnung or self.kostenart.name

    @property
    def zeigt_brennstoff(self):
        return self.kostenart.brennstoffangaben or self.brennstoffbezuege.exists()


class Brennstoffbezug(models.Model):
    """Bezug von Brennstoff oder Energie zu einer individuellen Umlage (Heizung)."""

    WOHNUNG_PFAD = "position__bereich__abrechnung__wohnung"

    position = models.ForeignKey(
        Kostenposition,
        on_delete=models.CASCADE,
        related_name="brennstoffbezuege",
        verbose_name="Umlage",
    )
    bezugsdatum = models.DateField("Bezugsdatum")
    menge_kwh = models.DecimalField("Menge (kWh)", validators=[MinValueValidator(0)], **MENGE)
    betrag = models.DecimalField("Betrag (€)", validators=[MinValueValidator(0)], **GELD)
    vermieteranteil_co2 = models.DecimalField(
        "Vermieteranteil CO₂-Kosten (€)",
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Anteil der CO₂-Kosten, den der Vermieter trägt.",
        **GELD,
    )

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Brennstoff-Bezug"
        verbose_name_plural = "Brennstoff-Bezüge"
        ordering = ["bezugsdatum", "id"]

    def __str__(self):
        return f"{self.bezugsdatum:%d.%m.%Y}: {self.menge_kwh} kWh"

    @property
    def brennstoffkosten(self):
        """Summe Brennstoff-/Energiekosten: Betrag minus Vermieteranteil CO₂-Kosten."""
        return self.betrag - self.vermieteranteil_co2

    def clean(self):
        if (
            self.betrag is not None
            and self.vermieteranteil_co2 is not None
            and self.vermieteranteil_co2 > self.betrag
        ):
            raise ValidationError(
                {"vermieteranteil_co2": "Der Vermieteranteil ist größer als der Betrag."}
            )


class Raumverbrauch(models.Model):
    """Verbrauchseinheiten eines Raums, z. B. abgelesen am Heizkostenverteiler."""

    WOHNUNG_PFAD = "position__bereich__abrechnung__wohnung"

    position = models.ForeignKey(
        Kostenposition,
        on_delete=models.CASCADE,
        related_name="raumverbraeuche",
        verbose_name="Umlage",
    )
    raum = models.CharField("Raum", max_length=100)
    geraetenummer = models.CharField("Gerätenummer", max_length=100, blank=True)
    einheiten = models.DecimalField("Einheiten", validators=[MinValueValidator(0)], **MENGE)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Verbrauch je Raum"
        verbose_name_plural = "Verbrauch je Raum"
        ordering = ["id"]

    def __str__(self):
        return f"{self.raum}: {self.einheiten}"


class Vorauszahlung(models.Model):
    WOHNUNG_PFAD = "abrechnung__wohnung"

    abrechnung = models.ForeignKey(
        Abrechnung,
        on_delete=models.CASCADE,
        related_name="vorauszahlungen",
        verbose_name="Abrechnung",
    )
    bereich = models.ForeignKey(
        Abrechnungsbereich,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vorauszahlungen",
        verbose_name="Bereich",
    )
    bezeichnung = models.CharField("Bezeichnung", max_length=200)
    betrag = models.DecimalField("Betrag (€)", **GELD)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Vorauszahlung"
        verbose_name_plural = "Vorauszahlungen"
        ordering = ["id"]

    def __str__(self):
        return f"{self.bezeichnung}: {self.betrag} €"

    def clean(self):
        if self.bereich_id and self.bereich.abrechnung_id != self.abrechnung_id:
            raise ValidationError({"bereich": "Der Bereich gehört zu einer anderen Abrechnung."})


class Zusatzfeld(models.Model):
    """Frei definierbares Feld einer Wohnung, z. B. Ablesewert eines Heizkostenverteilers."""

    WOHNUNG_PFAD = "wohnung"

    class Typ(models.TextChoices):
        ZAHL = "zahl", "Zahl"
        TEXT = "text", "Text"
        DATUM = "datum", "Datum"

    wohnung = models.ForeignKey(
        Wohnung, on_delete=models.CASCADE, related_name="zusatzfelder", verbose_name="Wohnung"
    )
    name = models.CharField("Name", max_length=200)
    typ = models.CharField("Typ", max_length=10, choices=Typ, default=Typ.ZAHL)
    einheit = models.CharField("Einheit", max_length=50, blank=True)
    reihenfolge = models.PositiveSmallIntegerField("Reihenfolge", default=0)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Zusatzfeld"
        verbose_name_plural = "Zusatzfelder"
        ordering = ["reihenfolge", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["wohnung", "name"],
                name="zusatzfeld_eindeutig",
                violation_error_message="Ein Feld mit diesem Namen gibt es schon.",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.einheit})" if self.einheit else self.name


class Zusatzwert(models.Model):
    WOHNUNG_PFAD = "abrechnung__wohnung"

    abrechnung = models.ForeignKey(
        Abrechnung, on_delete=models.CASCADE, related_name="zusatzwerte", verbose_name="Abrechnung"
    )
    feld = models.ForeignKey(
        Zusatzfeld, on_delete=models.CASCADE, related_name="werte", verbose_name="Feld"
    )
    wert_zahl = models.DecimalField("Zahl", null=True, blank=True, **MENGE)
    wert_text = models.TextField("Text", blank=True)
    wert_datum = models.DateField("Datum", null=True, blank=True)

    objects = WohnungsdatenQuerySet.as_manager()

    class Meta:
        verbose_name = "Zusatzwert"
        verbose_name_plural = "Zusatzwerte"
        ordering = ["feld__reihenfolge", "feld__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["abrechnung", "feld"],
                name="zusatzwert_eindeutig",
                violation_error_message="Für dieses Feld gibt es schon einen Wert.",
            ),
        ]

    def __str__(self):
        return f"{self.feld.name}: {self.wert}"

    @property
    def wert(self):
        return {
            Zusatzfeld.Typ.ZAHL: self.wert_zahl,
            Zusatzfeld.Typ.TEXT: self.wert_text,
            Zusatzfeld.Typ.DATUM: self.wert_datum,
        }[self.feld.typ]

    def clean(self):
        if not (self.feld_id and self.abrechnung_id):
            return
        if self.feld.wohnung_id != self.abrechnung.wohnung_id:
            raise ValidationError({"feld": "Das Feld gehört zu einer anderen Wohnung."})
        belegt = {
            Zusatzfeld.Typ.ZAHL: self.wert_zahl is not None,
            Zusatzfeld.Typ.TEXT: bool(self.wert_text),
            Zusatzfeld.Typ.DATUM: self.wert_datum is not None,
        }
        fremd = [typ for typ, gesetzt in belegt.items() if gesetzt and typ != self.feld.typ]
        if fremd:
            raise ValidationError(
                f"Das Feld „{self.feld.name}“ erwartet den Typ {self.feld.get_typ_display()}."
            )
