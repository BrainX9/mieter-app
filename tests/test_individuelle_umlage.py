"""Individuelle Umlage: Name, Art, Gesamtbetrag, Brennstoff-Bezüge und Verbrauch je Raum."""

import datetime
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from mieter.abrechnungen.forms import KostenpositionForm
from mieter.abrechnungen.models import (
    Brennstoffbezug,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Raumverbrauch,
    Verteilerschluessel,
)
from tests import fabrik

pytestmark = pytest.mark.django_db
NBSP = "\u00a0"


def individueller_bereich(abrechnung, **felder):
    felder.setdefault("bezeichnung", "Heizung und Warmwasser")
    return fabrik.bereich(
        abrechnung,
        verteilerschluessel=Verteilerschluessel.INDIVIDUELL,
        gesamtmenge=None,
        anteil_menge=None,
        **felder,
    )


def umlage(bereich, kostenart="Heizung und Warmwasser", betrag="912.47", **felder):
    return Kostenposition.objects.create(
        bereich=bereich,
        kostenart=Kostenart.objects.get(name=kostenart),
        betrag=D(betrag),
        **felder,
    )


def bezug(position, betrag="1200.00", co2="85.40", menge="9500"):
    return Brennstoffbezug.objects.create(
        position=position,
        bezugsdatum=datetime.date(2024, 3, 1),
        menge_kwh=D(menge),
        betrag=D(betrag),
        vermieteranteil_co2=D(co2),
    )


@pytest.fixture
def ich(client):
    n = fabrik.nutzer()
    client.force_login(n)
    return n


@pytest.fixture
def abrechnung(ich):
    return fabrik.abrechnung(fabrik.wohnung(mitglied=ich))


@pytest.fixture
def heizung(abrechnung):
    return umlage(individueller_bereich(abrechnung), bezeichnung="Heizkostenabrechnung")


def seite(client, position):
    return client.get(reverse("position_detail", args=[position.pk]))


class TestModell:
    def test_brennstoffangaben_bei_heizung(self):
        mit = set(Kostenart.objects.filter(brennstoffangaben=True).values_list("name", flat=True))
        assert mit == {"Heizung", "Heizung und Warmwasser"}

    def test_brennstoffkosten(self, heizung):
        assert bezug(heizung, "1200.00", "85.40").brennstoffkosten == D("1114.60")

    def test_vermieteranteil_nicht_groesser_als_betrag(self, heizung):
        b = Brennstoffbezug(
            position=heizung,
            bezugsdatum=datetime.date(2024, 1, 1),
            menge_kwh=D("1"),
            betrag=D("10.00"),
            vermieteranteil_co2=D("10.01"),
        )
        with pytest.raises(ValidationError, match="größer als der Betrag"):
            b.full_clean()

    def test_name_faellt_auf_kostenart_zurueck(self, abrechnung):
        p = umlage(individueller_bereich(abrechnung))
        assert p.name == "Heizung und Warmwasser"

    def test_nur_eigene_daten(self, heizung, ich):
        bezug(heizung)
        Raumverbrauch.objects.create(position=heizung, raum="Bad", einheiten=D("12.5"))
        fremd = fabrik.nutzer()
        for modell in [Brennstoffbezug, Raumverbrauch]:
            assert modell.objects.fuer_nutzer(ich).count() == 1
            assert modell.objects.fuer_nutzer(fremd).count() == 0

    def test_loeschen_der_umlage_loescht_details(self, heizung):
        bezug(heizung)
        Raumverbrauch.objects.create(position=heizung, raum="Bad", einheiten=D("1"))
        heizung.delete()
        assert not Brennstoffbezug.objects.exists()
        assert not Raumverbrauch.objects.exists()


class TestFormularImBereich:
    def test_individuell_mit_name_art_gesamtbetrag(self, abrechnung):
        form = KostenpositionForm(
            instance=Kostenposition(bereich=individueller_bereich(abrechnung))
        )
        assert list(form.fields) == ["bezeichnung", "kostenart", "betrag", "notiz"]
        assert form.fields["kostenart"].label == "Art"
        assert form.fields["betrag"].label == "Gesamtbetrag (€)"

    def test_sonst_ohne_name(self, abrechnung):
        form = KostenpositionForm(instance=Kostenposition(bereich=fabrik.bereich(abrechnung)))
        assert "bezeichnung" not in form.fields

    def test_umlage_hinzufuegen(self, client, abrechnung):
        bereich = individueller_bereich(abrechnung)
        art = Kostenart.objects.get(name="Heizung")
        p = f"b{bereich.pk}"
        client.post(
            reverse("position_neu", args=[bereich.pk]),
            {f"{p}-bezeichnung": "Fernwärme", f"{p}-kostenart": art.pk, f"{p}-betrag": "1.004,20"},
        )
        position = bereich.positionen.get()
        assert position.name == "Fernwärme"
        assert position.betrag == D("1004.20")

    def test_name_und_betrag_in_der_uebersicht(self, client, heizung):
        url = reverse("abrechnung_detail", args=[heizung.bereich.abrechnung_id])
        inhalt = client.get(url).content.decode()
        assert f"Heizkostenabrechnung: 912,47{NBSP}€" in inhalt
        assert heizung.get_absolute_url() in inhalt

    def test_posten_nur_bei_individuell(self, heizung):
        allgemein = fabrik.bereich(heizung.bereich.abrechnung)
        fabrik.position(allgemein, "400.00", "Grundsteuer")
        ergebnis = heizung.bereich.abrechnung.berechnen()
        posten = {b.bezeichnung: b.posten for b in ergebnis.bereiche}
        assert posten["Heizung und Warmwasser"] == (("Heizkostenabrechnung", D("912.47")),)
        assert posten["Allgemeine Betriebskosten"] == ()


class TestDetailseite:
    def test_zeigt_angaben(self, client, heizung):
        inhalt = seite(client, heizung).content.decode()
        assert "Heizkostenabrechnung" in inhalt
        assert "Brennstoff-/Energiekosten" in inhalt
        assert "Verbrauchseinheiten je Raum" in inhalt

    def test_nur_fuer_individuelle_umlagen(self, client, abrechnung):
        p = fabrik.position(fabrik.bereich(abrechnung), "10.00", "Grundsteuer")
        assert seite(client, p).status_code == 404

    def test_fremde_umlage(self, client, ich):
        fremd = fabrik.abrechnung(fabrik.wohnung(mitglied=fabrik.nutzer()))
        assert seite(client, umlage(individueller_bereich(fremd))).status_code == 404

    def test_brennstoff_nur_wenn_passend(self, client, abrechnung):
        wasser = umlage(individueller_bereich(abrechnung), "Wasserversorgung", "300.00")
        assert 'id="brennstoff"' not in seite(client, wasser).content.decode()
        bezug(wasser)
        assert 'id="brennstoff"' in seite(client, wasser).content.decode()

    def test_angaben_bearbeiten(self, client, heizung):
        client.post(
            reverse("position_bearbeiten", args=[heizung.pk]),
            {"bezeichnung": "Messdienst 2024", "kostenart": heizung.kostenart_id, "betrag": "950"},
        )
        heizung.refresh_from_db()
        assert heizung.name == "Messdienst 2024"
        assert heizung.bereich.abrechnung.berechnen().summe_anteile == D("950.00")

    def test_nur_lesen(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer())
        Mitgliedschaft.objects.create(nutzer=ich, wohnung=w, rolle=Mitgliedschaft.Rolle.LESEN)
        p = umlage(individueller_bereich(fabrik.abrechnung(w)))
        inhalt = seite(client, p).content.decode()
        assert "Bezug hinzufügen" not in inhalt
        assert "Raum hinzufügen" not in inhalt
        for name in ["position_bearbeiten", "brennstoff_neu", "raum_neu"]:
            assert client.post(reverse(name, args=[p.pk]), {}).status_code == 403


class TestBrennstoff:
    def test_hinzufuegen_mit_summen(self, client, heizung):
        bezug(heizung, "1200.00", "85.40", "9500")
        antwort = client.post(
            reverse("brennstoff_neu", args=[heizung.pk]),
            {
                "bezugsdatum": "2024-10-15",
                "menge_kwh": "4.250,5",
                "betrag": "612,30",
                "vermieteranteil_co2": "41,10",
            },
            follow=True,
        )
        inhalt = antwort.content.decode()
        assert heizung.brennstoffbezuege.count() == 2
        assert f"571,20{NBSP}€" in inhalt  # 612,30 − 41,10
        assert "13.750,5 kWh" in inhalt
        assert f"1.685,80{NBSP}€" in inhalt  # 1.114,60 + 571,20

    def test_fehler_bleibt_auf_der_seite(self, client, heizung):
        antwort = client.post(
            reverse("brennstoff_neu", args=[heizung.pk]),
            {
                "bezugsdatum": "2024-10-15",
                "menge_kwh": "100",
                "betrag": "10",
                "vermieteranteil_co2": "20",
            },
        )
        assert antwort.status_code == 200
        assert "größer als der Betrag" in antwort.content.decode()
        assert not heizung.brennstoffbezuege.exists()

    def test_htmx_bekommt_die_seite(self, client, heizung):
        """Das Formular nutzt hx-select: Die Antwort ist die Seite mit dem Abschnitt."""
        antwort = client.post(
            reverse("brennstoff_neu", args=[heizung.pk]),
            {
                "bezugsdatum": "2024-01-02",
                "menge_kwh": "1",
                "betrag": "1",
                "vermieteranteil_co2": "0",
            },
            headers={"HX-Request": "true"},
            follow=True,
        )
        assert 'id="brennstoff"' in antwort.content.decode()
        assert 'hx-select="#brennstoff"' in antwort.content.decode()

    def test_entfernen(self, client, heizung):
        b = bezug(heizung)
        client.post(reverse("brennstoff_loeschen", args=[b.pk]))
        assert not heizung.brennstoffbezuege.exists()

    def test_fremden_bezug_nicht_entfernen(self, client, ich):
        fremd = umlage(
            individueller_bereich(fabrik.abrechnung(fabrik.wohnung(mitglied=fabrik.nutzer())))
        )
        b = bezug(fremd)
        assert client.post(reverse("brennstoff_loeschen", args=[b.pk])).status_code == 404
        assert Brennstoffbezug.objects.filter(pk=b.pk).exists()


class TestRaeume:
    def test_hinzufuegen_mit_summe(self, client, heizung):
        for raum, nummer, einheiten in [("Wohnzimmer", "AF554", "120,5"), ("Bad", "KL604", "33")]:
            client.post(
                reverse("raum_neu", args=[heizung.pk]),
                {"raum": raum, "geraetenummer": nummer, "einheiten": einheiten},
            )
        inhalt = seite(client, heizung).content.decode()
        assert heizung.raumverbraeuche.count() == 2
        assert "AF554" in inhalt
        assert "<strong>153,5</strong>" in inhalt

    def test_raum_pflicht(self, client, heizung):
        antwort = client.post(reverse("raum_neu", args=[heizung.pk]), {"einheiten": "5"})
        assert antwort.status_code == 200
        assert not heizung.raumverbraeuche.exists()

    def test_entfernen(self, client, heizung):
        r = Raumverbrauch.objects.create(position=heizung, raum="Küche", einheiten=D("8"))
        client.post(reverse("raum_loeschen", args=[r.pk]))
        assert not heizung.raumverbraeuche.exists()
