"""Eingabe deutscher Zahlen."""

import pytest

from mieter.kern.zahlen import deutsche_zahl


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("1.234,56", "1234.56"),
        ("1234,56", "1234.56"),
        ("0,5", "0.5"),
        ("1.234.567,8", "1234567.8"),
        ("-12,30", "-12.30"),
        ("1.234", "1234"),  # Tausendergruppe
        ("12.345.678", "12345678"),
        ("75.5", "75.5"),  # Dezimalpunkt
        ("1.23", "1.23"),
        ("300", "300"),
        ("1.234,56 €", "1234.56"),
        (" 1 234,56 ", "1234.56"),
        ("", ""),
        ("abc", "abc"),
        (None, None),
    ],
)
def test_deutsche_zahl(eingabe, erwartet):
    assert deutsche_zahl(eingabe) == erwartet
