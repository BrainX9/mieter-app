"""URL-Konfiguration für mieter."""

from django.contrib import admin
from django.urls import include, path

from mieter.kern.views import gesund

urlpatterns = [
    path("gesund/", gesund, name="gesund"),
    path("konto/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("", include("mieter.abrechnungen.urls")),
]
