"""Oberfläche für Wohnungen und Abrechnungen.

Zugriff:
- Lesen nur über objects.fuer_nutzer(): Fremde Daten ergeben 404.
- Schreiben nur über objects.verwaltbar_fuer(): Mitglieder mit „Nur lesen“ bekommen 403.

HTMX: Kostenpositionen und Vorauszahlungen werden in der Seite hinzugefügt und gelöscht.
Ohne JavaScript funktionieren dieselben Formulare mit normalem Neuladen.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import hilfe
from .forms import (
    AbrechnungForm,
    AbrechnungsbereichForm,
    BrennstoffbezugForm,
    KostenpositionForm,
    MitgliedNeuForm,
    RaumverbrauchForm,
    VorauszahlungForm,
    WohnungForm,
)
from .models import (
    Abrechnung,
    Abrechnungsbereich,
    Brennstoffbezug,
    Kostenposition,
    Mitgliedschaft,
    Raumverbrauch,
    Vorauszahlung,
    Wohnung,
)


def _lesen(modell, request, pk):
    return get_object_or_404(modell.objects.fuer_nutzer(request.user), pk=pk)


def _schreiben(modell, request, pk):
    objekt = _lesen(modell, request, pk)
    if not modell.objects.verwaltbar_fuer(request.user).filter(pk=pk).exists():
        raise PermissionDenied("Für diese Wohnung hast du nur Leserechte.")
    return objekt


def _darf_verwalten(wohnung, nutzer):
    return Wohnung.objects.verwaltbar_fuer(nutzer).filter(pk=wohnung.pk).exists()


# Wohnungen


def startseite(request):
    wohnungen = Wohnung.objects.fuer_nutzer(request.user).prefetch_related("abrechnungen")
    return render(request, "abrechnungen/startseite.html", {"wohnungen": wohnungen})


def wohnung_neu(request):
    form = WohnungForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            wohnung = form.save()
            Mitgliedschaft.objects.create(
                nutzer=request.user, wohnung=wohnung, rolle=Mitgliedschaft.Rolle.VERWALTEN
            )
        messages.success(request, f"Wohnung „{wohnung}“ angelegt.")
        return redirect("wohnung_detail", pk=wohnung.pk)
    return render(request, "abrechnungen/formular.html", {"form": form, "titel": "Neue Wohnung"})


def _wohnung_seite(request, wohnung, mitglied_form=None):
    darf = _darf_verwalten(wohnung, request.user)
    abrechnungen = wohnung.abrechnungen.all()  # Jahr absteigend (Meta.ordering)
    if darf and mitglied_form is None:
        mitglied_form = MitgliedNeuForm(wohnung=wohnung)
    return render(
        request,
        "abrechnungen/wohnung_detail.html",
        {
            "wohnung": wohnung,
            "ergebnisse": [(a, a.berechnen()) for a in abrechnungen],
            "darf_verwalten": darf,
            "mitglieder": wohnung.mitgliedschaften.select_related("nutzer").order_by(
                "rolle", "nutzer__email"
            ),
            "mitglied_form": mitglied_form,
            "rollen": Mitgliedschaft.Rolle.choices,
        },
    )


def wohnung_detail(request, pk):
    return _wohnung_seite(request, _lesen(Wohnung, request, pk))


def wohnung_bearbeiten(request, pk):
    wohnung = _schreiben(Wohnung, request, pk)
    form = WohnungForm(request.POST or None, instance=wohnung)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Wohnung gespeichert.")
        return redirect("wohnung_detail", pk=wohnung.pk)
    return render(
        request,
        "abrechnungen/formular.html",
        {"form": form, "titel": "Wohnung bearbeiten", "zurueck": wohnung},
    )


# Abrechnungen


def abrechnung_neu(request, wohnung_pk):
    wohnung = _schreiben(Wohnung, request, wohnung_pk)
    form = AbrechnungForm(request.POST or None, instance=Abrechnung(wohnung=wohnung))
    if request.method == "POST" and form.is_valid():
        abrechnung = form.save()
        messages.success(request, f"Abrechnung {abrechnung.abrechnungsjahr} angelegt.")
        return redirect("abrechnung_detail", pk=abrechnung.pk)
    return render(
        request,
        "abrechnungen/formular.html",
        {"form": form, "titel": f"Neue Abrechnung für {wohnung}", "zurueck": wohnung},
    )


def _detail_kontext(request, abrechnung, positionsformulare=None, vorauszahlungsformular=None):
    darf = _darf_verwalten(abrechnung.wohnung, request.user)
    positionsformulare = positionsformulare or {}
    bereiche = []
    for bereich in abrechnung.bereiche.prefetch_related("positionen__kostenart"):
        form = positionsformulare.get(bereich.pk)
        if form is None and darf:
            form = KostenpositionForm(
                instance=Kostenposition(bereich=bereich), prefix=f"b{bereich.pk}"
            )
        bereiche.append({"bereich": bereich, "form": form})
    if vorauszahlungsformular is None and darf:
        vorauszahlungsformular = VorauszahlungForm(
            instance=Vorauszahlung(abrechnung=abrechnung), prefix="vz"
        )
    return {
        "abrechnung": abrechnung,
        "wohnung": abrechnung.wohnung,
        "bereiche": bereiche,
        "vorauszahlungen": abrechnung.vorauszahlungen.select_related("bereich"),
        "vorauszahlungsformular": vorauszahlungsformular,
        "ergebnis": abrechnung.berechnen(),
        "darf_verwalten": darf,
    }


def abrechnung_detail(request, pk):
    abrechnung = _lesen(Abrechnung, request, pk)
    return render(
        request, "abrechnungen/abrechnung_detail.html", _detail_kontext(request, abrechnung)
    )


def abrechnung_bearbeiten(request, pk):
    abrechnung = _schreiben(Abrechnung, request, pk)
    form = AbrechnungForm(request.POST or None, instance=abrechnung)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Abrechnung gespeichert.")
        return redirect("abrechnung_detail", pk=abrechnung.pk)
    return render(
        request,
        "abrechnungen/formular.html",
        {"form": form, "titel": "Abrechnung bearbeiten", "zurueck": abrechnung},
    )


def abrechnung_loeschen(request, pk):
    abrechnung = _schreiben(Abrechnung, request, pk)
    if request.method == "POST":
        wohnung = abrechnung.wohnung
        abrechnung.delete()
        messages.success(request, f"Abrechnung {abrechnung.abrechnungsjahr} gelöscht.")
        return redirect("wohnung_detail", pk=wohnung.pk)
    return render(
        request,
        "abrechnungen/loeschen.html",
        {"objekt": abrechnung, "titel": "Abrechnung löschen", "zurueck": abrechnung},
    )


# Abrechnungsbereiche


def _bereich_formular(request, form, titel, abrechnung):
    return render(
        request,
        "abrechnungen/bereich_formular.html",
        {
            "form": form,
            "titel": titel,
            "zurueck": abrechnung,
            "mengenhilfe": [{"schluessel": s, "hilfe": h} for s, h in hilfe.MENGENHILFE.items()],
            "individuell_hilfe": hilfe.INDIVIDUELL_HILFE,
            "rundungsbeispiel": hilfe.rundungsbeispiel(),
            "beispiel": hilfe,
        },
    )


def bereich_neu(request, abrechnung_pk):
    abrechnung = _schreiben(Abrechnung, request, abrechnung_pk)
    vorgabe = {"reihenfolge": abrechnung.bereiche.count() + 1}
    if abrechnung.wohnung.wohnflaeche:
        vorgabe["anteil_menge"] = abrechnung.wohnung.wohnflaeche
    form = AbrechnungsbereichForm(
        request.POST or None,
        instance=Abrechnungsbereich(abrechnung=abrechnung),
        initial=vorgabe,
    )
    if request.method == "POST" and form.is_valid():
        bereich = form.save()
        messages.success(request, f"Bereich „{bereich}“ angelegt.")
        return redirect(
            reverse("abrechnung_detail", args=[abrechnung.pk]) + f"#bereich-{bereich.pk}"
        )
    return _bereich_formular(request, form, "Neuer Abrechnungsbereich", abrechnung)


def bereich_bearbeiten(request, pk):
    bereich = _schreiben(Abrechnungsbereich, request, pk)
    form = AbrechnungsbereichForm(request.POST or None, instance=bereich)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Bereich gespeichert.")
        return redirect(
            reverse("abrechnung_detail", args=[bereich.abrechnung_id]) + f"#bereich-{bereich.pk}"
        )
    return _bereich_formular(request, form, "Bereich bearbeiten", bereich.abrechnung)


def bereich_loeschen(request, pk):
    bereich = _schreiben(Abrechnungsbereich, request, pk)
    if request.method == "POST":
        abrechnung = bereich.abrechnung
        bereich.delete()
        messages.success(request, f"Bereich „{bereich}“ gelöscht.")
        return redirect("abrechnung_detail", pk=abrechnung.pk)
    return render(
        request,
        "abrechnungen/loeschen.html",
        {"objekt": bereich, "titel": "Bereich löschen", "zurueck": bereich.abrechnung},
    )


# Kostenpositionen und Vorauszahlungen (HTMX)


def _bereich_antwort(request, bereich, form=None):
    """Antwort nach einer Änderung an Positionen: Bereich neu, Ergebnis per Out-of-Band."""
    abrechnung = bereich.abrechnung
    if request.htmx:
        kontext = _detail_kontext(
            request, abrechnung, positionsformulare={bereich.pk: form} if form else None
        )
        eintrag = next(e for e in kontext["bereiche"] if e["bereich"].pk == bereich.pk)
        kontext.update(eintrag=eintrag, oob=True)
        return render(request, "abrechnungen/_bereich_antwort.html", kontext)
    if form is not None:
        kontext = _detail_kontext(request, abrechnung, positionsformulare={bereich.pk: form})
        return render(request, "abrechnungen/abrechnung_detail.html", kontext)
    return redirect(reverse("abrechnung_detail", args=[abrechnung.pk]) + f"#bereich-{bereich.pk}")


@require_POST
def position_neu(request, bereich_pk):
    bereich = _schreiben(Abrechnungsbereich, request, bereich_pk)
    form = KostenpositionForm(
        request.POST, instance=Kostenposition(bereich=bereich), prefix=f"b{bereich.pk}"
    )
    if form.is_valid():
        form.save()
        return _bereich_antwort(request, bereich)
    return _bereich_antwort(request, bereich, form=form)


@require_POST
def position_loeschen(request, pk):
    position = _schreiben(Kostenposition, request, pk)
    bereich = position.bereich
    position.delete()
    return _bereich_antwort(request, bereich)


def _vorauszahlungen_antwort(request, abrechnung, form=None):
    if request.htmx:
        kontext = _detail_kontext(request, abrechnung, vorauszahlungsformular=form)
        kontext["oob"] = True
        return render(request, "abrechnungen/_vorauszahlungen_antwort.html", kontext)
    if form is not None:
        kontext = _detail_kontext(request, abrechnung, vorauszahlungsformular=form)
        return render(request, "abrechnungen/abrechnung_detail.html", kontext)
    return redirect(reverse("abrechnung_detail", args=[abrechnung.pk]) + "#vorauszahlungen")


@require_POST
def vorauszahlung_neu(request, abrechnung_pk):
    abrechnung = _schreiben(Abrechnung, request, abrechnung_pk)
    form = VorauszahlungForm(
        request.POST, instance=Vorauszahlung(abrechnung=abrechnung), prefix="vz"
    )
    if form.is_valid():
        form.save()
        return _vorauszahlungen_antwort(request, abrechnung)
    return _vorauszahlungen_antwort(request, abrechnung, form=form)


@require_POST
def vorauszahlung_loeschen(request, pk):
    vorauszahlung = _schreiben(Vorauszahlung, request, pk)
    abrechnung = vorauszahlung.abrechnung
    vorauszahlung.delete()
    return _vorauszahlungen_antwort(request, abrechnung)


# Individuelle Umlage: eigene Seite mit Brennstoff-Bezügen und Verbrauch je Raum.
# Die Formulare dort laden per HTMX nur ihren Abschnitt neu (hx-select), ohne JavaScript
# die ganze Seite.


def _umlage(position):
    if not position.bereich.ist_individuell:
        raise Http404("Details gibt es nur für individuelle Umlagen.")
    return position


def _umlage_seite(request, position, form=None, brennstoff_form=None, raum_form=None):
    darf = _darf_verwalten(position.bereich.abrechnung.wohnung, request.user)
    if darf:
        form = form or KostenpositionForm(instance=position)
        brennstoff_form = brennstoff_form or BrennstoffbezugForm(
            instance=Brennstoffbezug(position=position)
        )
        raum_form = raum_form or RaumverbrauchForm(instance=Raumverbrauch(position=position))
    bezuege = position.brennstoffbezuege.all()
    summen = bezuege.aggregate(
        menge=Sum("menge_kwh"), betrag=Sum("betrag"), co2=Sum("vermieteranteil_co2")
    )
    if summen["betrag"] is not None:
        summen["brennstoffkosten"] = summen["betrag"] - summen["co2"]
    raeume = position.raumverbraeuche.all()
    return render(
        request,
        "abrechnungen/umlage_detail.html",
        {
            "position": position,
            "bereich": position.bereich,
            "abrechnung": position.bereich.abrechnung,
            "wohnung": position.bereich.abrechnung.wohnung,
            "darf_verwalten": darf,
            "form": form,
            "brennstoff_form": brennstoff_form,
            "raum_form": raum_form,
            "brennstoffbezuege": bezuege,
            "summen": summen,
            "raeume": raeume,
            "summe_einheiten": raeume.aggregate(summe=Sum("einheiten"))["summe"],
        },
    )


def _zur_umlage(position, abschnitt=""):
    return redirect(position.get_absolute_url() + (f"#{abschnitt}" if abschnitt else ""))


def position_detail(request, pk):
    position = _umlage(_lesen(Kostenposition, request, pk))
    return _umlage_seite(request, position)


@require_POST
def position_bearbeiten(request, pk):
    position = _umlage(_schreiben(Kostenposition, request, pk))
    form = KostenpositionForm(request.POST, instance=position)
    if form.is_valid():
        form.save()
        messages.success(request, "Umlage gespeichert.")
        return _zur_umlage(position)
    return _umlage_seite(request, position, form=form)


@require_POST
def brennstoff_neu(request, position_pk):
    position = _umlage(_schreiben(Kostenposition, request, position_pk))
    form = BrennstoffbezugForm(request.POST, instance=Brennstoffbezug(position=position))
    if form.is_valid():
        form.save()
        return _zur_umlage(position, "brennstoff")
    return _umlage_seite(request, position, brennstoff_form=form)


@require_POST
def brennstoff_loeschen(request, pk):
    bezug = _schreiben(Brennstoffbezug, request, pk)
    bezug.delete()
    return _zur_umlage(bezug.position, "brennstoff")


@require_POST
def raum_neu(request, position_pk):
    position = _umlage(_schreiben(Kostenposition, request, position_pk))
    form = RaumverbrauchForm(request.POST, instance=Raumverbrauch(position=position))
    if form.is_valid():
        form.save()
        return _zur_umlage(position, "raeume")
    return _umlage_seite(request, position, raum_form=form)


@require_POST
def raum_loeschen(request, pk):
    raum = _schreiben(Raumverbrauch, request, pk)
    raum.delete()
    return _zur_umlage(raum.position, "raeume")


# Mitglieder. Eine Wohnung behält immer mindestens ein Mitglied mit der Rolle „Verwalten“.

LETZTER_VERWALTER = (
    "Die Wohnung braucht mindestens ein Mitglied, das sie verwaltet. "
    "Gib zuerst jemand anderem die Rolle „Verwalten“."
)


def _mitglieder_sperren(wohnung_id):
    """Sperrt die Mitgliedschaften der Wohnung bis zum Ende der Transaktion.

    Verhindert, dass sich zwei Verwalter gleichzeitig gegenseitig entfernen.
    """
    list(Mitgliedschaft.objects.select_for_update().filter(wohnung_id=wohnung_id))


def _zu_mitgliedern(request, wohnung, kein_zugriff_mehr=False):
    if kein_zugriff_mehr:
        ziel = reverse("startseite")
        if request.htmx:
            return HttpResponse(headers={"HX-Redirect": ziel})
        return redirect(ziel)
    return redirect(reverse("wohnung_detail", args=[wohnung.pk]) + "#mitglieder")


@require_POST
def mitglied_neu(request, wohnung_pk):
    wohnung = _schreiben(Wohnung, request, wohnung_pk)
    form = MitgliedNeuForm(request.POST, wohnung=wohnung)
    if form.is_valid():
        mitglied = form.save()
        messages.success(
            request, f"{mitglied.nutzer.email} ist jetzt Mitglied ({mitglied.get_rolle_display()})."
        )
        return _zu_mitgliedern(request, wohnung)
    return _wohnung_seite(request, wohnung, mitglied_form=form)


@require_POST
def mitglied_rolle(request, pk):
    mitglied = _schreiben(Mitgliedschaft, request, pk)
    rolle = request.POST.get("rolle")
    if rolle not in Mitgliedschaft.Rolle.values:
        messages.error(request, "Unbekannte Rolle.")
        return _zu_mitgliedern(request, mitglied.wohnung)
    with transaction.atomic():
        _mitglieder_sperren(mitglied.wohnung_id)
        mitglied.refresh_from_db()
        if rolle == Mitgliedschaft.Rolle.LESEN and mitglied.ist_letzter_verwalter:
            messages.error(request, LETZTER_VERWALTER)
        elif rolle != mitglied.rolle:
            mitglied.rolle = rolle
            mitglied.save(update_fields=["rolle"])
            messages.success(
                request, f"{mitglied.nutzer.email}: Rolle „{mitglied.get_rolle_display()}“."
            )
    return _zu_mitgliedern(request, mitglied.wohnung)


def _entfernen(request, mitglied):
    """Entfernt das Mitglied, außer es ist der letzte Verwalter. Gibt True bei Erfolg."""
    with transaction.atomic():
        _mitglieder_sperren(mitglied.wohnung_id)
        if mitglied.ist_letzter_verwalter:
            messages.error(request, LETZTER_VERWALTER)
            return False
        mitglied.delete()
    return True


@require_POST
def mitglied_entfernen(request, pk):
    mitglied = _schreiben(Mitgliedschaft, request, pk)
    wohnung = mitglied.wohnung
    if _entfernen(request, mitglied):
        selbst = mitglied.nutzer_id == request.user.pk
        if selbst:
            messages.success(request, f"Du hast „{wohnung}“ verlassen.")
        else:
            messages.success(request, f"{mitglied.nutzer.email} ist kein Mitglied mehr.")
        return _zu_mitgliedern(request, wohnung, kein_zugriff_mehr=selbst)
    return _zu_mitgliedern(request, wohnung)


@require_POST
def wohnung_verlassen(request, pk):
    wohnung = _lesen(Wohnung, request, pk)
    mitglied = wohnung.mitgliedschaften.get(nutzer=request.user)
    if _entfernen(request, mitglied):
        messages.success(request, f"Du hast „{wohnung}“ verlassen.")
        return _zu_mitgliedern(request, wohnung, kein_zugriff_mehr=True)
    return _zu_mitgliedern(request, wohnung)
