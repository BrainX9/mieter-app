"""Oberfläche: Ansichten, Zugriffsschutz, HTMX, deutsche Eingabe und Anzeige."""

import datetime
from decimal import Decimal as D

import pytest
from django.urls import reverse

from mieter.abrechnungen.models import (
    Abrechnung,
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Vorauszahlung,
    Wohnung,
)
from tests import fabrik

pytestmark = pytest.mark.django_db
NBSP = " "
HTMX = {"HX-Request": "true"}


def euro(text):
    """Vor dem Eurozeichen steht ein geschütztes Leerzeichen."""
    return text.replace(" €", f"{NBSP}€")


@pytest.fixture
def ich(client):
    nutzer = fabrik.nutzer(email="ich@example.org")
    client.force_login(nutzer)
    return nutzer


@pytest.fixture
def daten(ich):
    """Eigene Abrechnung mit dem Rechenbeispiel aus test_berechnung."""
    w = fabrik.wohnung(mitglied=ich, bezeichnung="Testwohnung")
    a = fabrik.abrechnung(w, jahr=2024, vermieter="Muster Hausverwaltung")
    allgemein = fabrik.bereich(a)
    fabrik.position(allgemein, "400.00", "Grundsteuer")
    fabrik.position(allgemein, "600.00", "Gebäudeversicherung")
    heizung = fabrik.bereich(
        a,
        bezeichnung="Heizung",
        verteilerschluessel=Abrechnungsbereich.Verteilerschluessel.DIREKT,
        gesamtmenge=None,
        anteil_menge=None,
        reihenfolge=2,
    )
    fabrik.position(heizung, "812.34", "Heizung und Warmwasser")
    vz = fabrik.vorauszahlung(a, "900.00")
    return {"wohnung": w, "abrechnung": a, "bereich": allgemein, "heizung": heizung, "vz": vz}


@pytest.fixture
def fremd():
    """Daten eines anderen Haushalts."""
    w = fabrik.wohnung(mitglied=fabrik.nutzer(), bezeichnung="Fremde Wohnung")
    a = fabrik.abrechnung(w)
    b = fabrik.bereich(a)
    return {
        "wohnung": w,
        "abrechnung": a,
        "bereich": b,
        "position": fabrik.position(b, "10.00", "Grundsteuer"),
        "vz": fabrik.vorauszahlung(a, "5.00"),
    }


def nur_lesen(ich, wohnung):
    Mitgliedschaft.objects.create(nutzer=ich, wohnung=wohnung, rolle=Mitgliedschaft.Rolle.LESEN)


class TestStartseiteUndWohnungen:
    def test_zeigt_nur_eigene_wohnungen(self, client, daten, fremd):
        inhalt = client.get("/").content.decode()
        assert "Testwohnung" in inhalt
        assert "Fremde Wohnung" not in inhalt

    def test_leer(self, client, ich):
        assert "noch keine Wohnung" in client.get("/").content.decode()

    def test_wohnung_anlegen_macht_mich_zum_verwalter(self, client, ich):
        antwort = client.post(
            reverse("wohnung_neu"), {"bezeichnung": "Neue Wohnung", "wohnflaeche": "68,25"}
        )
        w = Wohnung.objects.get(bezeichnung="Neue Wohnung")
        assert antwort.url == w.get_absolute_url()
        assert w.wohnflaeche == D("68.25")
        assert Mitgliedschaft.objects.get(wohnung=w, nutzer=ich).rolle == "verwalten"

    def test_abrechnungen_nach_jahr_absteigend(self, client, daten):
        for jahr in [2022, 2025, 2023]:
            fabrik.abrechnung(daten["wohnung"], jahr=jahr)
        inhalt = client.get(daten["wohnung"].get_absolute_url()).content.decode()
        positionen = [inhalt.index(f">{j}</a>") for j in [2025, 2024, 2023, 2022]]
        assert positionen == sorted(positionen)

    def test_uebersicht_zeigt_ergebnis(self, client, daten):
        inhalt = client.get(daten["wohnung"].get_absolute_url()).content.decode()
        assert euro("Nachzahlung 163,76 €") in inhalt

    def test_bearbeiten(self, client, daten):
        url = reverse("wohnung_bearbeiten", args=[daten["wohnung"].pk])
        client.post(url, {"bezeichnung": "Umbenannt", "wohnflaeche": "70"})
        daten["wohnung"].refresh_from_db()
        assert daten["wohnung"].bezeichnung == "Umbenannt"


class TestAbrechnung:
    def test_detail_zeigt_nachrechnung(self, client, daten):
        inhalt = client.get(daten["abrechnung"].get_absolute_url()).content.decode()
        assert euro("251,42 €") in inhalt  # gerundet wie Vermieter
        assert "251,6667" in inhalt  # exakte Rechnung
        assert euro("812,34 €") in inhalt
        assert euro("Nachzahlung 163,76 €") in inhalt
        assert "3,33 € je m²" in inhalt
        assert "01.01.2024 – 31.12.2024" in inhalt

    def test_guthaben(self, client, daten):
        fabrik.vorauszahlung(daten["abrechnung"], "300.00")
        inhalt = client.get(daten["abrechnung"].get_absolute_url()).content.decode()
        assert euro("Guthaben 136,24 €") in inhalt

    def test_unvollstaendig(self, client, daten):
        Abrechnungsbereich.objects.filter(pk=daten["bereich"].pk).update(gesamtmenge=None)
        inhalt = client.get(daten["abrechnung"].get_absolute_url()).content.decode()
        assert "unvollständig" in inhalt
        assert "Gesamtmenge fehlt" in inhalt

    def test_anlegen_mit_standardzeitraum(self, client, daten):
        url = reverse("abrechnung_neu", args=[daten["wohnung"].pk])
        antwort = client.post(url, {"abrechnungsjahr": "2025"})
        neu = Abrechnung.objects.get(wohnung=daten["wohnung"], abrechnungsjahr=2025)
        assert antwort.url == neu.get_absolute_url()
        assert neu.zeitraum_von == datetime.date(2025, 1, 1)
        assert neu.zeitraum_bis == datetime.date(2025, 12, 31)

    def test_zeitraum_rueckwaerts_wird_abgelehnt(self, client, daten):
        url = reverse("abrechnung_neu", args=[daten["wohnung"].pk])
        antwort = client.post(
            url,
            {"abrechnungsjahr": "2025", "zeitraum_von": "2025-12-31", "zeitraum_bis": "2025-01-01"},
        )
        assert antwort.status_code == 200
        assert "Ende des Zeitraums" in antwort.content.decode()

    def test_loeschen_mit_bestaetigung(self, client, daten):
        url = reverse("abrechnung_loeschen", args=[daten["abrechnung"].pk])
        assert "wirklich gelöscht" in client.get(url).content.decode()
        assert Abrechnung.objects.filter(pk=daten["abrechnung"].pk).exists()
        client.post(url)
        assert not Abrechnung.objects.filter(pk=daten["abrechnung"].pk).exists()


class TestBereich:
    def test_anlegen_mit_deutschen_zahlen(self, client, daten):
        url = reverse("bereich_neu", args=[daten["abrechnung"].pk])
        client.post(
            url,
            {
                "bezeichnung": "Wasser und Müll",
                "verteilerschluessel": "einheiten",
                "gesamtmenge": "1.234,5",
                "anteil_menge": "98,76",
                "rundungsregel": "n_stellen",
                "nachkommastellen": "3",
                "reihenfolge": "3",
            },
        )
        b = Abrechnungsbereich.objects.get(bezeichnung="Wasser und Müll")
        assert b.gesamtmenge == D("1234.5")
        assert b.anteil_menge == D("98.76")

    def test_vorbelegung_mit_wohnflaeche(self, client, daten):
        inhalt = client.get(reverse("bereich_neu", args=[daten["abrechnung"].pk])).content.decode()
        assert 'value="75,5' in inhalt

    def test_fehlende_mengen(self, client, daten):
        url = reverse("bereich_neu", args=[daten["abrechnung"].pk])
        antwort = client.post(
            url,
            {
                "bezeichnung": "X",
                "verteilerschluessel": "wohnflaeche",
                "rundungsregel": "exakt",
                "nachkommastellen": "2",
                "reihenfolge": "1",
            },
        )
        assert "Gesamtmenge nötig" in antwort.content.decode()

    def test_loeschen(self, client, daten):
        client.post(reverse("bereich_loeschen", args=[daten["heizung"].pk]))
        assert not Abrechnungsbereich.objects.filter(pk=daten["heizung"].pk).exists()


class TestKostenpositionenMitHtmx:
    def _url(self, daten):
        return reverse("position_neu", args=[daten["bereich"].pk])

    def _post(self, client, daten, kostenart, betrag, **header):
        prefix = f"b{daten['bereich'].pk}"
        return client.post(
            self._url(daten),
            {f"{prefix}-kostenart": kostenart.pk, f"{prefix}-betrag": betrag},
            headers=header,
        )

    def test_hinzufuegen_liefert_bereich_und_neues_ergebnis(self, client, daten):
        strassenreinigung = Kostenart.objects.get(name="Straßenreinigung")
        antwort = self._post(client, daten, strassenreinigung, "1.234,56", **HTMX)
        assert antwort.status_code == 200
        inhalt = antwort.content.decode()
        assert f'id="bereich-{daten["bereich"].pk}"' in inhalt
        assert 'hx-swap-oob="true"' in inhalt
        assert "<html" not in inhalt  # nur Teilstück
        assert euro("1.234,56 €") in inhalt
        pos = Kostenposition.objects.get(bereich=daten["bereich"], kostenart=strassenreinigung)
        assert pos.betrag == D("1234.56")
        # 2.234,56 / 300 = 7,4485… → 7,45 × 75,5 = 562,475 → 562,48
        assert euro("562,48 €") in inhalt

    def test_ohne_htmx_weiterleitung(self, client, daten):
        antwort = self._post(client, daten, Kostenart.objects.get(name="Gartenpflege"), "50")
        assert antwort.status_code == 302
        assert antwort.url.endswith(f"#bereich-{daten['bereich'].pk}")

    def test_doppelte_kostenart_wird_abgelehnt(self, client, daten):
        antwort = self._post(client, daten, Kostenart.objects.get(name="Grundsteuer"), "1", **HTMX)
        assert "gibt es in dem Bereich schon" in antwort.content.decode()
        assert daten["bereich"].positionen.count() == 2

    def test_fehler_ohne_htmx_zeigt_ganze_seite(self, client, daten):
        antwort = self._post(client, daten, Kostenart.objects.get(name="Grundsteuer"), "1")
        assert antwort.status_code == 200
        assert "<html" in antwort.content.decode()
        assert "gibt es in dem Bereich schon" in antwort.content.decode()

    def test_loeschen(self, client, daten):
        pos = daten["bereich"].positionen.first()
        antwort = client.post(reverse("position_loeschen", args=[pos.pk]), headers=HTMX)
        assert antwort.status_code == 200
        assert not Kostenposition.objects.filter(pk=pos.pk).exists()
        assert 'hx-swap-oob="true"' in antwort.content.decode()

    def test_loeschen_nur_per_post(self, client, daten):
        pos = daten["bereich"].positionen.first()
        assert client.get(reverse("position_loeschen", args=[pos.pk])).status_code == 405


class TestVorauszahlungenMitHtmx:
    def test_hinzufuegen(self, client, daten):
        url = reverse("vorauszahlung_neu", args=[daten["abrechnung"].pk])
        antwort = client.post(
            url,
            {
                "vz-bezeichnung": "Heizkosten",
                "vz-betrag": "250,00",
                "vz-bereich": daten["heizung"].pk,
            },
            headers=HTMX,
        )
        assert antwort.status_code == 200
        inhalt = antwort.content.decode()
        assert 'id="vorauszahlungen"' in inhalt and 'hx-swap-oob="true"' in inhalt
        assert euro("1.150,00 €") in inhalt
        assert Vorauszahlung.objects.get(bezeichnung="Heizkosten").bereich == daten["heizung"]

    def test_bereich_einer_fremden_abrechnung(self, client, daten, fremd):
        url = reverse("vorauszahlung_neu", args=[daten["abrechnung"].pk])
        client.post(
            url,
            {"vz-bezeichnung": "X", "vz-betrag": "1", "vz-bereich": fremd["bereich"].pk},
            headers=HTMX,
        )
        assert not Vorauszahlung.objects.filter(bezeichnung="X").exists()

    def test_loeschen(self, client, daten):
        url = reverse("vorauszahlung_loeschen", args=[daten["vz"].pk])
        client.post(url, headers=HTMX)
        assert not Vorauszahlung.objects.filter(pk=daten["vz"].pk).exists()


def _alle_urls(d):
    """(Name, URL, Methode, schreibend) für jede Ansicht mit fremden bzw. eigenen Daten."""
    return [
        ("wohnung_detail", reverse("wohnung_detail", args=[d["wohnung"].pk]), "get", False),
        ("wohnung_bearbeiten", reverse("wohnung_bearbeiten", args=[d["wohnung"].pk]), "get", True),
        ("abrechnung_neu", reverse("abrechnung_neu", args=[d["wohnung"].pk]), "get", True),
        (
            "abrechnung_detail",
            reverse("abrechnung_detail", args=[d["abrechnung"].pk]),
            "get",
            False,
        ),
        (
            "abrechnung_bearbeiten",
            reverse("abrechnung_bearbeiten", args=[d["abrechnung"].pk]),
            "get",
            True,
        ),
        (
            "abrechnung_loeschen",
            reverse("abrechnung_loeschen", args=[d["abrechnung"].pk]),
            "post",
            True,
        ),
        ("bereich_neu", reverse("bereich_neu", args=[d["abrechnung"].pk]), "get", True),
        ("bereich_bearbeiten", reverse("bereich_bearbeiten", args=[d["bereich"].pk]), "get", True),
        ("bereich_loeschen", reverse("bereich_loeschen", args=[d["bereich"].pk]), "post", True),
        ("position_neu", reverse("position_neu", args=[d["bereich"].pk]), "post", True),
        ("position_loeschen", reverse("position_loeschen", args=[d["position"].pk]), "post", True),
        (
            "vorauszahlung_neu",
            reverse("vorauszahlung_neu", args=[d["abrechnung"].pk]),
            "post",
            True,
        ),
        (
            "vorauszahlung_loeschen",
            reverse("vorauszahlung_loeschen", args=[d["vz"].pk]),
            "post",
            True,
        ),
    ]


class TestZugriffsschutz:
    def test_fremde_daten_ergeben_404(self, client, ich, fremd):
        for name, url, methode, _ in _alle_urls(fremd):
            antwort = getattr(client, methode)(url)
            assert antwort.status_code == 404, name
        assert Abrechnung.objects.filter(pk=fremd["abrechnung"].pk).exists()
        assert Kostenposition.objects.filter(pk=fremd["position"].pk).exists()

    def test_nur_lesen_darf_ansehen_aber_nicht_aendern(self, client, ich, fremd):
        nur_lesen(ich, fremd["wohnung"])
        for name, url, methode, schreibend in _alle_urls(fremd):
            antwort = getattr(client, methode)(url)
            assert antwort.status_code == (403 if schreibend else 200), name
        assert Kostenposition.objects.filter(pk=fremd["position"].pk).exists()

    def test_nur_lesen_sieht_keine_bearbeiten_knoepfe(self, client, ich, fremd):
        nur_lesen(ich, fremd["wohnung"])
        inhalt = client.get(fremd["abrechnung"].get_absolute_url()).content.decode()
        assert "Kosten hinzufügen" not in inhalt
        assert "Entfernen" not in inhalt
        assert reverse("abrechnung_bearbeiten", args=[fremd["abrechnung"].pk]) not in inhalt

    def test_ohne_anmeldung_zum_login(self, client, fremd):
        for name, url, methode, _ in [("start", "/", "get", False), *_alle_urls(fremd)]:
            antwort = getattr(client, methode)(url)
            assert antwort.status_code == 302, name
            assert antwort.url.startswith(reverse("account_login")), name

    def test_404_seite_ist_deutsch(self, client, ich):
        antwort = client.get(reverse("abrechnung_detail", args=[999999]))
        assert antwort.status_code == 404
        assert "Nicht gefunden" in antwort.content.decode()
