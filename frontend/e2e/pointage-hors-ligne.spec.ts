import { expect, test } from "@playwright/test";

import { scansToday, studentsToScan } from "./django";
import { enterPassword, ITIG } from "./helpers";

test("pointage sans réseau : deux élèves gardés sur l'appareil, envoyés une seule fois au retour du réseau (6.3)", async ({
  page,
  context,
}) => {
  const [first, second] = studentsToScan();
  expect(first && second).toBeTruthy();
  await page.addInitScript(() => {
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  await page.goto(`${ITIG}entrance`);
  await enterPassword(page, "0000001006");
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  // La liste des élèves et des cartes gardée sur l'appareil sert hors ligne.
  await page.getByRole("radio", { name: "Borne / matricule" }).click();
  await expect(page.getByLabel("Lecteur USB ou matricule")).toBeVisible();

  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  const field = page.getByLabel("Lecteur USB ou matricule");
  for (const matricule of [first!, second!]) {
    await field.fill(matricule);
    await field.press("Enter");
  }
  // Un deuxième passage du même élève n'ajoute rien.
  await field.fill(first!);
  await field.press("Enter");
  await expect(page.getByText("Déjà passé").first()).toBeVisible();
  expect(scansToday(first!)).toBe(0);

  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect.poll(() => scansToday(first!), { timeout: 30_000 }).toBe(1);
  expect(scansToday(second!)).toBe(1);

  // Un rechargement ne renvoie rien : toujours un seul pointage chacun.
  await page.reload();
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  expect(scansToday(first!)).toBe(1);
  expect(scansToday(second!)).toBe(1);
});
