"""Zusatzfelder je Wohnung und Zusatzwerte je Abrechnung in der Oberfläche."""

import datetime
from decimal import Decimal as D

import pytest
from django.urls import reverse

from mieter.abrechnungen.models import Mitgliedschaft, Zusatzfeld, Zusatzwert
from tests import fabrik

pytestmark = pytest.mark.django_db
ZAHL, TEXT, DATUM = Zusatzfeld.Typ.ZAHL, Zusatzfeld.Typ.TEXT, Zusatzfeld.Typ.DATUM
HTMX = {"HX-Request": "true"}


@pytest.fixture
def ich(client):
    n = fabrik.nutzer()
    client.force_login(n)
    return n


@pytest.fixture
def wohnung(ich):
    return fabrik.wohnung(mitglied=ich)


@pytest.fixture
def abrechnung(wohnung):
    return fabrik.abrechnung(wohnung)


@pytest.fixture
def felder(wohnung):
    return {
        "zahl": fabrik.zusatzfeld(wohnung, "Einheiten Wohnzimmer", ZAHL, "Einheiten"),
        "text": fabrik.zusatzfeld(wohnung, "Bemerkung", TEXT),
        "datum": fabrik.zusatzfeld(wohnung, "Ablesedatum", DATUM),
    }


def nur_lesen(ich):
    w = fabrik.wohnung(mitglied=fabrik.nutzer())
    Mitgliedschaft.objects.create(nutzer=ich, wohnung=w, rolle=Mitgliedschaft.Rolle.LESEN)
    return w


class TestFelderAnlegen:
    def url(self, wohnung):
        return reverse("zusatzfeld_neu", args=[wohnung.pk])

    def test_anlegen(self, client, wohnung):
        antwort = client.post(
            self.url(wohnung),
            {"name": "Einheiten Bad", "typ": ZAHL, "einheit": "Einheiten", "reihenfolge": "1"},
            follow=True,
        )
        feld = wohnung.zusatzfelder.get()
        assert (feld.name, feld.typ, feld.einheit) == ("Einheiten Bad", ZAHL, "Einheiten")
        assert "Zusatzfeld „Einheiten Bad“ angelegt." in antwort.content.decode()

    def test_name_doppelt(self, client, wohnung, felder):
        antwort = client.post(
            self.url(wohnung), {"name": "einheiten wohnzimmer", "typ": ZAHL, "reihenfolge": "0"}
        )
        assert antwort.status_code == 200
        assert "gibt es schon" in antwort.content.decode()
        assert wohnung.zusatzfelder.count() == 3

    def test_gleicher_name_in_anderer_wohnung(self, client, ich, wohnung, felder):
        andere = fabrik.wohnung(mitglied=ich)
        client.post(self.url(andere), {"name": "Bemerkung", "typ": TEXT, "reihenfolge": "0"})
        assert andere.zusatzfelder.filter(name="Bemerkung").exists()

    def test_htmx(self, client, wohnung):
        antwort = client.post(
            self.url(wohnung),
            {"name": "Zählerstand", "typ": ZAHL, "reihenfolge": "1"},
            headers=HTMX,
            follow=True,
        )
        assert 'hx-select="#zusatzfelder"' in antwort.content.decode()

    def test_liste_auf_der_wohnungsseite(self, client, wohnung, felder, abrechnung):
        fabrik.zusatzwert(abrechnung, felder["zahl"], wert_zahl=D("12"))
        inhalt = client.get(reverse("wohnung_detail", args=[wohnung.pk])).content.decode()
        assert 'id="zusatzfelder"' in inhalt
        assert "Einheiten Wohnzimmer" in inhalt
        assert "Zusatzfeld hinzufügen" in inhalt


class TestFelderBearbeitenUndLoeschen:
    def test_bearbeiten(self, client, felder):
        feld = felder["zahl"]
        client.post(
            reverse("zusatzfeld_bearbeiten", args=[feld.pk]),
            {"name": "Einheiten Wohnraum", "typ": ZAHL, "einheit": "", "reihenfolge": "5"},
        )
        feld.refresh_from_db()
        assert (feld.name, feld.einheit, feld.reihenfolge) == ("Einheiten Wohnraum", "", 5)

    def test_typ_ohne_werte_aenderbar(self, client, felder):
        feld = felder["text"]
        client.post(
            reverse("zusatzfeld_bearbeiten", args=[feld.pk]),
            {"name": feld.name, "typ": ZAHL, "reihenfolge": "0"},
        )
        feld.refresh_from_db()
        assert feld.typ == ZAHL

    def test_typ_mit_werten_fest(self, client, felder, abrechnung):
        feld = felder["text"]
        fabrik.zusatzwert(abrechnung, feld, wert_text="Zähler getauscht")
        url = reverse("zusatzfeld_bearbeiten", args=[feld.pk])
        assert "der Typ bleibt deshalb fest" in client.get(url).content.decode()
        client.post(url, {"name": "Notiz", "typ": ZAHL, "reihenfolge": "0"})
        feld.refresh_from_db()
        assert feld.typ == TEXT
        assert feld.name == "Notiz"

    def test_loeschen_nennt_verlorene_werte(self, client, felder, abrechnung):
        feld = felder["zahl"]
        fabrik.zusatzwert(abrechnung, feld, wert_zahl=D("1"))
        fabrik.zusatzwert(fabrik.abrechnung(feld.wohnung, jahr=2023), feld, wert_zahl=D("2"))
        url = reverse("zusatzfeld_loeschen", args=[feld.pk])
        assert "Dabei gehen 2 eingetragene Werte verloren." in client.get(url).content.decode()
        client.post(url)
        assert not Zusatzfeld.objects.filter(pk=feld.pk).exists()
        assert not Zusatzwert.objects.exists()

    def test_loeschen_ohne_werte(self, client, felder):
        url = reverse("zusatzfeld_loeschen", args=[felder["datum"].pk])
        assert "verloren.</strong>" not in client.get(url).content.decode()


class TestWerte:
    def url(self, abrechnung):
        return reverse("zusatzwerte_speichern", args=[abrechnung.pk])

    def daten(self, felder, zahl="", text="", datum=""):
        return {
            f"feld_{felder['zahl'].pk}": zahl,
            f"feld_{felder['text'].pk}": text,
            f"feld_{felder['datum'].pk}": datum,
        }

    def werte(self, abrechnung):
        return {w.feld.name: w.wert for w in abrechnung.zusatzwerte.select_related("feld")}

    def test_speichern_nach_typ(self, client, abrechnung, felder):
        client.post(
            self.url(abrechnung),
            self.daten(felder, zahl="1.234,5", text="Zähler getauscht", datum="2024-12-31"),
        )
        assert self.werte(abrechnung) == {
            "Einheiten Wohnzimmer": D("1234.5"),
            "Bemerkung": "Zähler getauscht",
            "Ablesedatum": datetime.date(2024, 12, 31),
        }

    def test_aendern_und_leeren(self, client, abrechnung, felder):
        fabrik.zusatzwert(abrechnung, felder["zahl"], wert_zahl=D("10"))
        fabrik.zusatzwert(abrechnung, felder["text"], wert_text="alt")
        client.post(self.url(abrechnung), self.daten(felder, zahl="12,75"))
        assert self.werte(abrechnung) == {"Einheiten Wohnzimmer": D("12.75")}

    def test_ungueltige_zahl(self, client, abrechnung, felder):
        antwort = client.post(self.url(abrechnung), self.daten(felder, zahl="zwölf"))
        assert antwort.status_code == 200
        assert "Zahl" in antwort.content.decode()
        assert not abrechnung.zusatzwerte.exists()

    def test_formular_zeigt_vorhandene_werte(self, client, abrechnung, felder):
        fabrik.zusatzwert(abrechnung, felder["zahl"], wert_zahl=D("142.5000"))
        fabrik.zusatzwert(abrechnung, felder["datum"], wert_datum=datetime.date(2024, 1, 15))
        inhalt = client.get(reverse("abrechnung_detail", args=[abrechnung.pk])).content.decode()
        assert 'value="142,5"' in inhalt
        assert 'value="2024-01-15"' in inhalt
        assert "Einheiten Wohnzimmer (Einheiten)" in inhalt

    def test_htmx_mit_meldung(self, client, abrechnung, felder):
        antwort = client.post(
            self.url(abrechnung), self.daten(felder, text="x"), headers=HTMX, follow=True
        )
        inhalt = antwort.content.decode()
        assert "Zusatzwerte gespeichert." in inhalt
        assert 'hx-select="#zusatzwerte"' in inhalt

    def test_ohne_felder_hinweis(self, client, abrechnung):
        inhalt = client.get(reverse("abrechnung_detail", args=[abrechnung.pk])).content.decode()
        assert "noch keine Zusatzfelder" in inhalt

    def test_felder_anderer_wohnungen_werden_ignoriert(self, client, ich, abrechnung, felder):
        fremd = fabrik.zusatzfeld(fabrik.wohnung(mitglied=fabrik.nutzer()), "Fremd")
        daten = self.daten(felder, text="ok") | {f"feld_{fremd.pk}": "5"}
        client.post(self.url(abrechnung), daten)
        assert not Zusatzwert.objects.filter(feld=fremd).exists()
        assert self.werte(abrechnung) == {"Bemerkung": "ok"}


class TestZugriff:
    def test_nur_lesen_sieht_werte_ohne_formular(self, client, ich):
        w = nur_lesen(ich)
        a = fabrik.abrechnung(w)
        feld = fabrik.zusatzfeld(w, "Einheiten Bad", ZAHL, "Einheiten")
        fabrik.zusatzwert(a, feld, wert_zahl=D("65.5"))
        inhalt = client.get(reverse("abrechnung_detail", args=[a.pk])).content.decode()
        assert "65,5 Einheiten" in inhalt
        assert "Zusatzwerte speichern" not in inhalt
        inhalt = client.get(reverse("wohnung_detail", args=[w.pk])).content.decode()
        assert "Einheiten Bad" in inhalt
        assert "Zusatzfeld hinzufügen" not in inhalt

    def test_nur_lesen_darf_nichts_aendern(self, client, ich):
        w = nur_lesen(ich)
        a = fabrik.abrechnung(w)
        feld = fabrik.zusatzfeld(w)
        anfragen = [
            ("post", reverse("zusatzfeld_neu", args=[w.pk]), {"name": "X", "typ": ZAHL}),
            ("get", reverse("zusatzfeld_bearbeiten", args=[feld.pk]), {}),
            ("post", reverse("zusatzfeld_loeschen", args=[feld.pk]), {}),
            ("post", reverse("zusatzwerte_speichern", args=[a.pk]), {f"feld_{feld.pk}": "1"}),
        ]
        for methode, url, daten in anfragen:
            assert getattr(client, methode)(url, daten).status_code == 403, url
        assert Zusatzfeld.objects.filter(pk=feld.pk).exists()
        assert not Zusatzwert.objects.exists()

    def test_fremde_wohnung(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer())
        feld = fabrik.zusatzfeld(w)
        a = fabrik.abrechnung(w)
        assert client.get(reverse("zusatzfeld_bearbeiten", args=[feld.pk])).status_code == 404
        assert client.post(reverse("zusatzfeld_loeschen", args=[feld.pk])).status_code == 404
        assert client.post(reverse("zusatzwerte_speichern", args=[a.pk])).status_code == 404
        assert Zusatzfeld.objects.filter(pk=feld.pk).exists()
