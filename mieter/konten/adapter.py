from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class KontoAdapter(DefaultAccountAdapter):
    """Selbstregistrierung nur, wenn REGISTRIERUNG_OFFEN gesetzt ist.

    Gilt auch für die Anmeldung über OIDC: Ohne bestehendes Konto entsteht kein neues.
    """

    def is_open_for_signup(self, request):
        return settings.REGISTRIERUNG_OFFEN
