"""Formular „Abrechnungsbereich“: Vorschlag, Hilfen und verständliche Rundungsregeln."""

from decimal import Decimal as D

import pytest
from django.urls import reverse

from mieter.abrechnungen import hilfe
from mieter.abrechnungen.models import Abrechnungsbereich, Verteilerschluessel
from tests import fabrik

pytestmark = pytest.mark.django_db
V = Verteilerschluessel
R = Abrechnungsbereich.Rundungsregel


@pytest.fixture
def abrechnung(client):
    ich = fabrik.nutzer()
    client.force_login(ich)
    return fabrik.abrechnung(fabrik.wohnung(mitglied=ich))


def formular(client, abrechnung):
    return client.get(reverse("bereich_neu", args=[abrechnung.pk])).content.decode()


class TestBezeichnung:
    def test_vorschlag_ausgegraut(self, client, abrechnung):
        assert 'placeholder="Allgemeine Betriebskosten"' in formular(client, abrechnung)

    def test_leer_uebernimmt_vorschlag(self, client, abrechnung):
        client.post(
            reverse("bereich_neu", args=[abrechnung.pk]),
            {
                "bezeichnung": "  ",
                "verteilerschluessel": V.WOHNFLAECHE,
                "gesamtmenge": "300",
                "anteil_menge": "75,5",
                "rundungsregel": R.WIE_VERMIETER,
                "nachkommastellen": "2",
                "reihenfolge": "1",
            },
        )
        assert abrechnung.bereiche.get().bezeichnung == "Allgemeine Betriebskosten"

    def test_eigene_bezeichnung_bleibt(self, client, abrechnung):
        client.post(
            reverse("bereich_neu", args=[abrechnung.pk]),
            {
                "bezeichnung": "Heizung",
                "verteilerschluessel": V.INDIVIDUELL,
                "rundungsregel": R.WIE_VERMIETER,
                "nachkommastellen": "2",
                "reihenfolge": "1",
            },
        )
        b = abrechnung.bereiche.get()
        assert b.bezeichnung == "Heizung"
        assert b.gesamtmenge is None


class TestMengenhilfe:
    def test_fuer_jeden_schluessel_mit_mengen(self):
        assert set(hilfe.MENGENHILFE) == set(V.values) - {V.INDIVIDUELL}
        for h in hilfe.MENGENHILFE.values():
            assert "z. B." in h.gesamtmenge
            assert h.anteil

    def test_alle_hilfen_im_formular(self, client, abrechnung):
        inhalt = formular(client, abrechnung)
        for schluessel, h in hilfe.MENGENHILFE.items():
            assert f'data-schluessel="{schluessel}"' in inhalt
            assert h.gesamtmenge in inhalt
            assert h.anteil in inhalt
        assert hilfe.INDIVIDUELL_HILFE in inhalt
        assert "Gesamtmenge (alle Wohnungen)" in inhalt
        assert "Anteil deiner Wohnung" in inhalt
        assert "bereich.js" in inhalt

    def test_auch_beim_bearbeiten(self, client, abrechnung):
        b = fabrik.bereich(abrechnung)
        inhalt = client.get(reverse("bereich_bearbeiten", args=[b.pk])).content.decode()
        assert hilfe.MENGENHILFE[V.WOHNFLAECHE].gesamtmenge in inhalt


class TestRundungsregeln:
    def test_verstaendliche_bezeichnungen(self):
        assert R.WIE_VERMIETER.label == "Wie Vermieter: Preis je Einheit auf Cent gerundet"
        assert R.EXAKT.label == "Exakt: nur der Endbetrag wird gerundet"
        assert set(hilfe.RUNDUNG_ERKLAERUNG) == set(R.values)

    def test_rechenbeispiel_aus_dem_rechenkern(self):
        anteile = {z["regel"]: z["anteil"] for z in hilfe.rundungsbeispiel()}
        assert anteile == {
            R.WIE_VERMIETER: D("251.42"),  # 3,33 × 75,5
            R.N_STELLEN: D("251.64"),  # 3,333 × 75,5
            R.EXAKT: D("251.67"),  # 1000 × 75,5 / 300
        }

    def test_hilfe_im_formular(self, client, abrechnung):
        inhalt = formular(client, abrechnung)
        assert "Welche Rundungsregel passt?" in inhalt
        assert 'type="radio" name="rundungsregel"' in inhalt
        for betrag in ["251,42", "251,64", "251,67"]:
            assert betrag in inhalt


class TestZahleneingabe:
    """Dezimalfelder sind Textfelder mit deutscher Schreibweise, kein type="number"."""

    def test_gespeicherte_mengen_deutsch_ohne_nullen(self, client, abrechnung):
        b = fabrik.bereich(abrechnung, gesamtmenge=D("1234.5"), anteil_menge=D("75.5"))
        inhalt = client.get(reverse("bereich_bearbeiten", args=[b.pk])).content.decode()
        assert 'type="number" name="gesamtmenge"' not in inhalt
        assert 'type="text" name="gesamtmenge"' in inhalt
        assert 'value="1.234,5"' in inhalt
        assert 'value="75,5"' in inhalt
        assert 'inputmode="decimal"' in inhalt

    def test_geld_mit_zwei_stellen(self):
        from mieter.abrechnungen.forms import DezimalEingabe

        assert DezimalEingabe(stellen=2).format_value(D("12.5")) == "12,50"
        assert DezimalEingabe().format_value(D("3.2500")) == "3,25"

    def test_eingabe_bleibt_bei_fehlern_stehen(self, client, abrechnung):
        antwort = client.post(
            reverse("bereich_neu", args=[abrechnung.pk]),
            {
                "verteilerschluessel": V.WOHNFLAECHE,
                "gesamtmenge": "1.234,5",
                "rundungsregel": R.WIE_VERMIETER,
                "nachkommastellen": "2",
                "reihenfolge": "1",
            },
        )
        inhalt = antwort.content.decode()
        assert 'value="1.234,5"' in inhalt
        assert "der Anteil nötig" in inhalt
