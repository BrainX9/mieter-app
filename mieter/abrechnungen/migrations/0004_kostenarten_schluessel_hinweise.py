"""Verteilerschlüssel vereinheitlichen und den Kostenarten-Katalog ergänzen.

Bereiche:
- „Punkte / Einheiten“ und „Personen“ werden zu „Umlage nach Personen / Punkten“.
- „Direkt“ wird zu „Umlage individuell“.

Kostenarten: passende Verteilerschlüssel und Hinweise. Die Zuordnung folgt der Vorlage
(Fläche: Grundsteuer, Versicherungen, Straßenreinigung, Garten; Punkte: Wasser,
Entwässerung, Müll, Allgemeinstrom; individuell: Heizung und Warmwasser) und sonst der
Grundregel aus § 556a Abs. 1 BGB (Wohnfläche, verbrauchsabhängige Kosten nach Verbrauch).
Schon gepflegte Kostenarten (Schlüssel oder Hinweis gesetzt) bleiben unverändert.
"""

from django.db import migrations

FLAECHE = "wohnflaeche"
WOHNUNG = "wohneinheiten"
PUNKTE = "personen_punkte"
INDIVIDUELL = "individuell"

BEREICHE_ALT_NEU = {"einheiten": PUNKTE, "personen": PUNKTE, "direkt": INDIVIDUELL}
BEREICHE_NEU_ALT = {PUNKTE: "einheiten", INDIVIDUELL: "direkt"}

HEIZKOSTEN = (
    "Abrechnung nach Heizkostenverordnung: 50 bis 70 % nach Verbrauch, der Rest meist "
    "nach Fläche. Der Betrag steht in der Heizkostenabrechnung des Messdienstes."
)
CO2 = (
    " Seit 2023 trägt der Vermieter je nach CO₂-Ausstoß des Gebäudes einen Teil der "
    "CO₂-Kosten (Kohlendioxidkostenaufteilungsgesetz)."
)

KATALOG = {
    "Grundsteuer": (
        [FLAECHE],
        "Laufende öffentliche Lasten des Grundstücks. Ohne andere Vereinbarung nach Wohnfläche.",
    ),
    "Wasserversorgung": (
        [PUNKTE, INDIVIDUELL],
        "Meist nach Verbrauch laut Wasserzähler oder nach Personen. Enthält auch "
        "Grundgebühren, Zählermiete und Eichung.",
    ),
    "Entwässerung": (
        [PUNKTE, INDIVIDUELL],
        "Wird oft nach dem Frischwasserverbrauch berechnet und dann wie das Wasser verteilt.",
    ),
    "Heizung": ([INDIVIDUELL], HEIZKOSTEN),
    "Warmwasser": ([INDIVIDUELL], HEIZKOSTEN),
    "Heizung und Warmwasser": ([INDIVIDUELL], HEIZKOSTEN + CO2),
    "Aufzug": ([FLAECHE, WOHNUNG], "Strom, Beaufsichtigung, Prüfung und Reinigung des Aufzugs."),
    "Straßenreinigung": ([FLAECHE], "Gebühren der öffentlichen Straßenreinigung."),
    "Müllbeseitigung": (
        [PUNKTE, FLAECHE, WOHNUNG],
        "Häufig nach Personen, Fläche oder pro Wohnung. Wird die Müllmenge je Wohnung "
        "erfasst, muss danach abgerechnet werden.",
    ),
    "Gebäudereinigung": ([FLAECHE], "Reinigung von Fluren, Treppen, Kellern und Waschküchen."),
    "Ungezieferbekämpfung": (
        [FLAECHE],
        "Nur laufende, regelmäßige Bekämpfung. Einmalige Einsätze sind keine Betriebskosten.",
    ),
    "Gartenpflege": ([FLAECHE], "Gärtnerisch angelegte Flächen, Spielplätze, Wege, Zufahrten."),
    "Beleuchtung (Allgemeinstrom)": (
        [FLAECHE, PUNKTE],
        "Strom für Außenbeleuchtung, Treppenhaus, Keller und andere gemeinsame Räume.",
    ),
    "Schornsteinreinigung": (
        [FLAECHE, INDIVIDUELL],
        "Kehrgebühren, soweit nicht schon in den Heizkosten enthalten.",
    ),
    "Gebäudeversicherung": (
        [FLAECHE],
        "Feuer-, Sturm-, Wasser- und Elementarschäden, auch Glasversicherung.",
    ),
    "Haftpflichtversicherung": ([FLAECHE], "Haftpflicht für Gebäude, Öltank und Aufzug."),
    "Hauswart": (
        [FLAECHE],
        "Nur Arbeiten, die Betriebskosten sind. Reparatur und Verwaltung gehören nicht dazu.",
    ),
    "Antenne / Breitbandnetz": (
        [WOHNUNG],
        "Seit dem 1. Juli 2024 dürfen Nutzungsentgelte für Kabelfernsehen nicht mehr "
        "umgelegt werden, nur noch z. B. der Strom der Anlage.",
    ),
    "Wäschepflege": ([PUNKTE, WOHNUNG], "Gemeinschaftliche Waschmaschinen und Trockner."),
    "Sonstige Betriebskosten": (
        [FLAECHE, WOHNUNG, PUNKTE, INDIVIDUELL],
        "Nur umlagefähig, wenn die Kosten im Mietvertrag ausdrücklich genannt sind.",
    ),
}


def vorwaerts(apps, schema_editor):
    Abrechnungsbereich = apps.get_model("abrechnungen", "Abrechnungsbereich")
    Kostenart = apps.get_model("abrechnungen", "Kostenart")
    for alt, neu in BEREICHE_ALT_NEU.items():
        Abrechnungsbereich.objects.filter(verteilerschluessel=alt).update(verteilerschluessel=neu)
    for name, (schluessel, hinweis) in KATALOG.items():
        Kostenart.objects.filter(name=name, verteilerschluessel=[], hinweis="").update(
            verteilerschluessel=schluessel, hinweis=hinweis
        )


def rueckwaerts(apps, schema_editor):
    Abrechnungsbereich = apps.get_model("abrechnungen", "Abrechnungsbereich")
    for neu, alt in BEREICHE_NEU_ALT.items():
        Abrechnungsbereich.objects.filter(verteilerschluessel=neu).update(verteilerschluessel=alt)


class Migration(migrations.Migration):
    dependencies = [
        ("abrechnungen", "0003_verteilerschluessel_kostenarten"),
    ]

    operations = [
        migrations.RunPython(vorwaerts, rueckwaerts),
    ]
