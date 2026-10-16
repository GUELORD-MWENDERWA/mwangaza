import { expect, test } from "@playwright/test";

import { enterCode, enterPassword, ITIG, mainMenu } from "./helpers";

test("super-admin : session support « en tant qu'école » (A3)", async ({ page }) => {
  // Lien « Ouvrir en tant qu'école » de la console (ou de l'administration Django).
  await page.goto(`${ITIG}support`);
  await enterPassword(page, "0000000000");
  await enterCode(page);

  await expect(page.getByRole("heading", { name: "Ouvrir une session support" })).toBeVisible();
  await page.getByRole("button", { name: "Ouvrir la session support" }).click();
  await expect(page.getByText("Indiquez le motif.")).toBeVisible();
  await page.getByLabel("Motif").fill("Parcours de test : vérifier les rôles");
  await page.getByRole("button", { name: "Ouvrir la session support" }).click();

  const banner = page.getByRole("region", { name: "Session support" });
  await expect(banner).toContainText("vous agissez en tant que ITIG DON BOSCO");
  await expect(banner).toContainText("Motif : Parcours de test : vérifier les rôles");
  // Droits de l'école sauf la caisse.
  await expect(mainMenu(page).getByRole("link", { name: "Paramètres de l'école" })).toBeVisible();
  await expect(mainMenu(page).getByRole("link", { name: "Caisse", exact: true })).toHaveCount(0);

  // Bandeau sur tous les écrans.
  await page.goto(`${ITIG}account`);
  await expect(banner).toBeVisible();

  await banner.getByRole("button", { name: "Quitter" }).click();
  await expect(page.getByRole("heading", { name: "Ouvrir une session support" })).toBeVisible();
  await expect(banner).toHaveCount(0);
});
