import { expect, type Page } from "@playwright/test";

import { totp } from "./django";

export const PASSWORD = "mwangaza-demo";
export const ITIG = "http://itig-demo.localhost:5173/app/";
export const VOLCANS = "http://volcans.localhost:5173/app/";

/** Connexion avec le numéro et le mot de passe (étape 1). */
export async function enterPassword(page: Page, phone: string, password = PASSWORD) {
  await page.getByLabel("Numéro de téléphone").fill(phone);
  await page.getByLabel("Mot de passe", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Se connecter" }).click();
}

/** Étape du code (compte qui a déjà activé la double authentification). */
export async function enterCode(page: Page) {
  await expect(page.getByRole("heading", { name: "Code de vérification" })).toBeVisible();
  await page.getByLabel("Code à 6 chiffres").fill(await totp());
  await page.getByRole("button", { name: "Vérifier" }).click();
}

/** Première connexion avec un mot de passe provisoire : la personne choisit le sien. */
export async function choosePassword(page: Page, password: string) {
  await expect(page.getByRole("heading", { name: "Choisir votre mot de passe" })).toBeVisible();
  await page.getByLabel("Nouveau mot de passe").fill(password);
  await page.getByLabel("Confirmer").fill(password);
  await page.getByRole("button", { name: "Enregistrer le mot de passe" }).click();
}

/** Activation obligatoire de la double authentification : clé lue à l'écran (comme la personne
 *  qui ne peut pas scanner), code du moment, codes de secours confirmés. Renvoie la clé. */
export async function activateTwoFactor(page: Page): Promise<string> {
  await expect(page.getByText("Étape obligatoire")).toBeVisible();
  const key = (await page.getByText(/^([A-Z2-7]{4} ?)+$/).innerText()).replace(/\s/g, "");
  await page.getByLabel("Code à 6 chiffres").fill(await totp(key));
  await page.getByRole("button", { name: "Vérifier et activer" }).click();
  const finish = page.getByRole("button", { name: "Terminer" });
  await expect(finish).toBeDisabled();
  await page.getByText("J'ai imprimé ou recopié mes 8 codes de secours").click();
  await finish.click();
  return key;
}

/** Guide de première connexion (caissier, comptable) : « Passer le guide », comme le ferait
 *  quelqu'un qui le connaît déjà. */
export async function skipGuide(page: Page) {
  await page.getByRole("dialog").getByRole("button", { name: "Passer le guide" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

export function mainMenu(page: Page) {
  return page.getByRole("navigation", { name: "Menu principal" }).first();
}
