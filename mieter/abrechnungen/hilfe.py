"""Hilfetexte für das Formular „Abrechnungsbereich“.

Das Rechenbeispiel zu den Rundungsregeln wird mit dem echten Rechenkern erzeugt, damit
Hilfe und Nachrechnung nie auseinanderlaufen.
"""

from dataclasses import dataclass
from decimal import Decimal

from . import berechnung
from .models import Abrechnungsbereich, Verteilerschluessel

V = Verteilerschluessel
R = Abrechnungsbereich.Rundungsregel

VORSCHLAG_BEZEICHNUNG = "Allgemeine Betriebskosten"


@dataclass(frozen=True)
class Mengenhilfe:
    gesamtmenge: str
    anteil: str


MENGENHILFE = {
    V.WOHNFLAECHE: Mengenhilfe(
        gesamtmenge=(
            "Die Fläche aller Wohnungen, auf die der Vermieter die Kosten verteilt, in m². "
            "Steht in der Abrechnung meist als „Gesamtfläche“ oder „Gesamteinheiten“, "
            "z. B. 300,00."
        ),
        anteil=(
            "Deine Wohnfläche in m², so wie sie in der Abrechnung steht, z. B. 75,50. "
            "Weicht sie vom Mietvertrag ab, lohnt sich ein Blick darauf."
        ),
    ),
    V.WOHNEINHEITEN: Mengenhilfe(
        gesamtmenge="Die Zahl der Wohnungen, auf die verteilt wird, z. B. 6.",
        anteil="Fast immer 1, also deine Wohnung.",
    ),
    V.PERSONEN_PUNKTE: Mengenhilfe(
        gesamtmenge=(
            "Die Summe aller Personen oder Punkte im Haus laut Abrechnung, z. B. 14 Personen "
            "oder 1.000,00 Punkte. Bei Personentagen die Summe der Personentage."
        ),
        anteil=("Deine Personen oder Punkte laut Abrechnung, z. B. 2 Personen oder 245,50 Punkte."),
    ),
}

INDIVIDUELL_HILFE = (
    "Hier sind keine Mengen nötig. Der Betrag steht in der Abrechnung schon fertig für "
    "deine Wohnung, z. B. in der Heizkostenabrechnung des Messdienstes."
)

RUNDUNG_ERKLAERUNG = {
    R.WIE_VERMIETER: (
        "So rechnen die meisten Vermieter: Erst wird der Preis je m² (oder je Punkt) auf "
        "Cent gerundet, dann mit deinem Anteil malgenommen."
    ),
    R.N_STELLEN: (
        "Wie oben, nur wird der Preis je Einheit auf die angegebene Zahl an "
        "Nachkommastellen gerundet. Nimm das, wenn in der Abrechnung z. B. 3,333 € je m² steht."
    ),
    R.EXAKT: (
        "Ohne Zwischenrundung: Nur dein Betrag am Ende wird auf Cent gerundet. "
        "Das ist mathematisch genau, weicht aber oft um ein paar Cent vom Vermieter ab."
    ),
}

# Rechenbeispiel: 1.000 € Kosten, 300 m² Gesamtfläche, 75,5 m² Wohnung.
BEISPIEL_KOSTEN = Decimal("1000.00")
BEISPIEL_GESAMT = Decimal("300")
BEISPIEL_ANTEIL = Decimal("75.5")
BEISPIEL_STELLEN = 3


def rundungsbeispiel():
    """Ergebnis jeder Rundungsregel für das Rechenbeispiel, in der Reihenfolge der Auswahl."""
    zeilen = []
    for regel in R:
        ergebnis = berechnung.bereich_berechnen(
            berechnung.BereichEingabe(
                bezeichnung="Beispiel",
                verteilerschluessel=V.WOHNFLAECHE,
                rundungsregel=regel,
                kosten=[BEISPIEL_KOSTEN],
                gesamtmenge=BEISPIEL_GESAMT,
                anteil_menge=BEISPIEL_ANTEIL,
                nachkommastellen=BEISPIEL_STELLEN,
            )
        )
        zeilen.append(
            {
                "regel": regel,
                "erklaerung": RUNDUNG_ERKLAERUNG[regel],
                "einheitspreis": ergebnis.einheitspreis,
                "anteil": ergebnis.anteil,
            }
        )
    return zeilen
