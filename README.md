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

## Oberfläche

- **Wohnungen** → **Abrechnungen** (Jahr absteigend, mit Ergebnis) → **Abrechnung** mit
  Bereichen, Kosten, Vorauszahlungen und der Nachrechnung: gerundet nach der Regel des
  Bereichs und daneben exakt.
- Kosten und Vorauszahlungen fügt man mit HTMX direkt in der Seite hinzu und entfernt sie
  dort; das Ergebnis aktualisiert sich sofort. Ohne JavaScript funktioniert dasselbe mit
  Neuladen.
- Zahlen gibt man deutsch ein (`1.234,56`), Beträge erscheinen als `1.234,56 €`.
- Beim Anlegen eines Bereichs erklärt das Formular je Verteilerschlüssel, was als
  Gesamtmenge und Anteil einzutragen ist, und zeigt die Rundungsregeln an einem Beispiel.
- Wer eine Wohnung anlegt, verwaltet sie. Weitere Mitglieder (auch „Nur lesen“) und
  Zusatzfelder trägt man vorerst im Admin ein.

## Datenmodell

- **Wohnung** mit **Mitgliedschaften** (Rolle „Verwalten“ oder „Nur lesen“). Jede Abfrage
  auf Wohnungsdaten läuft über `objects.fuer_nutzer(nutzer)` bzw. `verwaltbar_fuer(nutzer)`.
- **Abrechnung** (Jahr, Zeitraum) → **Abrechnungsbereiche** mit Verteilerschlüssel
  (Umlage nach Fläche, pro Wohnung, nach Personen/Punkten oder individuell) und
  Rundungsregel → **Kostenpositionen** je Kostenart. Dazu **Vorauszahlungen**.
- **Kostenarten** und **Zusatzfelder** sind Daten: Neue legt man an, ohne Migration.
  Die Kostenarten nach § 2 BetrKV sind vorbelegt, jeweils mit passenden
  Verteilerschlüsseln und einem Hinweis. Im Bereich stehen nur Kostenarten zur Auswahl,
  die zu seinem Schlüssel passen. Kostenarten ohne Schlüssel passen überall.
- **Umlage individuell:** Jede Umlage hat Name, Art (Kostenart) und Gesamtbetrag und eine
  eigene Detailseite mit **Verbrauchseinheiten je Raum** (Raum, Gerätenummer, Einheiten).
  Bei Kostenarten „mit Brennstoff-/Energiekosten“ (Heizung, Heizung und Warmwasser) kommen
  **Brennstoff-Bezüge** dazu: Bezugsdatum, Menge in kWh, Betrag, Vermieteranteil
  CO₂-Kosten; die Summe Brennstoff-/Energiekosten rechnet die App aus.

Die Nachrechnung steht in `mieter/abrechnungen/berechnung.py`, nur mit `Decimal` und
`ROUND_HALF_UP`. Rundungsregeln pro Bereich:

| Regel | Rechnung |
|---|---|
| wie Vermieter | Einheitspreis auf 2 Stellen runden, × Anteil, Ergebnis auf Cent |
| n Stellen | wie oben, Einheitspreis auf n Stellen |
| exakt | keine Zwischenrundung, nur das Ergebnis auf Cent |

Die exakte Rechnung ohne jede Rundung wird immer mitgeführt.

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
