"""Deutsche Formate für Beträge und Zahlen."""

from decimal import Decimal as D

import pytest
from django.template import Context, Template

from mieter.kern.templatetags.format import euro, zahl

NBSP = " "


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [
        (D("1234.56"), "1.234,56 €"),
        (D("0"), "0,00 €"),
        (D("0.5"), "0,50 €"),
        (D("-136.24"), "-136,24 €"),
        (D("1234567.891"), "1.234.567,89 €"),
        (D("0.125"), "0,13 €"),  # ROUND_HALF_UP
        (D("-0.001"), "0,00 €"),  # kein "-0,00 €"
        (D("999.995"), "1.000,00 €"),
        (12, "12,00 €"),
        ("7.10", "7,10 €"),
    ],
)
def test_euro(wert, erwartet):
    assert euro(wert) == erwartet.replace(" ", NBSP)


@pytest.mark.parametrize("wert", [None, "", "kein Betrag"])
def test_euro_ohne_wert(wert):
    assert euro(wert) == ""


@pytest.mark.parametrize(
    ("wert", "stellen", "erwartet"),
    [
        (D("251.6666666667"), 4, "251,6667"),
        (D("3.33"), None, "3,33"),
        (D("75.5000"), None, "75,5"),
        (D("300.0000"), None, "300"),
        (D("1234.5"), 2, "1.234,50"),
        (D("2.5"), 0, "3"),
    ],
)
def test_zahl(wert, stellen, erwartet):
    assert zahl(wert, stellen) == erwartet


def test_im_template():
    html = Template("{% load format %}{{ b|euro }} | {{ m|zahl:2 }}").render(
        Context({"b": D("1234.56"), "m": D("75.5")})
    )
    assert html == f"1.234,56{NBSP}€ | 75,50"
