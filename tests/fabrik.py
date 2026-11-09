"""Synthetische Testdaten. Keine echten Daten verwenden."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model

from mieter.abrechnungen.models import (
    Abrechnung,
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Vorauszahlung,
    Wohnung,
    Zusatzfeld,
    Zusatzwert,
)

_zaehler = iter(range(1, 10_000))


def nutzer(**felder):
    n = next(_zaehler)
    felder.setdefault("email", f"nutzer{n}@example.org")
    return get_user_model().objects.create_user(password="x", **felder)


def wohnung(mitglied=None, rolle=Mitgliedschaft.Rolle.VERWALTEN, **felder):
    felder.setdefault("bezeichnung", f"Musterwohnung {next(_zaehler)}")
    felder.setdefault("wohnflaeche", Decimal("75.50"))
    w = Wohnung.objects.create(**felder)
    if mitglied:
        Mitgliedschaft.objects.create(nutzer=mitglied, wohnung=w, rolle=rolle)
    return w


def abrechnung(wohnung, jahr=2024, **felder):
    felder.setdefault("zeitraum_von", datetime.date(jahr, 1, 1))
    felder.setdefault("zeitraum_bis", datetime.date(jahr, 12, 31))
    return Abrechnung.objects.create(wohnung=wohnung, abrechnungsjahr=jahr, **felder)


def kostenart(name=None):
    return Kostenart.objects.get_or_create(name=name or f"Testkosten {next(_zaehler)}")[0]


def bereich(abrechnung, **felder):
    felder.setdefault("bezeichnung", "Allgemeine Betriebskosten")
    felder.setdefault("gesamtmenge", Decimal("300"))
    felder.setdefault("anteil_menge", Decimal("75.5"))
    return Abrechnungsbereich.objects.create(abrechnung=abrechnung, **felder)


def position(bereich, betrag, kostenart_name=None):
    return Kostenposition.objects.create(
        bereich=bereich, kostenart=kostenart(kostenart_name), betrag=Decimal(betrag)
    )


def vorauszahlung(abrechnung, betrag, bezeichnung="Vorauszahlung Betriebskosten"):
    return Vorauszahlung.objects.create(
        abrechnung=abrechnung, bezeichnung=bezeichnung, betrag=Decimal(betrag)
    )


def zusatzfeld(wohnung, name="Einheiten Testraum", typ=Zusatzfeld.Typ.ZAHL, einheit=""):
    return Zusatzfeld.objects.create(wohnung=wohnung, name=name, typ=typ, einheit=einheit)


def zusatzwert(abrechnung, feld, **werte):
    return Zusatzwert.objects.create(abrechnung=abrechnung, feld=feld, **werte)
