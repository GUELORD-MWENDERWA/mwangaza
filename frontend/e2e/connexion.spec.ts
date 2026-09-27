import { expect, test } from "@playwright/test";

import { shell, totp } from "./django";
import { enterCode, enterPassword, ITIG, mainMenu, VOLCANS } from "./helpers";

test("directeur : mot de passe puis code, menu complet, Mon compte, menu tiroir", async ({
  page,
}) => {
  await page.goto(`${ITIG}account`);
  await expect(page).toHaveURL(/\/app\/login\?next=%2Faccount$/);
  await expect(page.getByRole("heading", { name: "ITIG Don Bosco Goma (démo)" })).toBeVisible();

  await enterPassword(page, "0000001001");
  await enterCode(page);

  await expect(page.getByRole("heading", { name: "Mon compte" })).toBeVisible();
  const menu = mainMenu(page);
  for (const entry of ["Tableau de bord", "Élèves", "Frais et barèmes", "Journal d'audit"]) {
    await expect(menu.getByRole("link", { name: entry, exact: true })).toBeVisible();
  }
  await expect(menu.getByRole("link", { name: "Caisse", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Nouveaux codes de secours" })).toBeVisible();

  // Téléphone : menu tiroir, fermé après un choix.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(mainMenu(page)).toBeHidden();
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  const drawer = page.getByRole("dialog", { name: "Menu principal" });
  await drawer.getByRole("link", { name: "Impayés", exact: true }).click();
  await expect(drawer).toBeHidden();
  await expect(page.getByText("« Impayés » n'est pas encore disponible")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  // Isolation : la session de l'ITIG ne vaut pas à l'adresse d'une autre école, qui montre son
  // nom (aussi sur téléphone).
  await page.goto(VOLCANS);
  await expect(page.getByRole("heading", { name: "Se connecter" })).toBeVisible();
  await expect(
    page.getByText("Complexe scolaire Les Volcans (fictif)").filter({ visible: true }),
  ).toHaveCount(1);
});

test("caissière : seulement la caisse ; un écran interdit ouvert par son adresse → 403", async ({
  page,
}) => {
  await page.goto(ITIG);
  await enterPassword(page, "0000001005");
  await enterCode(page);

  const menu = mainMenu(page);
  await expect(menu.getByRole("link", { name: "Caisse", exact: true })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Frais et barèmes" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "Journal d'audit" })).toHaveCount(0);

  await page.goto(`${ITIG}fees`);
  await expect(page.getByText("Vous n'avez pas accès à cette page")).toBeVisible();
});

test("promoteur : activation obligatoire de la double authentification (M1)", async ({ page }) => {
  await page.goto(ITIG);
  await enterPassword(page, "0000001007");

  await expect(page.getByText("Étape obligatoire")).toBeVisible();
  const key = (await page.getByText(/^([A-Z2-7]{4} ?)+$/).innerText()).replace(/\s/g, "");
  await page.getByLabel("Code à 6 chiffres").fill(await totp(key));
  await page.getByRole("button", { name: "Vérifier et activer" }).click();

  const finish = page.getByRole("button", { name: "Terminer" });
  await expect(finish).toBeDisabled();
  await page.getByText("J'ai imprimé ou recopié mes 8 codes de secours").click();
  await finish.click();

  await expect(page.getByRole("heading", { name: /^Bonjour/ })).toBeVisible();
  await expect(mainMenu(page).getByRole("link", { name: "Journal d'audit" })).toBeVisible();
});

test("mot de passe provisoire : la personne choisit le sien", async ({ page }) => {
  shell(
    "from apps.accounts.models import User; u = User.objects.get(phone='+243000001006'); " +
      "u.set_password('provisoire-e2e-1'); u.must_change_password = True; u.save()",
  );
  await page.goto(ITIG);
  await enterPassword(page, "0000001006", "provisoire-e2e-1");

  await expect(page.getByRole("heading", { name: "Choisir votre mot de passe" })).toBeVisible();
  await page.getByLabel("Nouveau mot de passe").fill("court");
  await page.getByLabel("Confirmer").fill("court");
  await page.getByRole("button", { name: "Enregistrer le mot de passe" }).click();
  await expect(page.getByText("Au moins 10 caractères.").first()).toBeVisible();

  await page.getByLabel("Nouveau mot de passe").fill("secretaire-nouveau-2026");
  await page.getByLabel("Confirmer").fill("secretaire-nouveau-2026");
  await page.getByRole("button", { name: "Enregistrer le mot de passe" }).click();

  await expect(page.getByRole("heading", { name: /^Bonjour/ })).toBeVisible();
});

test("enseignant dans deux écoles : changer d'école (M2)", async ({ page }) => {
  await page.goto(ITIG);
  await enterPassword(page, "0000001008");

  await expect(page.getByText(/ne donne encore accès à aucun écran/)).toBeVisible();
  await page.getByRole("button", { name: /Changer d'école/ }).click();
  await expect(
    page.getByRole("menuitem", { name: "Complexe scolaire Les Volcans (fictif)" }),
  ).toHaveAttribute("href", VOLCANS);
  await page.getByRole("menuitem", { name: "Toutes mes écoles…" }).click();

  await expect(page.getByRole("heading", { name: "Choisir l'école" })).toBeVisible();
  await expect(page.getByText("actuelle")).toBeVisible();
});
