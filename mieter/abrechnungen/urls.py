from django.urls import path

from . import views

urlpatterns = [
    path("", views.startseite, name="startseite"),
    path("wohnungen/neu/", views.wohnung_neu, name="wohnung_neu"),
    path("wohnungen/<int:pk>/", views.wohnung_detail, name="wohnung_detail"),
    path("wohnungen/<int:pk>/bearbeiten/", views.wohnung_bearbeiten, name="wohnung_bearbeiten"),
    path("wohnungen/<int:pk>/verlassen/", views.wohnung_verlassen, name="wohnung_verlassen"),
    path("wohnungen/<int:wohnung_pk>/mitglieder/neu/", views.mitglied_neu, name="mitglied_neu"),
    path(
        "wohnungen/<int:wohnung_pk>/zusatzfelder/neu/",
        views.zusatzfeld_neu,
        name="zusatzfeld_neu",
    ),
    path(
        "zusatzfelder/<int:pk>/bearbeiten/",
        views.zusatzfeld_bearbeiten,
        name="zusatzfeld_bearbeiten",
    ),
    path("zusatzfelder/<int:pk>/loeschen/", views.zusatzfeld_loeschen, name="zusatzfeld_loeschen"),
    path(
        "abrechnungen/<int:abrechnung_pk>/zusatzwerte/",
        views.zusatzwerte_speichern,
        name="zusatzwerte_speichern",
    ),
    path("mitglieder/<int:pk>/rolle/", views.mitglied_rolle, name="mitglied_rolle"),
    path("mitglieder/<int:pk>/entfernen/", views.mitglied_entfernen, name="mitglied_entfernen"),
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
    path("positionen/<int:pk>/", views.position_detail, name="position_detail"),
    path("positionen/<int:pk>/bearbeiten/", views.position_bearbeiten, name="position_bearbeiten"),
    path("positionen/<int:pk>/loeschen/", views.position_loeschen, name="position_loeschen"),
    path(
        "positionen/<int:position_pk>/brennstoff/neu/",
        views.brennstoff_neu,
        name="brennstoff_neu",
    ),
    path("brennstoff/<int:pk>/loeschen/", views.brennstoff_loeschen, name="brennstoff_loeschen"),
    path("positionen/<int:position_pk>/raeume/neu/", views.raum_neu, name="raum_neu"),
    path("raeume/<int:pk>/loeschen/", views.raum_loeschen, name="raum_loeschen"),
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
