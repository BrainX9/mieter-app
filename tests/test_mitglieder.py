"""Mitglieder einer Wohnung: hinzufügen, Rolle ändern, entfernen, verlassen."""

import pytest
from django.urls import reverse

from mieter.abrechnungen.models import Mitgliedschaft
from tests import fabrik

pytestmark = pytest.mark.django_db
VERWALTEN = Mitgliedschaft.Rolle.VERWALTEN
LESEN = Mitgliedschaft.Rolle.LESEN
HTMX = {"HX-Request": "true"}


@pytest.fixture
def ich(client):
    n = fabrik.nutzer(email="ich@example.org")
    client.force_login(n)
    return n


@pytest.fixture
def wohnung(ich):
    return fabrik.wohnung(mitglied=ich)


def mitglied(wohnung, nutzer, rolle=LESEN):
    return Mitgliedschaft.objects.create(wohnung=wohnung, nutzer=nutzer, rolle=rolle)


def meine(wohnung, ich):
    return wohnung.mitgliedschaften.get(nutzer=ich)


def seite(client, wohnung):
    return client.get(reverse("wohnung_detail", args=[wohnung.pk])).content.decode()


class TestAnzeige:
    def test_liste_mit_rollen(self, client, wohnung):
        mitglied(wohnung, fabrik.nutzer(email="leserin@example.org"))
        inhalt = seite(client, wohnung)
        assert 'id="mitglieder"' in inhalt
        assert "leserin@example.org" in inhalt
        assert "(du)" in inhalt
        assert "Mitglied hinzufügen" in inhalt

    def test_nur_lesen_sieht_keine_knoepfe(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer(email="chefin@example.org"))
        mitglied(w, ich)
        inhalt = seite(client, w)
        assert "chefin@example.org" in inhalt
        assert "Mitglied hinzufügen" not in inhalt
        assert 'name="rolle"' not in inhalt
        assert "Wohnung verlassen" in inhalt

    def test_meldungsbereich_immer_da(self, client, wohnung):
        assert 'id="meldungen"' in seite(client, wohnung)


class TestHinzufuegen:
    def url(self, wohnung):
        return reverse("mitglied_neu", args=[wohnung.pk])

    def test_vorhandenes_konto(self, client, wohnung):
        anna = fabrik.nutzer(email="anna@example.org")
        client.post(self.url(wohnung), {"email": "Anna@Example.org", "rolle": LESEN})
        assert wohnung.mitgliedschaften.get(nutzer=anna).rolle == LESEN

    def test_unbekannte_adresse(self, client, wohnung):
        antwort = client.post(self.url(wohnung), {"email": "neu@example.org", "rolle": LESEN})
        assert antwort.status_code == 200
        assert "kein Konto" in antwort.content.decode()
        assert wohnung.mitgliedschaften.count() == 1

    def test_inaktives_konto(self, client, wohnung):
        fabrik.nutzer(email="weg@example.org", is_active=False)
        antwort = client.post(self.url(wohnung), {"email": "weg@example.org", "rolle": LESEN})
        assert "kein Konto" in antwort.content.decode()

    def test_schon_mitglied(self, client, wohnung, ich):
        antwort = client.post(self.url(wohnung), {"email": ich.email, "rolle": LESEN})
        assert "schon Mitglied" in antwort.content.decode()

    def test_htmx_bringt_meldung_mit(self, client, wohnung):
        fabrik.nutzer(email="anna@example.org")
        antwort = client.post(
            self.url(wohnung),
            {"email": "anna@example.org", "rolle": VERWALTEN},
            headers=HTMX,
            follow=True,
        )
        inhalt = antwort.content.decode()
        assert "anna@example.org ist jetzt Mitglied (Verwalten)." in inhalt
        assert 'hx-select-oob="#meldungen"' in inhalt


class TestRolle:
    def test_aendern(self, client, wohnung):
        m = mitglied(wohnung, fabrik.nutzer())
        client.post(reverse("mitglied_rolle", args=[m.pk]), {"rolle": VERWALTEN})
        m.refresh_from_db()
        assert m.rolle == VERWALTEN

    def test_letzter_verwalter_bleibt_verwalter(self, client, wohnung, ich):
        m = meine(wohnung, ich)
        antwort = client.post(reverse("mitglied_rolle", args=[m.pk]), {"rolle": LESEN}, follow=True)
        m.refresh_from_db()
        assert m.rolle == VERWALTEN
        assert "mindestens ein Mitglied" in antwort.content.decode()

    def test_selbst_herabstufen_wenn_es_noch_verwalter_gibt(self, client, wohnung, ich):
        mitglied(wohnung, fabrik.nutzer(), VERWALTEN)
        m = meine(wohnung, ich)
        client.post(reverse("mitglied_rolle", args=[m.pk]), {"rolle": LESEN})
        m.refresh_from_db()
        assert m.rolle == LESEN

    def test_unbekannte_rolle(self, client, wohnung):
        m = mitglied(wohnung, fabrik.nutzer())
        client.post(reverse("mitglied_rolle", args=[m.pk]), {"rolle": "chef"})
        m.refresh_from_db()
        assert m.rolle == LESEN


class TestEntfernen:
    def test_anderes_mitglied(self, client, wohnung):
        m = mitglied(wohnung, fabrik.nutzer())
        client.post(reverse("mitglied_entfernen", args=[m.pk]))
        assert not Mitgliedschaft.objects.filter(pk=m.pk).exists()

    def test_letzter_verwalter_nicht(self, client, wohnung, ich):
        m = meine(wohnung, ich)
        client.post(reverse("mitglied_entfernen", args=[m.pk]))
        assert Mitgliedschaft.objects.filter(pk=m.pk).exists()

    def test_sich_selbst_mit_weiterem_verwalter(self, client, wohnung, ich):
        mitglied(wohnung, fabrik.nutzer(), VERWALTEN)
        antwort = client.post(reverse("mitglied_entfernen", args=[meine(wohnung, ich).pk]))
        assert antwort.status_code == 302
        assert antwort.url == reverse("startseite")
        assert not wohnung.mitgliedschaften.filter(nutzer=ich).exists()

    def test_sich_selbst_per_htmx_leitet_um(self, client, wohnung, ich):
        mitglied(wohnung, fabrik.nutzer(), VERWALTEN)
        antwort = client.post(
            reverse("mitglied_entfernen", args=[meine(wohnung, ich).pk]), headers=HTMX
        )
        assert antwort["HX-Redirect"] == reverse("startseite")


class TestVerlassen:
    def test_leser_verlaesst(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer())
        mitglied(w, ich)
        antwort = client.post(reverse("wohnung_verlassen", args=[w.pk]), follow=True)
        assert not w.mitgliedschaften.filter(nutzer=ich).exists()
        assert f"Du hast „{w}“ verlassen." in antwort.content.decode()

    def test_letzter_verwalter_kann_nicht_verlassen(self, client, wohnung, ich):
        client.post(reverse("wohnung_verlassen", args=[wohnung.pk]))
        assert wohnung.mitgliedschaften.filter(nutzer=ich).exists()


class TestZugriff:
    def test_nur_lesen_darf_nichts_aendern(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer())
        mitglied(w, ich)
        andere = w.mitgliedschaften.exclude(nutzer=ich).get()
        fabrik.nutzer(email="anna@example.org")
        anfragen = [
            (reverse("mitglied_neu", args=[w.pk]), {"email": "anna@example.org", "rolle": LESEN}),
            (reverse("mitglied_rolle", args=[andere.pk]), {"rolle": LESEN}),
            (reverse("mitglied_rolle", args=[meine(w, ich).pk]), {"rolle": VERWALTEN}),
            (reverse("mitglied_entfernen", args=[andere.pk]), {}),
        ]
        for url, daten in anfragen:
            assert client.post(url, daten).status_code == 403, url
        assert meine(w, ich).rolle == LESEN
        assert w.mitgliedschaften.count() == 2

    def test_fremde_wohnung(self, client, ich):
        w = fabrik.wohnung(mitglied=fabrik.nutzer())
        fremd = w.mitgliedschaften.get()
        assert client.post(reverse("mitglied_entfernen", args=[fremd.pk])).status_code == 404
        assert client.post(reverse("wohnung_verlassen", args=[w.pk])).status_code == 404
        assert (
            client.post(reverse("mitglied_neu", args=[w.pk]), {"email": ich.email}).status_code
            == 404
        )
        assert Mitgliedschaft.objects.filter(pk=fremd.pk).exists()

    def test_nur_post(self, client, wohnung, ich):
        m = meine(wohnung, ich)
        assert client.get(reverse("mitglied_entfernen", args=[m.pk])).status_code == 405


class TestModell:
    def test_ist_letzter_verwalter(self, wohnung, ich):
        m = meine(wohnung, ich)
        assert m.ist_letzter_verwalter
        zweite = mitglied(wohnung, fabrik.nutzer(), VERWALTEN)
        assert not m.ist_letzter_verwalter
        leser = mitglied(wohnung, fabrik.nutzer())
        assert not leser.ist_letzter_verwalter
        zweite.delete()
        assert m.ist_letzter_verwalter
