import { expect, test } from "@playwright/test";

import { enterPassword, ITIG } from "./helpers";

test("conduite sans réseau : deux infractions gardées sur l'appareil, envoyées une seule fois au retour du réseau (HL.2)", async ({
  page,
  context,
}) => {
  const mark = Date.now().toString(36);
  const notes = [`Téléphone en classe ${mark}`, `Retard au rang ${mark}`];
  await page.addInitScript(() => {
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  await page.goto(`${ITIG}conduct`);
  await enterPassword(page, "0000001008");
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  const student = page.getByLabel("Élève");
  // La classe et l'historique de l'élève lus en ligne restent sur l'appareil.
  await expect(student.locator("option").nth(1)).toBeAttached();
  await student.selectOption({ index: 1 });
  const name = (await student.locator("option:checked").textContent())!;
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByText(/Aucun incident|période :/).first()).toBeVisible();

  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  for (const note of notes) {
    await page.getByLabel("Note (facultative)").fill(note);
    await page.getByRole("button", { name: "Enregistrer l'infraction" }).click();
    await expect(
      page.getByText("Infraction gardée sur cet appareil", { exact: false }),
    ).toBeVisible();
  }
  await expect(page.getByText(/2 infractions attendent le réseau/)).toBeVisible();
  await expect(page.getByText("En attente du réseau")).toHaveCount(2);

  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(page.getByText(/attendent? le réseau/)).toHaveCount(0);

  // Le serveur a les deux infractions, une seule fois chacune : l'historique relu est le sien.
  await page.reload();
  await page.getByLabel("Élève").selectOption({ label: name });
  for (const note of notes) await expect(page.getByText(note)).toHaveCount(1);
  await expect(page.getByText("En attente du réseau")).toHaveCount(0);
});
