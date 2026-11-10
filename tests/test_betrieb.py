"""Betrieb im Container: Statusseite und Einstellungen hinter dem Reverse Proxy."""

import os
import runpy
import subprocess
from pathlib import Path

import pytest
from django.db import OperationalError
from django.urls import reverse

WURZEL = Path(__file__).resolve().parent.parent
EINSTELLUNGEN = WURZEL / "mieter" / "settings.py"


def einstellungen(monkeypatch, **werte):
    """Lädt settings.py neu mit den angegebenen Umgebungsvariablen (ohne lokale .env)."""
    monkeypatch.setattr("environ.Env.read_env", lambda *a, **k: None)
    for name in ("DEBUG", "HTTPS", "HSTS_SEKUNDEN", "ALLOWED_HOSTS", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SECRET_KEY", "test")
    monkeypatch.setenv("DATABASE_URL", "postgres://test@localhost/test")
    for name, wert in werte.items():
        monkeypatch.setenv(name, wert)
    return runpy.run_path(str(EINSTELLUNGEN))


class TestGesund:
    @pytest.mark.django_db
    def test_ohne_anmeldung(self, client):
        antwort = client.get(reverse("gesund"))
        assert antwort.status_code == 200
        assert antwort.content == b"ok"
        assert "no-cache" in antwort["Cache-Control"]

    def test_datenbank_weg(self, client, monkeypatch):
        def kaputt():
            raise OperationalError("weg")

        monkeypatch.setattr("mieter.kern.views.connection.cursor", kaputt)
        antwort = client.get(reverse("gesund"))
        assert antwort.status_code == 503

    @pytest.mark.django_db
    def test_nur_get(self, client):
        assert client.post(reverse("gesund")).status_code == 405

    @pytest.mark.django_db
    def test_https_hinter_proxy(self, client, settings):
        settings.ALLOWED_HOSTS = ["mieter.example.org", "localhost"]
        antwort = client.get(
            reverse("gesund"),
            headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "mieter.example.org"},
        )
        assert antwort.status_code == 200
        assert antwort.wsgi_request.is_secure()
        assert antwort.wsgi_request.get_host() == "mieter.example.org"


class TestEinstellungen:
    def test_betrieb_ist_sicher(self, monkeypatch):
        s = einstellungen(monkeypatch, ALLOWED_HOSTS="mieter.example.org")
        assert s["DEBUG"] is False
        assert s["SESSION_COOKIE_SECURE"] is True
        assert s["CSRF_COOKIE_SECURE"] is True
        assert s["SECURE_HSTS_SECONDS"] == 0
        assert s["ALLOWED_HOSTS"] == ["mieter.example.org", "localhost", "127.0.0.1"]

    def test_hsts(self, monkeypatch):
        s = einstellungen(monkeypatch, HSTS_SEKUNDEN="31536000")
        assert s["SECURE_HSTS_SECONDS"] == 31536000

    def test_heimnetz_ohne_https(self, monkeypatch):
        s = einstellungen(monkeypatch, HTTPS="False", HSTS_SEKUNDEN="31536000")
        assert s["SESSION_COOKIE_SECURE"] is False
        assert s["SECURE_HSTS_SECONDS"] == 0

    def test_entwicklung(self, monkeypatch):
        s = einstellungen(monkeypatch, DEBUG="True", ALLOWED_HOSTS="localhost")
        assert s["SESSION_COOKIE_SECURE"] is False
        assert s["ALLOWED_HOSTS"] == ["localhost", "127.0.0.1"]

    def test_whitenoise_direkt_nach_security(self, monkeypatch):
        s = einstellungen(monkeypatch)
        mw = s["MIDDLEWARE"]
        assert mw.index("whitenoise.middleware.WhiteNoiseMiddleware") == 1
        assert "Manifest" in s["STORAGES"]["staticfiles"]["BACKEND"]

    def test_log_level(self, monkeypatch):
        s = einstellungen(monkeypatch, LOG_LEVEL="WARNING")
        assert s["LOGGING"]["root"]["level"] == "WARNING"


class TestImage:
    def test_dockerignore_haelt_geheimes_fern(self):
        regeln = (WURZEL / ".dockerignore").read_text().split()
        for muster in (".env", ".env.*", "daten/", "backup/", "media/", ".git/"):
            assert muster in regeln

    def test_startskript_ausfuehrbar(self):
        assert os.access(WURZEL / "docker" / "start.sh", os.X_OK)

    def test_startskript_syntax(self):
        subprocess.run(["sh", "-n", str(WURZEL / "docker" / "start.sh")], check=True)
