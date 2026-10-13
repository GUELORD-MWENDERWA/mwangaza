import { expect, test } from "@playwright/test";

import { allowCodeAgain, shell } from "./django";
import {
  activateTwoFactor,
  enterCode,
  enterPassword,
  ITIG,
  mainMenu,
  PASSWORD,
  skipGuide,
  VOLCANS,
} from "./helpers";

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
  // « Se souvenir de cet appareil », cochée : clé créée par le navigateur, appareil enregistré.
  await expect(page.getByText("cet appareil", { exact: true })).toBeVisible();

  // Téléphone : menu tiroir, fermé après un choix.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(mainMenu(page)).toBeHidden();
  await page.getByRole("button", { name: "Ouvrir le menu" }).click();
  const drawer = page.getByRole("dialog", { name: "Menu principal" });
  await drawer.getByRole("link", { name: "Impayés", exact: true }).click();
  await expect(drawer).toBeHidden();
  await expect(page.getByRole("heading", { name: "Impayés" })).toBeVisible();
  await expect(page.getByText("Montant échu FC")).toBeVisible();
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
  allowCodeAgain("+243000001005");
  await page.goto(ITIG);
  await enterPassword(page, "0000001005");
  await enterCode(page);
  await expect(page.getByText("Guide du caissier · étape 1 sur 5")).toBeVisible();
  await skipGuide(page);

  const menu = mainMenu(page);
  await expect(menu.getByRole("link", { name: "Caisse", exact: true })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Frais et barèmes" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "Journal d'audit" })).toHaveCount(0);

  await page.goto(`${ITIG}fees`);
  await expect(page.getByText("Vous n'avez pas accès à cette page")).toBeVisible();
});

test("démonstration : pas de code ; espace d'essai : double authentification obligatoire (M1)", async ({
  page,
}) => {
  // Espace de démonstration : le promoteur entre sans code, avec un rôle qui l'exige ailleurs.
  await page.goto(ITIG);
  await enterPassword(page, "0000001007");
  await expect(page.getByRole("heading", { name: /^Bonjour/ })).toBeVisible();
  await expect(mainMenu(page).getByRole("link", { name: "Journal d'audit" })).toBeVisible();

  // Le même rôle dans un espace d'essai (créé ici, hors de la plage de numéros réservée).
  shell(`from apps.accounts import services
from apps.accounts.models import Membership, Role, User
from apps.accounts.roles import starter_role_name
from apps.core.tenancy import use_school
from apps.schools.models import School
school, _ = School.objects.get_or_create(
    code="essaie2e", defaults={"name": "Espace d'essai (parcours)", "environment": "test"}
)
user = User.objects.filter(phone="+243100001007").first()
user = user or User(phone="+243100001007", last_name="Essai")
user.set_password("${PASSWORD}")
user.must_change_password = False
user.save()
services.reset_totp(user)
membership, _ = Membership.objects.get_or_create(user=user, school=school)
with use_school(school):
    membership.roles.set([Role.objects.get(name=starter_role_name("promoter"))])
`);
  await page.goto("http://essaie2e.localhost:5173/app/");
  await enterPassword(page, "0100001007");

  await activateTwoFactor(page);

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

  // Sans aucun droit, il lit ce que tout le personnel lit (5.7) : annonces de l'école, calendrier.
  await page.getByRole("link", { name: "Annonces au personnel" }).click();
  await expect(page.getByText("Conseil des enseignants de fin de période")).toBeVisible();
  await page.getByRole("button", { name: /Changer d'école/ }).click();
  await expect(
    page.getByRole("menuitem", { name: "Complexe scolaire Les Volcans (fictif)" }),
  ).toHaveAttribute("href", VOLCANS);
  await page.getByRole("menuitem", { name: "Toutes mes écoles…" }).click();

  await expect(page.getByRole("heading", { name: "Choisir l'école" })).toBeVisible();
  await expect(page.getByText("actuelle")).toBeVisible();
});
