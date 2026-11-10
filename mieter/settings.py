"""Django-Einstellungen für mieter.

Alle umgebungsabhängigen Werte kommen aus Umgebungsvariablen (django-environ).
Vorlage mit allen Variablen: .env.beispiel
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    REGISTRIERUNG_OFFEN=(bool, False),
    EMAIL_BESTAETIGUNG=(str, "mandatory"),
    OIDC_SERVER_URL=(str, ""),
    OIDC_CLIENT_ID=(str, ""),
    OIDC_CLIENT_SECRET=(str, ""),
    OIDC_ANZEIGENAME=(str, "Synology SSO"),
    OIDC_EMAIL_VERTRAUEN=(bool, True),
    HSTS_SEKUNDEN=(int, 0),
    LOG_LEVEL=(str, "INFO"),
)

# Eine lokale .env-Datei ist optional; gesetzte Umgebungsvariablen haben Vorrang.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
# localhost immer erlaubt: Der Healthcheck im Container ruft http://localhost:8000/gesund/ auf.
ALLOWED_HOSTS = list(dict.fromkeys([*env("ALLOWED_HOSTS"), "localhost", "127.0.0.1"]))
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")


# Betrieb hinter einem Reverse Proxy (z. B. DSM), der HTTPS übernimmt und
# X-Forwarded-Proto und X-Forwarded-Host setzt.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Cookies nur über HTTPS. Standard: an, sobald DEBUG aus ist. Für reinen Betrieb im
# Heimnetz ohne HTTPS: HTTPS=False.
HTTPS = env.bool("HTTPS", default=not DEBUG)
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
# HSTS erst einschalten, wenn HTTPS sicher läuft (z. B. 31536000 = ein Jahr).
SECURE_HSTS_SECONDS = env("HSTS_SEKUNDEN") if HTTPS else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"


# Anwendungen

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "procrastinate.contrib.django",
    "mieter.konten",
    "mieter.kern",
    "mieter.jobs",
    "mieter.abrechnungen",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Alle Seiten nur für angemeldete Nutzer, Ausnahmen per @login_not_required
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "mieter.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "mieter" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "mieter.kern.context_processors.app",
            ],
        },
    },
]

WSGI_APPLICATION = "mieter.wsgi.application"


# Datenbank (PostgreSQL), z. B. postgres://benutzer:passwort@localhost:5432/mieter

DATABASES = {"default": env.db("DATABASE_URL")}


# Nutzer und Anmeldung (django-allauth)

AUTH_USER_MODEL = "konten.Nutzer"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "startseite"
ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"

ACCOUNT_ADAPTER = "mieter.konten.adapter.KontoAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = env("EMAIL_BESTAETIGUNG")

# Neue Konten nur, wenn REGISTRIERUNG_OFFEN gesetzt ist (siehe KontoAdapter).
REGISTRIERUNG_OFFEN = env("REGISTRIERUNG_OFFEN")

# OIDC über den Synology SSO Server. Aktiv nur, wenn Server, Client-ID und Secret gesetzt sind.
# Redirect-URI beim SSO Server: <Basis-URL>/konto/oidc/synology/login/callback/
SOCIALACCOUNT_PROVIDERS = {}
if env("OIDC_SERVER_URL") and env("OIDC_CLIENT_ID") and env("OIDC_CLIENT_SECRET"):
    SOCIALACCOUNT_PROVIDERS["openid_connect"] = {
        "APPS": [
            {
                "provider_id": "synology",
                "name": env("OIDC_ANZEIGENAME"),
                "client_id": env("OIDC_CLIENT_ID"),
                "secret": env("OIDC_CLIENT_SECRET"),
                "settings": {
                    "server_url": env("OIDC_SERVER_URL"),
                    # Der eigene SSO Server gilt als vertrauenswürdig: Seine E-Mail-Adresse
                    # meldet ein bestehendes lokales Konto mit derselben Adresse an.
                    "verified_email": env("OIDC_EMAIL_VERTRAUEN"),
                    "email_authentication": env("OIDC_EMAIL_VERTRAUEN"),
                },
            }
        ]
    }
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True


# E-Mail, z. B. smtp+tls://benutzer:passwort@smtp.example.org:587

vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="mieter@localhost")


# Hintergrundaufgaben (Procrastinate). Die Warteschlange liegt in PostgreSQL.

PROCRASTINATE_DATABASE_ALIAS = "default"


# Passwortprüfung

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Sprache und Zeit

LANGUAGE_CODE = "de-de"
LANGUAGES = [("de", "Deutsch")]
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True


# Statische Dateien

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "mieter" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# WhiteNoise liefert die statischen Dateien selbst aus, komprimiert und mit Hash im Namen.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


# Protokoll auf die Standardausgabe (im Container Manager unter „Protokoll“ sichtbar)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "einfach": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "konsole": {"class": "logging.StreamHandler", "formatter": "einfach"},
    },
    "root": {"handlers": ["konsole"], "level": env("LOG_LEVEL")},
    # Ersetzt Djangos eigene Handler, sonst erscheinen Meldungen bei DEBUG doppelt.
    "loggers": {
        "django": {"handlers": ["konsole"], "level": env("LOG_LEVEL"), "propagate": False},
        # Procrastinate meldet beim Start jede Aufgabe; nur der Worker soll gesprächig sein.
        "procrastinate": {"level": "WARNING"},
        "procrastinate.worker": {"level": env("LOG_LEVEL")},
    },
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
