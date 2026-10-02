import { expect, type Page } from "@playwright/test";

import { totp } from "./django";

export const PASSWORD = "mwangaza-demo";
export const ITIG = "http://itig.localhost:5173/app/";
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

/** Guide de première connexion (caissier, comptable) : « Passer le guide », comme le ferait
 *  quelqu'un qui le connaît déjà. */
export async function skipGuide(page: Page) {
  await page.getByRole("dialog").getByRole("button", { name: "Passer le guide" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

export function mainMenu(page: Page) {
  return page.getByRole("navigation", { name: "Menu principal" }).first();
}
