// Formular „Abrechnungsbereich“: zeigt nur die Hilfe und Felder, die zur Auswahl passen.
// Ohne JavaScript bleibt alles sichtbar.
document.addEventListener("DOMContentLoaded", () => {
  const formular = document.querySelector("form.bereich-formular");
  if (!formular) return;
  const schluessel = formular.querySelector('[name="verteilerschluessel"]');
  const regel = () => formular.querySelector('[name="rundungsregel"]:checked')?.value;

  const aktualisieren = () => {
    const individuell = schluessel.value === "individuell";
    formular.querySelectorAll("[data-schluessel]").forEach((el) => {
      el.hidden = el.dataset.schluessel !== schluessel.value;
    });
    formular.querySelectorAll("[data-nur-mengen]").forEach((el) => {
      el.hidden = individuell;
    });
    formular.querySelectorAll("[data-nur-n-stellen]").forEach((el) => {
      el.hidden = individuell || regel() !== "n_stellen";
    });
  };

  formular.addEventListener("change", aktualisieren);
  aktualisieren();
});
