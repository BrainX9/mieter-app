"""Kostenarten-Katalog: passende Verteilerschlüssel, Hinweise und Auswahl im Bereich."""

import importlib

import pytest
from django.apps import apps
from django.urls import reverse

from mieter.abrechnungen import berechnung
from mieter.abrechnungen.forms import KostenpositionForm
from mieter.abrechnungen.models import (
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Verteilerschluessel,
)
from tests import fabrik

pytestmark = pytest.mark.django_db
V = Verteilerschluessel
migration = importlib.import_module(
    "mieter.abrechnungen.migrations.0004_kostenarten_schluessel_hinweise"
)


def auswahl(bereich):
    form = KostenpositionForm(instance=Kostenposition(bereich=bereich))
    return set(form.fields["kostenart"].queryset.values_list("name", flat=True))


@pytest.fixture
def abrechnung():
    return fabrik.abrechnung(fabrik.wohnung(mitglied=fabrik.nutzer()))


class TestKatalog:
    def test_jede_startkostenart_hat_schluessel_und_hinweis(self):
        for name in migration.KATALOG:
            k = Kostenart.objects.get(name=name)
            assert k.verteilerschluessel, name
            assert k.hinweis, name
            assert set(k.verteilerschluessel) <= set(V.values), name

    @pytest.mark.parametrize(
        ("name", "schluessel"),
        [
            ("Grundsteuer", [V.WOHNFLAECHE]),
            ("Gebäudeversicherung", [V.WOHNFLAECHE]),
            ("Wasserversorgung", [V.PERSONEN_PUNKTE, V.INDIVIDUELL]),
            ("Heizung und Warmwasser", [V.INDIVIDUELL]),
            ("Antenne / Breitbandnetz", [V.WOHNEINHEITEN]),
        ],
    )
    def test_zuordnung(self, name, schluessel):
        assert Kostenart.objects.get(name=name).verteilerschluessel == schluessel

    def test_vier_verteilerschluessel(self):
        assert V.labels == [
            "Umlage nach Fläche (m²)",
            "Umlage pro Wohnung",
            "Umlage nach Personen / Punkten",
            "Umlage individuell",
        ]

    def test_berechnung_kennt_individuell_und_einheiten(self):
        assert berechnung.INDIVIDUELL == V.INDIVIDUELL
        assert set(berechnung.MENGENEINHEITEN) == set(V.values) - {V.INDIVIDUELL}


class TestPassendZu:
    def test_filtert_nach_schluessel(self):
        namen = set(Kostenart.objects.passend_zu(V.INDIVIDUELL).values_list("name", flat=True))
        assert "Heizung und Warmwasser" in namen
        assert "Wasserversorgung" in namen
        assert "Grundsteuer" not in namen

    def test_ohne_schluessel_passt_ueberall(self):
        k = fabrik.kostenart("Eigene Kostenart")
        assert k.verteilerschluessel == []
        for schluessel in V.values:
            assert Kostenart.objects.passend_zu(schluessel).filter(pk=k.pk).exists()


class TestAuswahlImBereich:
    def test_flaeche(self, abrechnung):
        namen = auswahl(fabrik.bereich(abrechnung))
        assert {"Grundsteuer", "Gartenpflege"} <= namen
        assert "Heizung und Warmwasser" not in namen

    def test_individuell(self, abrechnung):
        bereich = fabrik.bereich(
            abrechnung,
            verteilerschluessel=V.INDIVIDUELL,
            gesamtmenge=None,
            anteil_menge=None,
        )
        namen = auswahl(bereich)
        assert {"Heizung", "Warmwasser", "Heizung und Warmwasser"} <= namen
        assert "Grundsteuer" not in namen

    def test_inaktive_fehlen(self, abrechnung):
        Kostenart.objects.filter(name="Grundsteuer").update(aktiv=False)
        assert "Grundsteuer" not in auswahl(fabrik.bereich(abrechnung))

    def test_unpassende_kostenart_wird_abgelehnt(self, client):
        ich = fabrik.nutzer()
        client.force_login(ich)
        a = fabrik.abrechnung(fabrik.wohnung(mitglied=ich))
        bereich = fabrik.bereich(a)
        heizung = Kostenart.objects.get(name="Heizung und Warmwasser")
        p = f"b{bereich.pk}"
        antwort = client.post(
            reverse("position_neu", args=[bereich.pk]),
            {f"{p}-kostenart": heizung.pk, f"{p}-betrag": "100,00"},
        )
        assert antwort.status_code == 200
        assert "gültige Auswahl" in antwort.content.decode()
        assert not bereich.positionen.exists()

    def test_hinweis_wird_angezeigt(self, client):
        ich = fabrik.nutzer()
        client.force_login(ich)
        a = fabrik.abrechnung(fabrik.wohnung(mitglied=ich))
        fabrik.position(fabrik.bereich(a), "400.00", "Grundsteuer")
        inhalt = client.get(reverse("abrechnung_detail", args=[a.pk])).content.decode()
        assert "Laufende öffentliche Lasten des Grundstücks" in inhalt


class TestMigration:
    def test_alte_schluessel_werden_umgestellt(self, abrechnung):
        alt = {
            "einheiten": V.PERSONEN_PUNKTE,
            "personen": V.PERSONEN_PUNKTE,
            "direkt": V.INDIVIDUELL,
            "wohnflaeche": V.WOHNFLAECHE,
        }
        bereiche = {
            schluessel: fabrik.bereich(abrechnung, verteilerschluessel=schluessel)
            for schluessel in alt
        }
        migration.vorwaerts(apps, None)
        for schluessel, neu in alt.items():
            bereiche[schluessel].refresh_from_db()
            assert bereiche[schluessel].verteilerschluessel == neu

    def test_gepflegte_kostenarten_bleiben(self):
        k = Kostenart.objects.get(name="Grundsteuer")
        k.verteilerschluessel = [V.WOHNEINHEITEN]
        k.hinweis = "Eigener Hinweis"
        k.save()
        migration.vorwaerts(apps, None)
        k.refresh_from_db()
        assert k.verteilerschluessel == [V.WOHNEINHEITEN]
        assert k.hinweis == "Eigener Hinweis"

    def test_rueckwaerts(self, abrechnung):
        b = fabrik.bereich(abrechnung, verteilerschluessel=V.INDIVIDUELL)
        migration.rueckwaerts(apps, None)
        b.refresh_from_db()
        assert b.verteilerschluessel == "direkt"


class TestAdmin:
    @pytest.fixture
    def admin_client(self, client):
        from django.contrib.auth import get_user_model

        chef = get_user_model().objects.create_superuser(email="chef@example.org", password="x")
        client.force_login(chef)
        return client

    def test_schluessel_als_ankreuzfelder(self, admin_client):
        k = Kostenart.objects.get(name="Grundsteuer")
        inhalt = admin_client.get(
            reverse("admin:abrechnungen_kostenart_change", args=[k.pk])
        ).content.decode()
        assert 'type="checkbox" name="verteilerschluessel" value="wohnflaeche"' in inhalt

    def test_speichern(self, admin_client):
        antwort = admin_client.post(
            reverse("admin:abrechnungen_kostenart_add"),
            {
                "name": "Dachrinnenreinigung",
                "verteilerschluessel": [V.WOHNFLAECHE, V.WOHNEINHEITEN],
                "hinweis": "Nur wenn regelmäßig.",
                "aktiv": "on",
            },
        )
        assert antwort.status_code == 302
        k = Kostenart.objects.get(name="Dachrinnenreinigung")
        assert k.verteilerschluessel == [V.WOHNFLAECHE, V.WOHNEINHEITEN]

    def test_liste_zeigt_schluessel(self, admin_client):
        inhalt = admin_client.get(reverse("admin:abrechnungen_kostenart_changelist")).content
        assert "Umlage individuell" in inhalt.decode()


def test_bereich_alias():
    assert Abrechnungsbereich.Verteilerschluessel is Verteilerschluessel
