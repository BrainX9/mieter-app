"""Datenmodell: Zugriff über Mitgliedschaft, Regeln, Sortierung, Kostenarten."""

import datetime
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from mieter.abrechnungen.models import (
    Abrechnung,
    Abrechnungsbereich,
    Kostenart,
    Kostenposition,
    Mitgliedschaft,
    Vorauszahlung,
    Wohnung,
    Zusatzfeld,
    Zusatzwert,
)
from tests import fabrik

pytestmark = pytest.mark.django_db


@pytest.fixture
def zwei_haushalte():
    """Zwei Nutzer mit je einer Wohnung und vollständigen Daten."""
    daten = {}
    for name in ["erika", "max"]:
        n = fabrik.nutzer(email=f"{name}@example.org")
        w = fabrik.wohnung(mitglied=n)
        a = fabrik.abrechnung(w)
        br = fabrik.bereich(a)
        fabrik.position(br, "100.00", "Grundsteuer")
        fabrik.vorauszahlung(a, "50.00")
        f = fabrik.zusatzfeld(w)
        fabrik.zusatzwert(a, f, wert_zahl=D("12.5"))
        daten[name] = {"nutzer": n, "wohnung": w, "abrechnung": a}
    return daten


ALLE_MODELLE = [
    Wohnung,
    Mitgliedschaft,
    Abrechnung,
    Abrechnungsbereich,
    Kostenposition,
    Vorauszahlung,
    Zusatzfeld,
    Zusatzwert,
]


class TestZugriffUeberMitgliedschaft:
    @pytest.mark.parametrize("modell", ALLE_MODELLE, ids=lambda m: m.__name__)
    def test_nutzer_sieht_nur_eigene_daten(self, zwei_haushalte, modell):
        erika = zwei_haushalte["erika"]
        eigene = modell.objects.fuer_nutzer(erika["nutzer"])
        alle = modell.objects.all()
        assert eigene.count() == alle.count() // 2
        assert eigene.count() >= 1
        for objekt in eigene:
            assert _wohnung_von(objekt) == erika["wohnung"]

    @pytest.mark.parametrize("modell", ALLE_MODELLE, ids=lambda m: m.__name__)
    def test_anonym_sieht_nichts(self, zwei_haushalte, modell):
        assert not modell.objects.fuer_nutzer(AnonymousUser()).exists()

    def test_gemeinsame_wohnung(self, zwei_haushalte):
        erika, max_ = zwei_haushalte["erika"], zwei_haushalte["max"]
        Mitgliedschaft.objects.create(
            nutzer=max_["nutzer"], wohnung=erika["wohnung"], rolle=Mitgliedschaft.Rolle.LESEN
        )
        assert Abrechnung.objects.fuer_nutzer(max_["nutzer"]).count() == 2

    def test_lesen_darf_nicht_verwalten(self, zwei_haushalte):
        erika, max_ = zwei_haushalte["erika"], zwei_haushalte["max"]
        Mitgliedschaft.objects.create(
            nutzer=max_["nutzer"], wohnung=erika["wohnung"], rolle=Mitgliedschaft.Rolle.LESEN
        )
        verwaltbar = Abrechnung.objects.verwaltbar_fuer(max_["nutzer"])
        assert list(verwaltbar) == [max_["abrechnung"]]
        assert Kostenposition.objects.verwaltbar_fuer(max_["nutzer"]).count() == 1
        assert not Abrechnung.objects.verwaltbar_fuer(AnonymousUser()).exists()

    def test_keine_doppelten_treffer(self, zwei_haushalte):
        erika = zwei_haushalte["erika"]
        weitere = fabrik.nutzer()
        Mitgliedschaft.objects.create(nutzer=weitere, wohnung=erika["wohnung"])
        assert Abrechnung.objects.fuer_nutzer(erika["nutzer"]).count() == 1


def _wohnung_von(objekt):
    pfad = type(objekt).WOHNUNG_PFAD
    if not pfad:
        return objekt
    for teil in pfad.split("__"):
        objekt = getattr(objekt, teil)
    return objekt


class TestAbrechnung:
    def test_sortierung_nach_jahr_absteigend(self):
        w = fabrik.wohnung()
        for jahr in [2022, 2024, 2023]:
            fabrik.abrechnung(w, jahr=jahr)
        assert [a.abrechnungsjahr for a in Abrechnung.objects.all()] == [2024, 2023, 2022]

    def test_zeitraum_ende_vor_beginn(self):
        w = fabrik.wohnung()
        a = Abrechnung(
            wohnung=w,
            abrechnungsjahr=2024,
            zeitraum_von=datetime.date(2024, 12, 31),
            zeitraum_bis=datetime.date(2024, 1, 1),
        )
        with pytest.raises(ValidationError, match="Ende des Zeitraums"):
            a.full_clean()
        with pytest.raises(IntegrityError), transaction.atomic():
            a.save()

    def test_berechnen_aus_gespeicherten_daten(self):
        a = fabrik.abrechnung(fabrik.wohnung())
        allgemein = fabrik.bereich(a)
        fabrik.position(allgemein, "400.00", "Grundsteuer")
        fabrik.position(allgemein, "600.00", "Gebäudeversicherung")
        heizung = fabrik.bereich(
            a,
            bezeichnung="Heizung",
            verteilerschluessel=Abrechnungsbereich.Verteilerschluessel.INDIVIDUELL,
            gesamtmenge=None,
            anteil_menge=None,
        )
        fabrik.position(heizung, "812.34", "Heizung und Warmwasser")
        fabrik.vorauszahlung(a, "900.00")

        ergebnis = a.berechnen()
        assert [e.anteil for e in ergebnis.bereiche] == [D("251.42"), D("812.34")]
        assert ergebnis.saldo == D("163.76")


class TestAbrechnungsbereich:
    def test_verteilung_braucht_mengen(self):
        a = fabrik.abrechnung(fabrik.wohnung())
        br = Abrechnungsbereich(abrechnung=a, bezeichnung="Test")
        with pytest.raises(ValidationError) as fehler:
            br.full_clean()
        assert set(fehler.value.message_dict) == {"gesamtmenge", "anteil_menge"}

    def test_individuell_braucht_keine_mengen(self):
        a = fabrik.abrechnung(fabrik.wohnung())
        Abrechnungsbereich(
            abrechnung=a,
            bezeichnung="Heizung",
            verteilerschluessel=Abrechnungsbereich.Verteilerschluessel.INDIVIDUELL,
        ).full_clean()

    def test_anteil_groesser_als_gesamt(self):
        a = fabrik.abrechnung(fabrik.wohnung())
        br = Abrechnungsbereich(
            abrechnung=a, bezeichnung="Test", gesamtmenge=D("10"), anteil_menge=D("11")
        )
        with pytest.raises(ValidationError, match="größer als die Gesamtmenge"):
            br.full_clean()

    @pytest.mark.parametrize(
        "felder",
        [{"gesamtmenge": D("0")}, {"anteil_menge": D("-1")}, {"nachkommastellen": 7}],
    )
    def test_datenbank_regeln(self, felder):
        a = fabrik.abrechnung(fabrik.wohnung())
        with pytest.raises(IntegrityError), transaction.atomic():
            fabrik.bereich(a, **felder)


class TestKostenarten:
    def test_startwerte_nach_betrkv(self):
        namen = set(Kostenart.objects.values_list("name", flat=True))
        assert {"Grundsteuer", "Müllbeseitigung", "Heizung und Warmwasser"} <= namen
        nummern = set(Kostenart.objects.values_list("betrkv_nummer", flat=True))
        assert set(range(1, 18)) <= nummern

    def test_neue_kostenart_ohne_migration(self):
        neu = Kostenart.objects.create(name="Rauchwarnmelder-Wartung")
        a = fabrik.abrechnung(fabrik.wohnung())
        p = Kostenposition.objects.create(
            bereich=fabrik.bereich(a), kostenart=neu, betrag=D("24.00")
        )
        assert p.kostenart.name == "Rauchwarnmelder-Wartung"

    def test_kostenart_doppelt_im_bereich(self):
        br = fabrik.bereich(fabrik.abrechnung(fabrik.wohnung()))
        fabrik.position(br, "1.00", "Grundsteuer")
        with pytest.raises(IntegrityError), transaction.atomic():
            fabrik.position(br, "2.00", "Grundsteuer")

    def test_benutzte_kostenart_nicht_loeschbar(self):
        from django.db.models import ProtectedError

        br = fabrik.bereich(fabrik.abrechnung(fabrik.wohnung()))
        p = fabrik.position(br, "1.00", "Grundsteuer")
        with pytest.raises(ProtectedError):
            p.kostenart.delete()


class TestVorauszahlungUndZusatzfelder:
    def test_vorauszahlung_bereich_aus_anderer_abrechnung(self):
        w = fabrik.wohnung()
        a1, a2 = fabrik.abrechnung(w, 2023), fabrik.abrechnung(w, 2024)
        v = Vorauszahlung(abrechnung=a1, bereich=fabrik.bereich(a2), bezeichnung="X", betrag=1)
        with pytest.raises(ValidationError, match="anderen Abrechnung"):
            v.full_clean()

    def test_zusatzwert_nach_typ(self):
        w = fabrik.wohnung()
        a = fabrik.abrechnung(w)
        zahl = fabrik.zusatzfeld(w, "Einheiten Küche", einheit="Einheiten")
        datum = fabrik.zusatzfeld(w, "Ablesedatum", typ=Zusatzfeld.Typ.DATUM)
        assert fabrik.zusatzwert(a, zahl, wert_zahl=D("41.3")).wert == D("41.3")
        tag = datetime.date(2024, 12, 31)
        assert fabrik.zusatzwert(a, datum, wert_datum=tag).wert == tag
        assert str(zahl) == "Einheiten Küche (Einheiten)"

    def test_zusatzwert_falscher_typ(self):
        w = fabrik.wohnung()
        feld = fabrik.zusatzfeld(w)
        wert = Zusatzwert(abrechnung=fabrik.abrechnung(w), feld=feld, wert_text="viel")
        with pytest.raises(ValidationError, match="erwartet den Typ Zahl"):
            wert.full_clean()

    def test_zusatzwert_feld_einer_anderen_wohnung(self):
        feld = fabrik.zusatzfeld(fabrik.wohnung())
        wert = Zusatzwert(
            abrechnung=fabrik.abrechnung(fabrik.wohnung()), feld=feld, wert_zahl=D("1")
        )
        with pytest.raises(ValidationError, match="anderen Wohnung"):
            wert.full_clean()

    def test_neues_zusatzfeld_ohne_migration(self):
        w = fabrik.wohnung()
        feld = Zusatzfeld.objects.create(wohnung=w, name="Zählerstand Wasser", einheit="m³")
        wert = fabrik.zusatzwert(fabrik.abrechnung(w), feld, wert_zahl=D("123.4"))
        assert wert.wert == D("123.4")


class TestAdmin:
    def test_mitarbeiter_sieht_nur_eigene_abrechnungen(self, zwei_haushalte, rf):
        from django.contrib.admin.sites import site

        erika = zwei_haushalte["erika"]["nutzer"]
        erika.is_staff = True
        erika.save()
        anfrage = rf.get("/admin/")
        anfrage.user = erika
        qs = site._registry[Abrechnung].get_queryset(anfrage)
        assert list(qs) == [zwei_haushalte["erika"]["abrechnung"]]

    def test_auswahlfelder_nur_eigene_wohnungen(self, zwei_haushalte, rf):
        from django.contrib.admin.sites import site

        erika = zwei_haushalte["erika"]["nutzer"]
        anfrage = rf.get("/admin/")
        anfrage.user = erika
        admin_klasse = site._registry[Abrechnung]
        feld = admin_klasse.formfield_for_foreignkey(Abrechnung._meta.get_field("wohnung"), anfrage)
        assert list(feld.queryset) == [zwei_haushalte["erika"]["wohnung"]]

    def test_superuser_sieht_alles(self, zwei_haushalte, rf):
        from django.contrib.admin.sites import site

        admin = fabrik.nutzer(is_staff=True, is_superuser=True)
        anfrage = rf.get("/admin/")
        anfrage.user = admin
        assert site._registry[Abrechnung].get_queryset(anfrage).count() == 2

    @pytest.mark.parametrize(
        "pfad",
        [
            "/admin/abrechnungen/wohnung/",
            "/admin/abrechnungen/abrechnung/",
            "/admin/abrechnungen/abrechnungsbereich/",
            "/admin/abrechnungen/kostenart/",
        ],
    )
    def test_admin_seiten_laden(self, client, zwei_haushalte, pfad):
        client.force_login(fabrik.nutzer(is_staff=True, is_superuser=True))
        assert client.get(pfad).status_code == 200
