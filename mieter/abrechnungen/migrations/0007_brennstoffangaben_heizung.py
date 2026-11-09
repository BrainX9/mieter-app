"""Heizung und „Heizung und Warmwasser“ erfassen Brennstoff-/Energiekosten mit CO₂-Anteil."""

from django.db import migrations

MIT_BRENNSTOFF = ["Heizung", "Heizung und Warmwasser"]


def vorwaerts(apps, schema_editor):
    Kostenart = apps.get_model("abrechnungen", "Kostenart")
    Kostenart.objects.filter(name__in=MIT_BRENNSTOFF).update(brennstoffangaben=True)


class Migration(migrations.Migration):
    dependencies = [
        ("abrechnungen", "0006_individuelle_umlage"),
    ]

    operations = [
        migrations.RunPython(vorwaerts, migrations.RunPython.noop),
    ]
