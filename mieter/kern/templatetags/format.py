"""Deutsche Zahlen- und Geldformate, unabhängig von Locale-Einstellungen des Servers.

{{ betrag|euro }}        → 1.234,56 €
{{ wert|zahl:4 }}        → 1.234,5678
{{ wert|zahl }}          → so viele Stellen wie nötig, ohne Nullen am Ende
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def _als_decimal(wert):
    if wert is None or wert == "":
        return None
    if isinstance(wert, float):
        # Floats haben im Geldbereich nichts verloren; über str() wenigstens ohne Binärfehler.
        wert = str(wert)
    try:
        return Decimal(wert)
    except (InvalidOperation, TypeError, ValueError):
        return None


def zahl_formatieren(wert, stellen=None):
    d = _als_decimal(wert)
    if d is None:
        return ""
    if stellen is not None:
        d = d.quantize(Decimal(1).scaleb(-int(stellen)), rounding=ROUND_HALF_UP)
    vorzeichen = "-" if d < 0 else ""
    text = f"{abs(d):f}"
    ganz, _, nachkomma = text.partition(".")
    if stellen is None:
        nachkomma = nachkomma.rstrip("0")
    gruppen = []
    while len(ganz) > 3:
        gruppen.insert(0, ganz[-3:])
        ganz = ganz[:-3]
    gruppen.insert(0, ganz)
    ergebnis = ".".join(gruppen)
    if nachkomma:
        ergebnis += "," + nachkomma
    if ergebnis.strip("0.,") == "":
        vorzeichen = ""  # kein "-0,00"
    return vorzeichen + ergebnis


@register.filter
def zahl(wert, stellen=None):
    return zahl_formatieren(wert, stellen)


@register.filter
def euro(wert):
    text = zahl_formatieren(wert, 2)
    return f"{text} €" if text else ""
