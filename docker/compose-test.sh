#!/bin/sh
# Startet compose.yml wie auf der Synology, aber mit einem lokal gebauten Image, und prüft
# Web, Worker und das Anlegen eines Admins.
#   docker/compose-test.sh [image:tag]     (Standard: mieter-app:test)
# Arbeitet in einem neuen temporären Ordner, der danach liegen bleibt (Ausgabe am Ende).
# Alle Zugangsdaten sind Platzhalter nur für diesen Test.
set -eu

IMAGE="${1:-mieter-app:test}"
WURZEL="$(cd "$(dirname "$0")/.." && pwd)"
ORDNER="$(mktemp -d "${TMPDIR:-/tmp}/mieter-compose-test.XXXXXX")"
PORT="${COMPOSE_TEST_PORT:-18001}"
PROJEKT="mieter-compose-test-$$"

cp "$WURZEL/compose.yml" "$ORDNER/compose.yml"
cat > "$ORDNER/.env" <<EOF
SECRET_KEY=nur-fuer-den-compose-test
ALLOWED_HOSTS=mieter.example.org
CSRF_TRUSTED_ORIGINS=https://mieter.example.org
POSTGRES_PASSWORD=composetest
MIETER_IMAGE=${IMAGE%:*}
MIETER_VERSION=${IMAGE##*:}
MIETER_PORT=$PORT
EOF

dc() { docker compose --project-directory "$ORDNER" -p "$PROJEKT" "$@"; }

aufraeumen() {
  status=$?
  [ "$status" -eq 0 ] || dc logs --tail 40 || true
  dc down -v >/dev/null 2>&1 || true
  echo "Testordner: $ORDNER"
  exit "$status"
}
trap aufraeumen EXIT

pruefe() {
  echo "prüfe: $1"
  shift
  "$@" || { echo "FEHLGESCHLAGEN"; exit 1; }
}

pruefe "Konfiguration gültig" dc config --quiet
dc up -d --wait --wait-timeout 180

pruefe "Statusseite" sh -c "curl -fsS http://127.0.0.1:$PORT/gesund/ | grep -qx ok"
worker_gesund() {
  test "$(docker inspect -f '{{.State.Health.Status}}' "$(dc ps -q worker)")" = healthy
}
# Sicherung und Wiederherstellung genau wie in docs/synology.md beschrieben.
sichern_wie_anleitung() {
  dc exec -T postgres sh -c \
    'pg_dump --format=custom -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$ORDNER/test.dump"
  dc stop web worker >/dev/null
  dc exec -T postgres sh -c \
    'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$ORDNER/test.dump"
  dc start web worker >/dev/null
  i=0
  until curl -fsS "http://127.0.0.1:$PORT/gesund/" >/dev/null 2>&1; do
    i=$((i + 1)); [ "$i" -lt 60 ] || return 1; sleep 1
  done
  dc exec -T web python manage.py shell -c \
    "from mieter.konten.models import Nutzer; assert Nutzer.objects.filter(email='admin@example.org').exists()"
}
port_nur_lokal() {
  case "$(dc port web 8000)" in 127.0.0.1:*) ;; *) return 1 ;; esac
}

pruefe "Worker gesund" worker_gesund
pruefe "Admin anlegen" dc exec -T \
  -e DJANGO_SUPERUSER_EMAIL=admin@example.org -e DJANGO_SUPERUSER_PASSWORD=nur-ein-test-123 \
  web python manage.py createsuperuser --noinput
pruefe "Port nur lokal" port_nur_lokal
pruefe "Sichern und Wiederherstellen laut Anleitung" sichern_wie_anleitung

echo "Compose-Test bestanden."
