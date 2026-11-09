"""Hintergrundaufgaben mit Procrastinate."""

import datetime

import pytest
from django.core.management import call_command
from procrastinate import testing, utils
from procrastinate.contrib.django import app

from mieter.jobs import tasks


@pytest.fixture
def warteschlange():
    """Ersetzt PostgreSQL durch eine Warteschlange im Speicher."""
    connector = testing.InMemoryConnector()
    with app.replace_connector(connector) as test_app:
        yield test_app, connector


def _worker_laufen_lassen(test_app):
    test_app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)


def test_aufgabe_ist_registriert():
    assert "jobs.alte_auftraege_aufraeumen" in app.tasks


def test_hoechstens_ein_wartender_aufraeumauftrag(warteschlange):
    from procrastinate.exceptions import AlreadyEnqueued

    test_app, _ = warteschlange
    aufgabe = test_app.configure_task("jobs.alte_auftraege_aufraeumen")
    aufgabe.defer(timestamp=0)
    with pytest.raises(AlreadyEnqueued):
        test_app.configure_task("jobs.alte_auftraege_aufraeumen").defer(timestamp=1)


def test_aufraeumen_laeuft_taeglich():
    periodisch = {t.periodic_id: t for t in app.periodic_registry.periodic_tasks.values()}
    aufgabe = periodisch["alte_auftraege_aufraeumen"]
    assert aufgabe.cron == "0 3 * * *"
    assert aufgabe.task.name == "jobs.alte_auftraege_aufraeumen"


# Der Worker schließt vor jedem Auftrag alte Django-Datenbankverbindungen.
# Das verträgt sich nicht mit der Test-Transaktion, daher transaction=True.
@pytest.mark.django_db(transaction=True)
def test_aufraeumen_loescht_nur_alte_auftraege(warteschlange):
    test_app, connector = warteschlange

    # Zwei erledigte Aufträge: einer alt, einer frisch. Die Aufgabe hat eine
    # Warteschlangen-Sperre, deshalb jeden Auftrag erst abarbeiten.
    alt = test_app.configure_task("jobs.alte_auftraege_aufraeumen").defer(timestamp=0)
    _worker_laufen_lassen(test_app)
    frisch = test_app.configure_task("jobs.alte_auftraege_aufraeumen").defer(timestamp=1)
    _worker_laufen_lassen(test_app)
    assert connector.jobs[alt]["status"] == "succeeded"
    assert connector.jobs[frisch]["status"] == "succeeded"

    vor_langer_zeit = utils.utcnow() - datetime.timedelta(hours=tasks.AUFBEWAHRUNG_STUNDEN + 1)
    for ereignis in connector.events[alt]:
        ereignis["at"] = vor_langer_zeit

    neu = test_app.configure_task("jobs.alte_auftraege_aufraeumen").defer(timestamp=2)
    _worker_laufen_lassen(test_app)

    assert alt not in connector.jobs
    assert frisch in connector.jobs
    assert connector.jobs[neu]["status"] == "succeeded"


@pytest.mark.django_db
def test_datenbank_ist_fuer_procrastinate_eingerichtet(capsys):
    call_command("procrastinate", "healthchecks")
    ausgabe = capsys.readouterr().out
    assert "OK" in ausgabe
