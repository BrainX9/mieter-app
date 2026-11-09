"""Nachrechnen: Rundungsregeln, exakte Rechnung, Saldo. Ohne Datenbank."""

from decimal import Decimal as D

import pytest

from mieter.abrechnungen import berechnung as b
from mieter.abrechnungen.models import Abrechnungsbereich


def bereich(regel=b.WIE_VERMIETER, kosten=("400.00", "350.00", "250.00"), **felder):
    felder.setdefault("verteilerschluessel", "wohnflaeche")
    felder.setdefault("gesamtmenge", D("300"))
    felder.setdefault("anteil_menge", D("75.5"))
    return b.BereichEingabe(
        bezeichnung="Allgemeine Betriebskosten",
        rundungsregel=regel,
        kosten=[D(k) for k in kosten],
        **felder,
    )


def direkt(betrag="812.34"):
    return b.BereichEingabe(
        bezeichnung="Heizung und Warmwasser",
        verteilerschluessel=b.DIREKT,
        rundungsregel=b.WIE_VERMIETER,
        kosten=[D(betrag)],
    )


class TestRunden:
    @pytest.mark.parametrize(
        ("wert", "stellen", "erwartet"),
        [
            ("0.125", 2, "0.13"),  # ROUND_HALF_EVEN ergäbe 0.12
            ("0.135", 2, "0.14"),
            ("-0.125", 2, "-0.13"),
            ("2.5", 0, "3"),  # ROUND_HALF_EVEN ergäbe 2
            ("3.33349", 3, "3.333"),
            ("10.0250", 2, "10.03"),
        ],
    )
    def test_kaufmaennisch(self, wert, stellen, erwartet):
        assert b.runden(D(wert), stellen) == D(erwartet)


class TestRundungsregeln:
    def test_wie_vermieter_rundet_einheitspreis_auf_2_stellen(self):
        e = b.bereich_berechnen(bereich(b.WIE_VERMIETER))
        assert e.kosten == D("1000.00")
        assert e.einheitspreis == D("3.33")
        assert e.anteil == D("251.42")  # 3,33 × 75,5 = 251,415

    def test_exakt_rundet_nur_das_ergebnis(self):
        e = b.bereich_berechnen(bereich(b.EXAKT))
        assert e.einheitspreis == e.einheitspreis_exakt
        assert e.anteil == D("251.67")  # 1000 × 75,5 / 300 = 251,666…

    def test_wie_vermieter_und_exakt_unterscheiden_sich(self):
        vermieter = b.bereich_berechnen(bereich(b.WIE_VERMIETER)).anteil
        exakt = b.bereich_berechnen(bereich(b.EXAKT)).anteil
        assert exakt - vermieter == D("0.25")

    @pytest.mark.parametrize(
        ("stellen", "einheitspreis", "anteil"),
        [
            (0, "3", "226.50"),
            (2, "3.33", "251.42"),
            (3, "3.333", "251.64"),  # 3,333 × 75,5 = 251,6415
            (4, "3.3333", "251.66"),  # 3,3333 × 75,5 = 251,66415
        ],
    )
    def test_n_stellen(self, stellen, einheitspreis, anteil):
        e = b.bereich_berechnen(bereich(b.N_STELLEN, nachkommastellen=stellen))
        assert e.einheitspreis == D(einheitspreis)
        assert e.anteil == D(anteil)

    def test_einheitspreis_rundet_kaufmaennisch(self):
        e = b.bereich_berechnen(
            bereich(kosten=["100.25"], gesamtmenge=D("10"), anteil_menge=D("1"))
        )
        assert e.einheitspreis_exakt == D("10.025")
        assert e.einheitspreis == D("10.03")
        assert e.anteil == D("10.03")

    def test_unbekannte_regel(self):
        with pytest.raises(ValueError, match="Rundungsregel"):
            b.bereich_berechnen(bereich("geraten"))

    def test_konstanten_passen_zum_modell(self):
        regeln = Abrechnungsbereich.Rundungsregel
        assert {b.WIE_VERMIETER, b.N_STELLEN, b.EXAKT} == set(regeln.values)
        assert b.DIREKT == Abrechnungsbereich.Verteilerschluessel.DIREKT


class TestExakteRechnung:
    def test_wird_immer_mitgefuehrt(self):
        for regel in [b.WIE_VERMIETER, b.N_STELLEN, b.EXAKT]:
            e = b.bereich_berechnen(bereich(regel))
            assert b.runden(e.anteil_exakt, 10) == D("251.6666666667")
            assert b.runden(e.einheitspreis_exakt, 10) == D("3.3333333333")

    def test_rundungsdifferenz(self):
        e = b.bereich_berechnen(bereich(b.WIE_VERMIETER))
        assert b.runden(e.rundungsdifferenz, 6) == D("-0.246667")

    def test_keine_floats(self):
        e = b.bereich_berechnen(bereich())
        for wert in [e.kosten, e.einheitspreis, e.einheitspreis_exakt, e.anteil, e.anteil_exakt]:
            assert isinstance(wert, D)


class TestSonderfaelle:
    def test_direkt_uebernimmt_den_betrag(self):
        e = b.bereich_berechnen(direkt("812.34"))
        assert e.anteil == D("812.34")
        assert e.anteil_exakt == D("812.34")
        assert e.einheitspreis is None

    def test_bereich_ohne_positionen(self):
        e = b.bereich_berechnen(bereich(kosten=[]))
        assert e.kosten == D("0")
        assert e.anteil == D("0.00")

    @pytest.mark.parametrize("gesamtmenge", [None, D("0")])
    def test_fehlende_gesamtmenge(self, gesamtmenge):
        e = b.bereich_berechnen(bereich(gesamtmenge=gesamtmenge))
        assert not e.vollstaendig
        assert "Gesamtmenge" in e.fehler
        assert e.anteil is None

    def test_fehlender_anteil(self):
        e = b.bereich_berechnen(bereich(anteil_menge=None))
        assert "Anteil" in e.fehler


class TestGesamtergebnis:
    def test_nachzahlung(self):
        e = b.berechnen([bereich(), direkt("812.34")], [D("600.00"), D("300.00")])
        assert e.summe_anteile == D("1063.76")
        assert e.vorauszahlungen == D("900.00")
        assert e.saldo == D("163.76")
        assert e.ist_nachzahlung and not e.ist_guthaben
        assert b.runden(e.saldo_exakt, 6) == D("164.006667")

    def test_guthaben(self):
        e = b.berechnen([bereich(), direkt("812.34")], [D("1200.00")])
        assert e.saldo == D("-136.24")
        assert e.ist_guthaben

    def test_ausgeglichen(self):
        e = b.berechnen([direkt("100.00")], [D("100.00")])
        assert e.saldo == D("0.00")
        assert not e.ist_nachzahlung and not e.ist_guthaben

    def test_unvollstaendig_hat_keinen_saldo(self):
        e = b.berechnen([bereich(gesamtmenge=None), direkt()], [D("100")])
        assert not e.vollstaendig
        assert len(e.fehler) == 1
        assert e.saldo is None and e.summe_anteile is None
