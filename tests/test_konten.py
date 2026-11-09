"""Nutzermodell und Anmeldung."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.urls import reverse

OIDC_KONFIGURATION = {
    "openid_connect": {
        "APPS": [
            {
                "provider_id": "synology",
                "name": "Synology SSO",
                "client_id": "test-client",
                "secret": "test-secret",
                "settings": {"server_url": "https://sso.example.org/webman/sso"},
            }
        ]
    }
}


@pytest.mark.django_db
class TestNutzermodell:
    def test_anmeldung_ueber_email_statt_benutzername(self):
        Nutzer = get_user_model()
        assert Nutzer.USERNAME_FIELD == "email"
        with pytest.raises(FieldDoesNotExist):
            Nutzer._meta.get_field("username")

    def test_email_wird_normalisiert(self):
        n = get_user_model().objects.create_user(email="Max@EXAMPLE.org", password="x")
        assert n.email == "Max@example.org"
        assert str(n) == "Max@example.org"

    def test_email_ist_pflicht(self):
        with pytest.raises(ValueError, match="E-Mail-Adresse"):
            get_user_model().objects.create_user(email="", password="x")

    def test_superuser(self):
        n = get_user_model().objects.create_superuser(email="admin@example.org", password="x")
        assert n.is_staff and n.is_superuser


@pytest.mark.django_db
class TestZugriff:
    def test_startseite_leitet_ohne_anmeldung_zum_login(self, client):
        antwort = client.get("/")
        assert antwort.status_code == 302
        assert antwort.url.startswith(reverse("account_login"))

    def test_login_seite_ohne_anmeldung_erreichbar(self, client):
        antwort = client.get(reverse("account_login"))
        assert antwort.status_code == 200
        assert "Anmelden" in antwort.content.decode()

    def test_anmeldung_mit_email_und_passwort(self, client, nutzer):
        antwort = client.post(
            reverse("account_login"),
            {"login": "erika@example.org", "password": "geheim-123"},
        )
        assert antwort.status_code == 302
        assert antwort.url == reverse("startseite")
        assert client.get("/").status_code == 200

    def test_falsches_passwort_wird_abgelehnt(self, client, nutzer):
        antwort = client.post(
            reverse("account_login"),
            {"login": "erika@example.org", "password": "falsch"},
        )
        assert antwort.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_abmelden_per_post(self, client, nutzer):
        client.force_login(nutzer)
        antwort = client.post(reverse("account_logout"))
        assert antwort.status_code == 302
        assert client.get("/").status_code == 302


@pytest.mark.django_db
class TestRegistrierung:
    def test_standardmaessig_geschlossen(self, client, settings):
        settings.REGISTRIERUNG_OFFEN = False
        antwort = client.get(reverse("account_signup"))
        assert "Registrierung geschlossen" in antwort.content.decode()

    def test_kein_registrieren_link_wenn_geschlossen(self, client, settings):
        settings.REGISTRIERUNG_OFFEN = False
        inhalt = client.get(reverse("account_login")).content.decode()
        assert reverse("account_signup") not in inhalt

    def test_standardwert_der_umgebungsvariable_ist_geschlossen(self):
        from mieter import settings as einstellungen

        assert einstellungen.env.scheme["REGISTRIERUNG_OFFEN"] == (bool, False)

    def test_offen_zeigt_formular_und_link(self, client, settings):
        settings.REGISTRIERUNG_OFFEN = True
        assert reverse("account_signup") in client.get(reverse("account_login")).content.decode()
        antwort = client.get(reverse("account_signup"))
        assert "Registrierung geschlossen" not in antwort.content.decode()
        assert 'name="email"' in antwort.content.decode()


@pytest.mark.django_db
class TestOidc:
    def test_ohne_konfiguration_kein_sso_knopf(self, client, settings):
        settings.SOCIALACCOUNT_PROVIDERS = {}
        inhalt = client.get(reverse("account_login")).content.decode()
        assert "Anmelden mit" not in inhalt

    def test_mit_konfiguration_sso_knopf(self, client, settings):
        settings.SOCIALACCOUNT_PROVIDERS = OIDC_KONFIGURATION
        inhalt = client.get(reverse("account_login")).content.decode()
        assert "Anmelden mit Synology SSO" in inhalt
        assert "/konto/oidc/synology/login/" in inhalt

    def test_callback_url_fuer_synology(self):
        assert (
            reverse("openid_connect_callback", kwargs={"provider_id": "synology"})
            == "/konto/oidc/synology/login/callback/"
        )

    def test_oidc_registrierung_folgt_einstellung(self, rf, settings):
        from allauth.socialaccount.adapter import get_adapter

        settings.REGISTRIERUNG_OFFEN = False
        assert get_adapter().is_open_for_signup(rf.get("/"), sociallogin=None) is False
        settings.REGISTRIERUNG_OFFEN = True
        assert get_adapter().is_open_for_signup(rf.get("/"), sociallogin=None) is True
