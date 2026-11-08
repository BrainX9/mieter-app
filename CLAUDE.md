# Mieter

Selbst gehostete Web-App für Mieter in Deutschland: Betriebskostenabrechnungen
erfassen, nachrechnen und auswerten. Repository, Image und Domain heißen mieter-app.

## Sprache
- Oberfläche, Fehlermeldungen, Doku, Commit-Messages, Issues und PRs auf Deutsch.
- Modell- und Feldnamen deutsch ohne Umlaute (abrechnungsjahr), verbose_name mit Umlauten.
- LANGUAGE_CODE de-de, TIME_ZONE Europe/Berlin, Beträge im Format 1.234,56 €.

## Stack
Django 5.2 LTS, Python 3.13, PostgreSQL 17, HTMX, django-allauth (lokal + OIDC über
Synology SSO Server), Procrastinate (Jobs), uv, pytest, ruff.
Entwicklung auf Mac (Apple Silicon), Betrieb als Docker auf Synology (amd64 und arm64).

## Befehle
- Start: docker compose -f compose.dev.yml up -d && uv run python manage.py runserver
- Tests: uv run pytest
- Lint: uv run ruff check . && uv run ruff format --check .

## Regeln
- Geld immer Decimal, nie float. Runden nach der Rundungsregel des Abrechnungsbereichs
  (wie Vermieter, n Stellen, exakt; ROUND_HALF_UP). Die exakte Rechnung immer mitführen.
- Abrechnungen standardmäßig nach Jahr absteigend sortieren.
- Kostenarten und Zusatzfelder sind Daten, keine Spalten. Keine Migration für neue Kostenarten.
- Jede Abfrage auf Wohnungsdaten filtert über die Mitgliedschaft des angemeldeten Nutzers.
- KI-Ergebnisse nie direkt speichern: immer Vorschlag, den der Nutzer bestätigt.
- KI-Anbieter nur über die Schnittstelle in mieter/ki/anbieter.py ansprechen.
- Keine echten Daten in Code, Tests, Fixtures, Screenshots oder Commits. Testdaten synthetisch.
- Secrets nur aus Umgebungsvariablen. .env nie lesen oder ausgeben.
- Jede Änderung mit Tests. Vor jedem Commit: ruff und pytest grün.
- Vor größeren Änderungen erst einen Plan vorlegen.

## Vorlage
MCP-Server "nocodb": Base "Haushalt Betriebskostenabrechnung" ist Vorlage für das Schema
und Quelle für Testdaten. Nur lesen, nichts ändern.
