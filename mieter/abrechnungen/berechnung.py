"""Nachrechnen einer Betriebskostenabrechnung.

Regeln (siehe CLAUDE.md):
- Geld immer Decimal, gerundet wird mit ROUND_HALF_UP.
- Gerundet wird nach der Rundungsregel des Abrechnungsbereichs:
  - wie Vermieter: Einheitspreis auf 2 Stellen runden, dann mal Anteil, Ergebnis auf Cent
  - n Stellen:     wie oben, aber Einheitspreis auf n Stellen
  - exakt:         keine Zwischenrundung, nur das Ergebnis auf Cent
- Die exakte Rechnung (ohne jede Rundung) wird immer mitgeführt.

Der Kern rechnet auf einfachen Datenklassen (BereichEingabe), damit er ohne Datenbank
testbar ist. abrechnung_berechnen() baut die Eingaben aus den Modellen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext

CENT = Decimal("0.01")
NULL = Decimal("0")

# Genug Stellen, damit die exakte Rechnung bei Geldbeträgen nichts verliert.
_KONTEXT = Context(prec=40, rounding=ROUND_HALF_UP)

WIE_VERMIETER = "wie_vermieter"
N_STELLEN = "n_stellen"
EXAKT = "exakt"
INDIVIDUELL = "individuell"

MENGENEINHEITEN = {
    "wohnflaeche": "m²",
    "wohneinheiten": "Wohnung",
    "personen_punkte": "Person/Punkt",
}


def runden(wert: Decimal, stellen: int = 2) -> Decimal:
    """Kaufmännisch runden (ROUND_HALF_UP) auf die angegebene Zahl an Stellen."""
    return wert.quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class BereichEingabe:
    bezeichnung: str
    verteilerschluessel: str
    rundungsregel: str
    kosten: list[Decimal]
    gesamtmenge: Decimal | None = None
    anteil_menge: Decimal | None = None
    nachkommastellen: int = 2


@dataclass(frozen=True)
class Bereichsergebnis:
    bezeichnung: str
    verteilerschluessel: str
    rundungsregel: str
    kosten: Decimal
    gesamtmenge: Decimal | None
    anteil_menge: Decimal | None
    einheitspreis_exakt: Decimal | None
    einheitspreis: Decimal | None
    anteil_exakt: Decimal | None
    anteil: Decimal | None
    fehler: str | None = None

    @property
    def vollstaendig(self) -> bool:
        return self.fehler is None

    @property
    def mengeneinheit(self) -> str:
        """Einheit des Verteilerschlüssels, z. B. für „3,33 € je m²“."""
        return MENGENEINHEITEN.get(self.verteilerschluessel, "")

    @property
    def rundungsdifferenz(self) -> Decimal | None:
        """Gerundeter Anteil minus exakter Anteil."""
        if self.anteil is None or self.anteil_exakt is None:
            return None
        return self.anteil - self.anteil_exakt


@dataclass(frozen=True)
class Abrechnungsergebnis:
    bereiche: list[Bereichsergebnis]
    vorauszahlungen: Decimal
    fehler: list[str] = field(default_factory=list)

    @property
    def vollstaendig(self) -> bool:
        return not self.fehler

    @property
    def summe_anteile(self) -> Decimal | None:
        if not self.vollstaendig:
            return None
        return sum((b.anteil for b in self.bereiche), NULL)

    @property
    def summe_anteile_exakt(self) -> Decimal | None:
        if not self.vollstaendig:
            return None
        return sum((b.anteil_exakt for b in self.bereiche), NULL)

    @property
    def saldo(self) -> Decimal | None:
        """Positiv: Nachzahlung. Negativ: Guthaben."""
        if not self.vollstaendig:
            return None
        return self.summe_anteile - self.vorauszahlungen

    @property
    def saldo_betrag(self) -> Decimal | None:
        """Saldo ohne Vorzeichen, z. B. für „Guthaben 136,24 €“."""
        return None if self.saldo is None else abs(self.saldo)

    @property
    def saldo_exakt(self) -> Decimal | None:
        if not self.vollstaendig:
            return None
        return self.summe_anteile_exakt - self.vorauszahlungen

    @property
    def ist_nachzahlung(self) -> bool:
        return self.saldo is not None and self.saldo > 0

    @property
    def ist_guthaben(self) -> bool:
        return self.saldo is not None and self.saldo < 0


def _stellen(eingabe: BereichEingabe) -> int | None:
    """Stellen für den Einheitspreis; None heißt: nicht runden."""
    if eingabe.rundungsregel == WIE_VERMIETER:
        return 2
    if eingabe.rundungsregel == N_STELLEN:
        return eingabe.nachkommastellen
    if eingabe.rundungsregel == EXAKT:
        return None
    raise ValueError(f"Unbekannte Rundungsregel: {eingabe.rundungsregel}")


def bereich_berechnen(eingabe: BereichEingabe) -> Bereichsergebnis:
    with localcontext(_KONTEXT):
        kosten = sum(eingabe.kosten, NULL)
        basis = {
            "bezeichnung": eingabe.bezeichnung,
            "verteilerschluessel": eingabe.verteilerschluessel,
            "rundungsregel": eingabe.rundungsregel,
            "kosten": kosten,
            "gesamtmenge": eingabe.gesamtmenge,
            "anteil_menge": eingabe.anteil_menge,
        }

        if eingabe.verteilerschluessel == INDIVIDUELL:
            # Der Betrag ist schon der Anteil der Wohnung, es wird nichts verteilt.
            return Bereichsergebnis(
                **basis,
                einheitspreis_exakt=None,
                einheitspreis=None,
                anteil_exakt=kosten,
                anteil=runden(kosten),
            )

        fehler = None
        if eingabe.gesamtmenge is None or eingabe.gesamtmenge <= 0:
            fehler = f"{eingabe.bezeichnung}: Gesamtmenge fehlt oder ist 0."
        elif eingabe.anteil_menge is None:
            fehler = f"{eingabe.bezeichnung}: Anteil der Wohnung fehlt."
        if fehler:
            return Bereichsergebnis(
                **basis,
                einheitspreis_exakt=None,
                einheitspreis=None,
                anteil_exakt=None,
                anteil=None,
                fehler=fehler,
            )

        einheitspreis_exakt = kosten / eingabe.gesamtmenge
        anteil_exakt = einheitspreis_exakt * eingabe.anteil_menge

        stellen = _stellen(eingabe)
        if stellen is None:
            einheitspreis = einheitspreis_exakt
            anteil = runden(anteil_exakt)
        else:
            einheitspreis = runden(einheitspreis_exakt, stellen)
            anteil = runden(einheitspreis * eingabe.anteil_menge)

        return Bereichsergebnis(
            **basis,
            einheitspreis_exakt=einheitspreis_exakt,
            einheitspreis=einheitspreis,
            anteil_exakt=anteil_exakt,
            anteil=anteil,
        )


def berechnen(
    bereiche: list[BereichEingabe], vorauszahlungen: list[Decimal]
) -> Abrechnungsergebnis:
    ergebnisse = [bereich_berechnen(b) for b in bereiche]
    with localcontext(_KONTEXT):
        summe_vorauszahlungen = sum(vorauszahlungen, NULL)
    return Abrechnungsergebnis(
        bereiche=ergebnisse,
        vorauszahlungen=summe_vorauszahlungen,
        fehler=[e.fehler for e in ergebnisse if e.fehler],
    )


def abrechnung_berechnen(abrechnung) -> Abrechnungsergebnis:
    """Rechnet eine gespeicherte Abrechnung nach."""
    bereiche = [
        BereichEingabe(
            bezeichnung=b.bezeichnung,
            verteilerschluessel=b.verteilerschluessel,
            rundungsregel=b.rundungsregel,
            kosten=[p.betrag for p in b.positionen.all()],
            gesamtmenge=b.gesamtmenge,
            anteil_menge=b.anteil_menge,
            nachkommastellen=b.nachkommastellen,
        )
        for b in abrechnung.bereiche.prefetch_related("positionen")
    ]
    vorauszahlungen = [v.betrag for v in abrechnung.vorauszahlungen.all()]
    return berechnen(bereiche, vorauszahlungen)
