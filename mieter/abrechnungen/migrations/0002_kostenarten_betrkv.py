"""Startwerte für den Kostenarten-Katalog nach § 2 Betriebskostenverordnung.

Einmalige Grundausstattung. Weitere Kostenarten legt man in der App oder im Admin an,
dafür ist keine Migration nötig.
"""

from django.db import migrations

KOSTENARTEN = [
    (1, "Grundsteuer", "Laufende öffentliche Lasten des Grundstücks"),
    (2, "Wasserversorgung", "Wasserverbrauch, Grundgebühren, Zählermiete"),
    (3, "Entwässerung", "Gebühren für Haus- und Grundstücksentwässerung"),
    (4, "Heizung", "Betrieb der zentralen Heizungsanlage"),
    (5, "Warmwasser", "Betrieb der zentralen Warmwasserversorgung"),
    (6, "Heizung und Warmwasser", "Verbundene Heizungs- und Warmwasserversorgungsanlagen"),
    (7, "Aufzug", "Betrieb des Personen- oder Lastenaufzugs"),
    (8, "Straßenreinigung", "Öffentliche Straßenreinigung"),
    (8, "Müllbeseitigung", "Müllabfuhr"),
    (9, "Gebäudereinigung", "Reinigung gemeinsam genutzter Gebäudeteile"),
    (9, "Ungezieferbekämpfung", ""),
    (10, "Gartenpflege", "Pflege gärtnerisch angelegter Flächen und Spielplätze"),
    (11, "Beleuchtung (Allgemeinstrom)", "Strom für Außen- und Treppenhausbeleuchtung"),
    (12, "Schornsteinreinigung", "Kehrgebühren"),
    (13, "Gebäudeversicherung", "Sachversicherung gegen Feuer-, Sturm-, Wasserschäden"),
    (13, "Haftpflichtversicherung", "Haftpflicht für Gebäude, Öltank und Aufzug"),
    (14, "Hauswart", ""),
    (15, "Antenne / Breitbandnetz", "Gemeinschafts-Antennenanlage oder Breitbandverteilnetz"),
    (16, "Wäschepflege", "Einrichtungen für die Wäschepflege"),
    (17, "Sonstige Betriebskosten", "Im Mietvertrag gesondert vereinbarte Kosten"),
]


def anlegen(apps, schema_editor):
    Kostenart = apps.get_model("abrechnungen", "Kostenart")
    for nummer, name, beschreibung in KOSTENARTEN:
        Kostenart.objects.get_or_create(
            name=name, defaults={"betrkv_nummer": nummer, "beschreibung": beschreibung}
        )


def entfernen(apps, schema_editor):
    Kostenart = apps.get_model("abrechnungen", "Kostenart")
    Kostenart.objects.filter(
        name__in=[name for _, name, _ in KOSTENARTEN], positionen__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("abrechnungen", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(anlegen, entfernen),
    ]
