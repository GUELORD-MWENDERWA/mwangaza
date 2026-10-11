import { expect, test } from "@playwright/test";

import { allowCodeAgain } from "./django";
import { enterCode, enterPassword } from "./helpers";

const CONSOLE = "http://admin.localhost:5175/";
const ADMIN = "0000000000";

test("super-admin : console de la plateforme, mot de passe puis code, tableau de bord", async ({
  page,
}) => {
  allowCodeAgain("+243000000000");
  await page.goto(CONSOLE);
  await expect(page).toHaveURL(/\/login$/);

  // Un compte d'école (le directeur de l'ITIG) est refusé comme un mauvais mot de passe.
  await enterPassword(page, "0000001001");
  await expect(page.getByText("Numéro de téléphone ou mot de passe incorrect.")).toBeVisible();

  await enterPassword(page, ADMIN);
  await enterCode(page);
  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
  await expect(page.getByText("Écoles actives")).toBeVisible();
  await expect(page.getByText("Santé du serveur")).toBeVisible();
  // Les écoles de `make demo` sont des espaces de démonstration : hors des chiffres du tableau de
  // bord, rangées sous leur onglet.
  await expect(page.getByText("ITIG Don Bosco Goma (démo)")).toHaveCount(0);
  await page.getByRole("link", { name: "Écoles", exact: true }).first().click();
  await page.getByRole("tab", { name: "Démonstration" }).click();
  await expect(page.getByText("ITIG Don Bosco Goma (démo)")).toBeVisible();
  // Le parcours suivant du super-admin peut reprendre le même code.
  allowCodeAgain("+243000000000");
});
