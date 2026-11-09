from django.urls import path

from . import views

urlpatterns = [
    path("", views.startseite, name="startseite"),
    path("wohnungen/neu/", views.wohnung_neu, name="wohnung_neu"),
    path("wohnungen/<int:pk>/", views.wohnung_detail, name="wohnung_detail"),
    path("wohnungen/<int:pk>/bearbeiten/", views.wohnung_bearbeiten, name="wohnung_bearbeiten"),
    path(
        "wohnungen/<int:wohnung_pk>/abrechnungen/neu/",
        views.abrechnung_neu,
        name="abrechnung_neu",
    ),
    path("abrechnungen/<int:pk>/", views.abrechnung_detail, name="abrechnung_detail"),
    path(
        "abrechnungen/<int:pk>/bearbeiten/",
        views.abrechnung_bearbeiten,
        name="abrechnung_bearbeiten",
    ),
    path("abrechnungen/<int:pk>/loeschen/", views.abrechnung_loeschen, name="abrechnung_loeschen"),
    path("abrechnungen/<int:abrechnung_pk>/bereiche/neu/", views.bereich_neu, name="bereich_neu"),
    path("bereiche/<int:pk>/bearbeiten/", views.bereich_bearbeiten, name="bereich_bearbeiten"),
    path("bereiche/<int:pk>/loeschen/", views.bereich_loeschen, name="bereich_loeschen"),
    path("bereiche/<int:bereich_pk>/positionen/neu/", views.position_neu, name="position_neu"),
    path("positionen/<int:pk>/loeschen/", views.position_loeschen, name="position_loeschen"),
    path(
        "abrechnungen/<int:abrechnung_pk>/vorauszahlungen/neu/",
        views.vorauszahlung_neu,
        name="vorauszahlung_neu",
    ),
    path(
        "vorauszahlungen/<int:pk>/loeschen/",
        views.vorauszahlung_loeschen,
        name="vorauszahlung_loeschen",
    ),
]
