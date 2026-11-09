from django.conf import settings


def app(request):
    return {"registrierung_offen": settings.REGISTRIERUNG_OFFEN}
