"""URL-Konfiguration für mieter."""

from django.contrib import admin
from django.urls import include, path

from mieter.kern.views import StartseiteView

urlpatterns = [
    path("", StartseiteView.as_view(), name="startseite"),
    path("konto/", include("allauth.urls")),
    path("admin/", admin.site.urls),
]
