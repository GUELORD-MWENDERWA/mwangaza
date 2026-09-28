import { expect, test } from "@playwright/test";

import { manage } from "./django";
import { enterCode, enterPassword, ITIG } from "./helpers";

/** Un élève de la démonstration qui n'a encore rien payé et doit des frais en dollars. */
function unpaidStudent(): { matricule: string; name: string } {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig")):
    e = (Enrollment.objects.filter(status="active", payments__isnull=True, charges__currency="USD",
         charges__status="active").select_related("student").order_by("student__matricule").first())
    print(e.student.matricule, "|", e.student.last_name.upper(), e.student.middle_name.upper(), e.student.first_name)`,
  );
  // Dernière ligne : le shell annonce d'abord ses imports automatiques.
  const [matricule, name] = output.trim().split("\n").at(-1)!.split(" | ");
  return { matricule: matricule!, name: name!.replace(/\s+/g, " ") };
}

test("caissière : ouvre sa caisse, encaisse, voit le paiement du jour", async ({ page }) => {
  const student = unpaidStudent();
  await page.goto(`${ITIG}cash`);
  await enterPassword(page, "0000001005");
  await enterCode(page);

  // `make demo` a clôturé les sessions : la caisse s'ouvre.
  await expect(page.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();
  await page.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();
  await expect(page.getByText(/Session ouverte à .* · 0 paiement$/)).toBeVisible();

  await page.getByLabel("Élève qui paie").fill(student.matricule);
  await page.getByRole("button", { name: new RegExp(student.matricule) }).click();
  await page.getByLabel("Montant reçu en USD").fill("10");
  await expect(page.getByText("Répartition")).toBeVisible();
  // Double appui : un seul paiement (identifiant donné par l'appareil, bouton bloqué).
  await page.keyboard.press("F9");
  await page.keyboard.press("F9");

  await expect(page.getByText(/^Paiement enregistré : reçu ITIG-C\d-26-\d{6}\.$/)).toBeVisible();
  const today = page.locator("section", {
    has: page.getByRole("heading", { name: "Paiements du jour" }),
  });
  await expect(
    today.getByRole("row", { name: new RegExp(`${student.name}.*10,00`, "i") }),
  ).toHaveCount(1);
  await expect(page.getByText(/Session ouverte à .* · 1 paiement$/)).toBeVisible();
});
