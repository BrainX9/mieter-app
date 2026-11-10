#!/bin/sh
# Startet das Image mit einer Wegwerf-Datenbank und prüft die wichtigsten Seiten.
#   docker/smoke-test.sh [image]     (Standard: mieter-app:test)
# Alle Zugangsdaten hier sind Platzhalter nur für diesen Test.
set -eu

IMAGE="${1:-mieter-app:test}"
NAME="mieter-smoke-$$"
PORT="${SMOKE_PORT:-18000}"
DB_URL="postgres://mieter:smoke@$NAME-db:5432/mieter"

aufraeumen() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "--- Protokoll web ---"; docker logs "$NAME-web" 2>&1 | tail -40 || true
    echo "--- Protokoll worker ---"; docker logs "$NAME-worker" 2>&1 | tail -20 || true
  fi
  docker rm -f "$NAME-web" "$NAME-worker" "$NAME-db" >/dev/null 2>&1 || true
  docker network rm "$NAME" >/dev/null 2>&1 || true
  exit "$status"
}
trap aufraeumen EXIT

docker network create "$NAME" >/dev/null
docker run -d --name "$NAME-db" --network "$NAME" \
  -e POSTGRES_DB=mieter -e POSTGRES_USER=mieter -e POSTGRES_PASSWORD=smoke \
  postgres:17 >/dev/null
until docker exec "$NAME-db" pg_isready -U mieter -d mieter >/dev/null 2>&1; do sleep 1; done

for rolle in web worker; do
  docker run -d --name "$NAME-$rolle" --network "$NAME" \
    $( [ "$rolle" = web ] && echo "-p 127.0.0.1:$PORT:8000" ) \
    -e SECRET_KEY=nur-fuer-den-smoke-test -e DATABASE_URL="$DB_URL" \
    -e ALLOWED_HOSTS=mieter.example.org -e CSRF_TRUSTED_ORIGINS=https://mieter.example.org \
    "$IMAGE" "$rolle" >/dev/null
  # Der Worker braucht die Tabellen, die web beim Start anlegt.
  if [ "$rolle" = web ]; then
    i=0
    until curl -fsS "http://127.0.0.1:$PORT/gesund/" >/dev/null 2>&1; do
      i=$((i + 1)); [ "$i" -lt 60 ] || { echo "web startet nicht"; exit 1; }; sleep 1
    done
  fi
done

pruefe() {
  echo "prüfe: $1"
  shift
  "$@" || { echo "FEHLGESCHLAGEN"; exit 1; }
}

pruefe "Statusseite" sh -c "curl -fsS http://127.0.0.1:$PORT/gesund/ | grep -qx ok"
pruefe "Anmeldeseite hinter Proxy" sh -c "curl -fsS -H 'X-Forwarded-Proto: https' \
  -H 'X-Forwarded-Host: mieter.example.org' http://127.0.0.1:$PORT/konto/login/ | grep -q Anmelden"
pruefe "Fremder Host abgelehnt" sh -c "test \"\$(curl -s -o /dev/null -w '%{http_code}' \
  -H 'Host: boese.example.org' http://127.0.0.1:$PORT/konto/login/)\" = 400"
css=$(curl -fsS -H 'X-Forwarded-Host: mieter.example.org' "http://127.0.0.1:$PORT/konto/login/" \
  | grep -o '/static/mieter\.[0-9a-f]*\.css' | head -1)
pruefe "CSS mit Hash im Namen ($css)" test -n "$css"
pruefe "CSS wird ausgeliefert" curl -fsS -o /dev/null "http://127.0.0.1:$PORT$css"
pruefe "Läuft nicht als root" sh -c "test \"\$(docker exec $NAME-web id -u)\" != 0"
pruefe "Keine .env im Image" sh -c "! docker exec $NAME-web test -e /app/.env"
pruefe "Keine Tests im Image" sh -c "! docker exec $NAME-web test -e /app/tests"
pruefe "Worker läuft" sh -c "sleep 2; test \"\$(docker inspect -f '{{.State.Running}}' $NAME-worker)\" = true"
pruefe "Worker erreicht Datenbank" docker exec "$NAME-worker" python manage.py procrastinate healthchecks

echo "Smoke-Test bestanden."
