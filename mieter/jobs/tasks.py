"""Hintergrundaufgaben (Procrastinate).

Procrastinate findet Aufgaben in jedem tasks.py der installierten Apps.
Der Worker läuft getrennt vom Webserver: uv run python manage.py procrastinate worker
"""

from procrastinate import JobContext
from procrastinate.contrib.django import app

# Erledigte Aufträge so lange aufbewahren, danach löschen.
AUFBEWAHRUNG_STUNDEN = 30 * 24


# Cron-Zeiten von Procrastinate sind UTC: 03:00 UTC = 04:00 bzw. 05:00 Uhr in Berlin.
@app.periodic(cron="0 3 * * *", periodic_id="alte_auftraege_aufraeumen")
@app.task(
    name="jobs.alte_auftraege_aufraeumen",
    queue="wartung",
    queueing_lock="alte_auftraege_aufraeumen",
    pass_context=True,
)
async def alte_auftraege_aufraeumen(context: JobContext, timestamp: int) -> None:
    """Löscht abgeschlossene Aufträge, die älter als AUFBEWAHRUNG_STUNDEN sind."""
    await context.app.job_manager.delete_old_jobs(
        nb_hours=AUFBEWAHRUNG_STUNDEN,
        include_failed=True,
        include_cancelled=True,
        include_aborted=True,
    )
