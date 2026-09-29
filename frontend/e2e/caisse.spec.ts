import { expect, test } from "@playwright/test";

import { allowCodeAgain, manage } from "./django";
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

/** Paiements de l'élève enregistrés sur le serveur (numéros de reçus) et ce qu'il a payé en
 *  dollars d'après son solde. */
function serverPayments(matricule: string): { receipts: string[]; paidUsd: number } {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import Payment
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig")):
    e = Enrollment.objects.get(student__matricule="${matricule}", status="active")
    receipts = Payment.objects.filter(enrollment=e).order_by("receipt_number").values_list("receipt_number", flat=True)
    usd = next(c for c in services.balance(services.charges_of(e.pk)).currencies if c.currency == "USD")
    print(" ".join(receipts), "|", usd.paid_minor)`,
  );
  const [receipts, paid] = output.trim().split("\n").at(-1)!.split(" | ");
  return { receipts: receipts!.split(" "), paidUsd: Number(paid) };
}

test("caissière : ouvre sa caisse, encaisse en ligne puis sans réseau, aucun doublon au retour (3.5.1)", async ({
  page,
  context,
}) => {
  const student = unpaidStudent();
  // Pas de fenêtre d'impression : on garde ce qui serait imprimé. Stockage persistant accordé
  // (Chromium sans écran le refuse : la caisse serait bloquée, M8).
  await page.addInitScript(() => {
    window.print = () => {
      document.body.dataset.prints = String(Number(document.body.dataset.prints ?? 0) + 1);
      document.body.dataset.printed = document.querySelector(".print-area")?.textContent ?? "";
    };
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  // La caissière se connecte aussi dans d'autres parcours : un code ne sert qu'une fois.
  allowCodeAgain("+243000001005");
  await page.goto(`${ITIG}cash`);
  // « Se souvenir de cet appareil » est cochée par défaut : la caisse travaille sur l'appareil.
  await enterPassword(page, "0000001005");
  await enterCode(page);
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });

  // `make demo` a clôturé les sessions : la caisse s'ouvre (en ligne).
  await expect(page.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();
  await page.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();
  await expect(page.getByText(/Session ouverte à .* · 0 paiement$/)).toBeVisible();

  const recorded = page.getByText(/^Paiement enregistré : reçu ITIG-P\d+-26-\d{6}\.$/);
  async function collect(amount: string): Promise<string> {
    await page.getByLabel("Élève qui paie").fill(student.matricule);
    await page.getByRole("button", { name: new RegExp(student.matricule) }).click();
    await page.getByLabel("Montant reçu en USD").fill(amount);
    await expect(page.getByText("Répartition")).toBeVisible();
    // Double appui : un seul paiement (identifiant donné par l'appareil, bouton bloqué).
    await page.keyboard.press("F9");
    await page.keyboard.press("F9");
    await expect(recorded).toBeVisible();
    return (await recorded.textContent())!.match(/ITIG-P\d+-26-\d{6}/)![0];
  }

  const first = await collect("10");
  // Un seul reçu imprimé, avec le montant en lettres.
  const body = page.locator("body");
  await expect(body).toHaveAttribute("data-printed", new RegExp(`Reçu n° ${first}.*Dix dollars`));
  await expect(body).toHaveAttribute("data-prints", "1");
  await expect(indicator).toHaveText("En ligne · à jour");

  // Réseau coupé : on encaisse toujours, reçus imprimés avec les numéros suivants de l'appareil.
  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  const second = await collect("5");
  await expect(body).toHaveAttribute("data-prints", "2");
  const third = await collect("5");
  await expect(body).toHaveAttribute("data-prints", "3");
  const seq = (number: string) => Number(number.slice(-6));
  expect([seq(second), seq(third)]).toEqual([seq(first) + 1, seq(first) + 2]);
  await expect(indicator).toHaveText("Hors ligne · 2 en attente");
  const today = page.locator("section", {
    has: page.getByRole("heading", { name: "Paiements du jour" }),
  });
  await expect(today.getByRole("row", { name: /en attente/ })).toHaveCount(2);
  await expect(page.getByText(/Session ouverte à .* · 3 paiements$/)).toBeVisible();

  // Retour du réseau : envoyés une seule fois, soldes justes sur le serveur.
  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(today.getByRole("row", { name: /en attente/ })).toHaveCount(0);
  await expect(
    today.getByRole("row", { name: new RegExp(`${student.name}.*enregistré`, "i") }),
  ).toHaveCount(3);
  expect(serverPayments(student.matricule)).toEqual({
    receipts: [first, second, third],
    paidUsd: 2000,
  });
});
