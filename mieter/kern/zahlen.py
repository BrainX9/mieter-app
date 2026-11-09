"""Eingabe von Zahlen in deutscher Schreibweise."""

import re

_TAUSENDERGRUPPEN = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+$")


def deutsche_zahl(wert):
    """Macht aus deutscher Schreibweise eine Zahl mit Dezimalpunkt (als Text).

    - Mit Komma: Komma ist der Dezimaltrenner, Punkte sind Tausenderpunkte.
      „1.234,56“ → „1234.56“
    - Ohne Komma: reine Tausendergruppen gelten als Tausenderpunkte („1.234“ → „1234“),
      sonst ist der Punkt ein Dezimalpunkt („75.5“ → „75.5“).
    Leerzeichen und ein Eurozeichen werden entfernt. Alles andere bleibt unverändert,
    damit die Prüfung des Formularfelds den Fehler meldet.
    """
    if not isinstance(wert, str):
        return wert
    text = wert.replace("€", "").replace(" ", "").replace(" ", "").strip()
    if "," in text:
        return text.replace(".", "").replace(",", ".")
    if _TAUSENDERGRUPPEN.match(text):
        return text.replace(".", "")
    return text
