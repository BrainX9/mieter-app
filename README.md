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
