# Betrieb auf der Synology

Die App läuft als Docker-Projekt im **Container Manager** (DSM 7.2 oder neuer) und auf
amd64- wie arm64-Modellen. Von außen erreicht man sie über den **Reverse Proxy** von DSM
mit HTTPS.

Das Projekt besteht aus drei Containern:

| Dienst     | Aufgabe                                                                 |
|------------|-------------------------------------------------------------------------|
| `postgres` | Datenbank (PostgreSQL 17), Daten in `daten/postgres`                    |
| `web`      | die App; führt beim Start die Migrationen aus                           |
| `worker`   | Hintergrundaufgaben (Procrastinate)                                     |

Das Image `ghcr.io/brainx9/mieter-app` ist öffentlich, die Synology braucht keinen Zugang
zu GitHub.

## 1. Ordner und Konfiguration

1. In der File Station unter `docker` den Ordner `mieter-app` anlegen, also
   `/volume1/docker/mieter-app`.
2. Dorthin laden:
   - [`compose.yml`](../compose.yml)
   - [`.env.synology.beispiel`](../.env.synology.beispiel), umbenannt in `.env`
3. In `.env` alle Werte in `<...>` ersetzen:
   - `SECRET_KEY`: ein langer Zufallswert, z. B. per SSH `openssl rand -base64 48`.
   - `ALLOWED_HOSTS` und `CSRF_TRUSTED_ORIGINS`: die Adresse der App, z. B.
     `mieter.example.org` und `https://mieter.example.org`.
   - `POSTGRES_PASSWORD`: nur Buchstaben und Ziffern, z. B. `openssl rand -hex 24`.

Die `.env` enthält Geheimnisse. Sie gehört nicht in Chats, Tickets oder Git.

## 2. Projekt anlegen

1. **Container Manager → Projekt → Erstellen**.
2. Projektname `mieter-app`, Pfad `/volume1/docker/mieter-app`. Der Container Manager
   erkennt die vorhandene `compose.yml`.
3. Das Angebot für ein Web Station-Portal ablehnen; den Zugang regelt der Reverse Proxy.
4. **Fertig**. Der erste Start lädt die Images und richtet die Datenbank ein.

Nach etwa einer Minute stehen alle drei Container auf „Wird ausgeführt“, `web` und
`worker` zusätzlich auf „Gesund“.

Per SSH geht dasselbe mit:

```sh
cd /volume1/docker/mieter-app
sudo docker compose up -d
```

## 3. Admin-Konto anlegen

Im Container Manager **Container → mieter-app-web-1 → Aktion → Terminal öffnen →
Erstellen → Mit Befehl starten**, Befehl:

```sh
python manage.py createsuperuser
```

Oder per SSH:

```sh
cd /volume1/docker/mieter-app
sudo docker compose exec web python manage.py createsuperuser
```

Weitere Konten legst du danach unter `/admin/` an.

## 4. Reverse Proxy mit HTTPS

1. **Systemsteuerung → Anmeldeportal → Erweitert → Reverse Proxy → Erstellen**:
   - Quelle: Protokoll `HTTPS`, Hostname `mieter.example.org`, Port `443`,
     HSTS vorerst aus.
   - Ziel: Protokoll `HTTP`, Hostname `localhost`, Port `8000` (bzw. `MIETER_PORT`).
2. **Systemsteuerung → Sicherheit → Zertifikat → Hinzufügen**: ein Let's-Encrypt-Zertifikat
   für `mieter.example.org`. Unter **Einstellungen** dem Reverse-Proxy-Eintrag zuweisen.
3. Im Router Port 443 auf die Synology weiterleiten, falls die App aus dem Internet
   erreichbar sein soll. Für reinen Zugriff aus dem Heimnetz oder per VPN entfällt das.

Die App lauscht nur auf `127.0.0.1` der Synology. Am Reverse Proxy vorbei ist sie nicht
erreichbar.

**Prüfen:** Unter `https://mieter.example.org/gesund/` erscheint `ok`. Danach anmelden.

Läuft HTTPS sicher, kann HSTS eingeschaltet werden: im Reverse Proxy oder mit
`HSTS_SEKUNDEN=31536000` in der `.env`.

### Nur im Heimnetz ohne HTTPS

In der `.env` `HTTPS=False` setzen, `ALLOWED_HOSTS` auf den Namen oder die IP der
Synology und `CSRF_TRUSTED_ORIGINS` auf `http://<name>:<port>`. In `compose.yml` steht der
Port dann auf `127.0.0.1`. Für direkten Zugriff ohne Proxy die Zeile unter `ports` in
`"${MIETER_PORT:-8000}:8000"` ändern.

## 5. Anmeldung über den Synology SSO Server (optional)

1. Im **SSO Server → Dienste → OIDC** eine Anwendung anlegen. Redirect-URI:
   `https://mieter.example.org/konto/oidc/synology/login/callback/`
2. In der `.env` `OIDC_SERVER_URL`, `OIDC_CLIENT_ID` und `OIDC_CLIENT_SECRET` setzen
   (Einzelheiten im [README](../README.md#synology-sso-server-oidc)).
3. Projekt neu starten (**Projekt → Aktion → Neu starten**).

## 6. Updates

1. Vorher die Datenbank sichern (siehe unten).
2. Per SSH das neue Image holen und das Projekt neu starten:

   ```sh
   cd /volume1/docker/mieter-app
   sudo docker compose pull
   sudo docker compose up -d
   ```

   `web` führt beim Start die Migrationen aus.

Mit `MIETER_VERSION=0.1.0` in der `.env` bleibt die App auf einer festen Version, bis du
sie änderst. Ohne Angabe folgt sie `latest`.

## 7. Datenbank sichern und wiederherstellen

Eine automatische Sicherung gibt es noch nicht; eine Backup-Funktion im Admin-Menü ist
geplant. Bis dahin sicherst du von Hand, vor allem vor jedem Update:

```sh
cd /volume1/docker/mieter-app
mkdir -p backup
sudo docker compose exec -T postgres sh -c \
  'pg_dump --format=custom -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > backup/mieter-$(date +%Y-%m-%d).dump
```

**Hyper Backup:** den Ordner `/volume1/docker/mieter-app` sichern, aber **ohne**
`daten/postgres`. Die Dateien einer laufenden Datenbank sind keine verlässliche Sicherung;
dafür sind die Dumps in `backup/` da. Weil `.env` Geheimnisse enthält, die Sicherung
verschlüsseln.

**Wiederherstellen** (überschreibt den aktuellen Stand der Datenbank):

```sh
cd /volume1/docker/mieter-app
sudo docker compose stop web worker
sudo docker compose exec -T postgres sh -c \
  'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < backup/mieter-2026-11-10.dump
sudo docker compose start web worker
```

## Fehlersuche

- **Protokolle:** Container Manager → Container → Protokoll, oder
  `sudo docker compose logs web`.
- **„Bad Request (400)“:** Die Adresse fehlt in `ALLOWED_HOSTS`.
- **„CSRF-Überprüfung fehlgeschlagen“ beim Anmelden:** `CSRF_TRUSTED_ORIGINS` muss genau
  der Adresse im Browser entsprechen, mit `https://` und ohne Schrägstrich am Ende.
- **SSO meldet eine Redirect-URI mit `http://`:** Der Reverse Proxy gibt nicht weiter,
  dass HTTPS benutzt wird. Im Reverse-Proxy-Eintrag unter **Benutzerdefinierte
  Kopfzeile** `X-Forwarded-Proto` mit dem Wert `$scheme` ergänzen.
- **Port 8000 belegt:** in der `.env` `MIETER_PORT=8010` setzen und im Reverse Proxy
  denselben Port eintragen.
- **`web` wird nicht gesund:** meist fehlt die Datenbank oder `POSTGRES_PASSWORD` wurde
  nach dem ersten Start geändert. Das Passwort gilt ab dem ersten Start; ändern nur in
  PostgreSQL selbst.
