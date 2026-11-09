"""Grundlayout, HTMX und statische Dateien."""

import pytest
from django.contrib.staticfiles import finders


@pytest.mark.django_db
def test_layout_bindet_htmx_und_pico_ein(client, nutzer):
    client.force_login(nutzer)
    inhalt = client.get("/").content.decode()
    assert '<html lang="de">' in inhalt
    assert "vendor/htmx-2.0.11.min.js" in inhalt
    assert "vendor/pico-2.1.1.min.css" in inhalt
    assert "X-CSRFToken" in inhalt
    assert "Abmelden" in inhalt


def test_statische_dateien_liegen_im_projekt():
    for pfad in ["vendor/htmx-2.0.11.min.js", "vendor/pico-2.1.1.min.css", "mieter.css"]:
        assert finders.find(pfad), pfad


@pytest.mark.django_db
def test_htmx_middleware_erkennt_htmx_anfragen(client, nutzer):
    from django.test import RequestFactory
    from django_htmx.middleware import HtmxMiddleware

    anfrage = RequestFactory().get("/", headers={"HX-Request": "true"})
    HtmxMiddleware(lambda r: None)(anfrage)
    assert anfrage.htmx
