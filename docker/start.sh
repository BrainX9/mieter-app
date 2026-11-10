#!/bin/sh
# Startskript des Images. Ein Image, zwei Rollen:
#   web     Migrationen ausführen, dann gunicorn auf Port 8000
#   worker  Procrastinate-Worker für Hintergrundaufgaben
# Alles andere wird direkt ausgeführt, z. B. "python manage.py createsuperuser".
set -e

case "$1" in
  web)
    python manage.py migrate --noinput
    exec gunicorn mieter.wsgi \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-2}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --access-logfile - \
      --forwarded-allow-ips "*"
    ;;
  worker)
    exec python manage.py procrastinate worker
    ;;
  *)
    exec "$@"
    ;;
esac
