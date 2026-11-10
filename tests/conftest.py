import pytest


@pytest.fixture(autouse=True)
def _schnelle_passwoerter(settings):
    """MD5 nur in Tests: macht das Anlegen und Anmelden von Nutzern schnell."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _statische_dateien_ohne_manifest(settings):
    """Tests laufen ohne collectstatic: Statische Dateien ohne Hash-Manifest."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def nutzer(db):
    from allauth.account.models import EmailAddress
    from django.contrib.auth import get_user_model

    n = get_user_model().objects.create_user(email="erika@example.org", password="geheim-123")
    EmailAddress.objects.create(user=n, email=n.email, verified=True, primary=True)
    return n
