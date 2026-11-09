# Mieter

Selbst gehostete Web-App für Mieter in Deutschland: Betriebskostenabrechnungen
erfassen, nachrechnen und auswerten.

## Voraussetzungen

- [uv](https://docs.astral.sh/uv/) (installiert Python 3.13 bei Bedarf selbst)
- Docker mit Docker Compose (für PostgreSQL 17)

## Schnellstart

```sh
cp .env.beispiel .env          # danach SECRET_KEY setzen
docker compose -f compose.dev.yml up -d
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Die App läuft dann unter <http://localhost:8000/>, die Verwaltung unter `/admin/`.

## Anmeldung

- Angemeldet wird mit E-Mail-Adresse und Passwort. Ohne Anmeldung ist keine Seite erreichbar.
- Neue Konten legst du im Admin an (`/admin/`) oder mit `uv run python manage.py createsuperuser`.
  Die Selbstregistrierung ist standardmäßig aus (`REGISTRIERUNG_OFFEN`).
- Bei der ersten Anmeldung muss die E-Mail-Adresse bestätigt werden. In der Entwicklung
  erscheint die Bestätigungs-Mail in der Konsole von `runserver`.

### Synology SSO Server (OIDC)

1. Im SSO Server unter *Dienste → OIDC* eine Anwendung anlegen. Redirect-URI:
   `<Basis-URL>/konto/oidc/synology/login/callback/`, z. B.
   `http://localhost:8000/konto/oidc/synology/login/callback/`.
2. In `.env` setzen: `OIDC_SERVER_URL` (die Well-Known-URL des SSO Servers ohne
   `/.well-known/openid-configuration`), `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`.
3. Auf der Anmeldeseite erscheint dann „Anmelden mit Synology SSO“.

Über SSO meldet sich nur an, wer schon ein Konto mit derselben E-Mail-Adresse hat
(solange die Registrierung geschlossen ist). Die E-Mail-Adresse des eigenen SSO Servers gilt
als vertrauenswürdig; abschalten mit `OIDC_EMAIL_VERTRAUEN=False`.

## Hintergrundaufgaben

Längere Arbeiten laufen über [Procrastinate](https://procrastinate.readthedocs.io/) mit der
Warteschlange in PostgreSQL. Der Worker ist ein eigener Prozess neben `runserver`:

```sh
uv run python manage.py procrastinate worker        # Worker starten
uv run python manage.py procrastinate healthchecks  # Verbindung und Migrationen prüfen
```

Aufgaben stehen in `tasks.py` der jeweiligen App. Täglich um 03:00 UTC löscht
`jobs.alte_auftraege_aufraeumen` abgeschlossene Aufträge, die älter als 30 Tage sind.

## Konfiguration

Alle Einstellungen kommen aus Umgebungsvariablen; eine `.env`-Datei im
Projektverzeichnis wird automatisch gelesen. Alle Variablen mit Erklärung stehen
in `.env.beispiel`.

## Entwicklung

```sh
uv run pytest                                  # Tests
uv run ruff check . && uv run ruff format --check .   # Lint
```

Einmalig die Git-Hooks einrichten (ruff, gitleaks und weitere Prüfungen vor
jedem Commit):

```sh
uv run pre-commit install
```

Die CI auf GitHub Actions (`.github/workflows/ci.yml`) führt Lint, Tests und
gitleaks bei jedem Push auf `main` und bei Pull Requests aus.

## Lizenz

[MIT](LICENSE)
