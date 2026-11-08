"""Grundlegende Prüfungen der Projektkonfiguration."""

import pytest
from django.conf import settings
from django.db import connection


def test_sprache_ist_deutsch():
    assert settings.LANGUAGE_CODE == "de-de"


def test_zeitzone_ist_berlin():
    assert settings.TIME_ZONE == "Europe/Berlin"
    assert settings.USE_TZ is True


@pytest.mark.django_db
def test_datenbank_ist_postgresql():
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        (version,) = cursor.fetchone()
    assert int(version) >= 170000


@pytest.mark.django_db
def test_admin_anmeldung_ist_deutsch(client):
    antwort = client.get("/admin/login/")
    assert antwort.status_code == 200
    assert "Anmelden" in antwort.content.decode()
