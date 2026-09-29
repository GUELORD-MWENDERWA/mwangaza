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

/** Paiements de l'élève enregistrés sur le serveur (numéros de reçus), ce qu'il a payé en
 *  dollars d'après son solde, et les duplicatas notés au journal à l'heure de l'appareil. */
function serverPayments(matricule: string): {
  receipts: string[];
  paidUsd: number;
  reprints: number;
} {
  const output = manage(
    "shell",
    "-c",
    `from apps.audit.models import AuditLog
from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import Payment
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig")):
    e = Enrollment.objects.get(student__matricule="${matricule}", status="active")
    payments = Payment.objects.filter(enrollment=e).order_by("receipt_number")
    receipts = payments.values_list("receipt_number", flat=True)
    usd = next(c for c in services.balance(services.charges_of(e.pk)).currencies if c.currency == "USD")
    reprints = AuditLog.objects.filter(action="finance.payment_reprinted", entity_id__in=payments.values("pk"), device_time__isnull=False).count()
    print(" ".join(receipts), "|", usd.paid_minor, "|", reprints)`,
  );
  const [receipts, paid, reprints] = output.trim().split("\n").at(-1)!.split(" | ");
  return { receipts: receipts!.split(" "), paidUsd: Number(paid), reprints: Number(reprints) };
}

test("caissière sans réseau : ouvre sa caisse, encaisse deux fois, réimprime ; reçus vérifiables, aucun doublon au retour (3.5)", async ({
  page,
  context,
  request,
}) => {
  const student = unpaidStudent();
  // Pas de fenêtre d'impression : on garde ce qui serait imprimé. Stockage persistant accordé
  // (Chromium sans écran le refuse : la caisse serait bloquée, M8).
  await page.addInitScript(() => {
    window.print = () => {
      document.body.dataset.prints = String(Number(document.body.dataset.prints ?? 0) + 1);
      document.body.dataset.printed = document.querySelector(".print-area")?.textContent ?? "";
      const qr = document.querySelector<HTMLElement>(".print-area .receipt__qr");
      document.body.dataset.qr = qr?.dataset.url ?? "";
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

  // `make demo` a clôturé les sessions. Réseau coupé : la caisse s'ouvre sur l'appareil.
  await expect(page.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();
  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
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

  // Reçus imprimés aussitôt, numéros consécutifs de l'appareil, montant en lettres.
  const first = await collect("10");
  const body = page.locator("body");
  await expect(body).toHaveAttribute("data-printed", new RegExp(`Reçu n° ${first}.*Dix dollars`));
  await expect(body).toHaveAttribute("data-prints", "1");
  const firstQr = (await body.getAttribute("data-qr"))!;
  const second = await collect("5");
  await expect(body).toHaveAttribute("data-prints", "2");
  expect(Number(second.slice(-6))).toBe(Number(first.slice(-6)) + 1);

  // Duplicata sans réseau, imprimé sur l'appareil.
  const today = page.locator("section", {
    has: page.getByRole("heading", { name: "Paiements du jour" }),
  });
  await today.getByRole("button", { name: `Réimprimer le reçu ${first}` }).click();
  await expect(body).toHaveAttribute("data-prints", "3");
  await expect(body).toHaveAttribute("data-printed", new RegExp(`Duplicata.*Reçu n° ${first}`));
  await expect(indicator).toHaveText("Hors ligne · 4 en attente");
  await expect(today.getByRole("row", { name: /en attente/ })).toHaveCount(2);

  // Le QR code signé par l'appareil suffit à vérifier le reçu avant la synchronisation.
  expect(firstQr).toContain(`n=${first}`);
  const verify = async () => (await request.get(firstQr)).text();
  expect(await verify()).toContain("Reçu authentique, en attente de synchronisation");
  expect(await (await request.get(firstQr.replace("a=1000", "a=10000"))).text()).toContain(
    "Reçu falsifié",
  );

  // Retour du réseau : ouverture, paiements et duplicata envoyés une seule fois.
  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(today.getByRole("row", { name: /en attente/ })).toHaveCount(0);
  await expect(
    today.getByRole("row", { name: new RegExp(`${student.name}.*enregistré`, "i") }),
  ).toHaveCount(2);
  await expect(page.getByText(/Session ouverte à .* · 2 paiements$/)).toBeVisible();
  expect(serverPayments(student.matricule)).toEqual({
    receipts: [first, second],
    paidUsd: 1500,
    reprints: 1,
  });
  expect(await verify()).toContain("Reçu authentique</h1>");
});
