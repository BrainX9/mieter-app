"""Allgemeine Seiten ohne Bezug zu Wohnungsdaten."""

import logging

from django.contrib.auth.decorators import login_not_required
from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@login_not_required
@never_cache
@require_GET
def gesund(request):
    """Statusseite für den Healthcheck: 200, wenn die Datenbank antwortet, sonst 503."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Healthcheck: Datenbank nicht erreichbar")
        return HttpResponse("Datenbank nicht erreichbar", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
