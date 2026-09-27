import { expect, test } from "@playwright/test";

import { allowCodeAgain } from "./django";
import { enterCode, enterPassword, ITIG, mainMenu, VOLCANS } from "./helpers";

// Numéro jamais utilisé par `make demo` (+243 0000 8xxxx), différent à chaque passage : le compte
// créé reste dans la base de développement.
const newPhone = () => `00000${80000 + Math.floor(Math.random() * 9999)}`;

test("directeur des études : organisation scolaire, classe ajoutée puis retirée, matricule", async ({
  page,
}) => {
  await page.goto(`${ITIG}organisation`);
  await enterPassword(page, "0000001002");

  await expect(page.getByRole("heading", { name: "Organisation scolaire" })).toBeVisible();
  await expect(page.getByLabel("Année", { exact: true }).locator("option:checked")).toHaveText(
    "Année : 2026-2027 (en cours)",
  );
  const terms = page.locator("section", { has: page.getByRole("heading", { name: "Découpage" }) });
  await expect(
    terms.getByRole("row", { name: /1re période 07\/09\/2026 07\/11\/2026/ }),
  ).toBeVisible();
  await expect(terms.getByRole("row", { name: /Examens du 2e semestre/ })).toBeVisible();

  await page.getByRole("tab", { name: "Classes" }).click();
  const classes = page.locator("section", {
    has: page.getByRole("heading", { name: "Classes 2026-2027" }),
  });
  await expect(classes.getByText("23 classes")).toBeVisible();
  await classes.getByRole("button", { name: "Ajouter une classe" }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Niveau").selectOption({ label: "4e" });
  await dialog.getByLabel("Option").selectOption({ label: "Électricité" });
  await dialog.getByLabel("Section").fill("b");
  await dialog.getByLabel("Capacité").fill("40");
  await dialog.getByRole("button", { name: "Ajouter" }).click();
  await expect(classes.getByText("24 classes")).toBeVisible();

  await classes.getByRole("button", { name: "Ouvrir la classe 4e Électricité B" }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Supprimer la classe" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Supprimer" }).click();
  await expect(classes.getByText("23 classes")).toBeVisible();

  await page.getByRole("tab", { name: "Matricule" }).click();
  const format = page.getByLabel("Modèle");
  await format.fill("ITIG/{AA}/{0000}");
  await expect(page.getByText("ITIG/26/0001")).toBeVisible();
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("Format enregistré.")).toBeVisible();
  await format.fill("ITIG-{AAAA}-{0000}");
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("ITIG-2026-0001")).toBeVisible();

  // Pas de droit sur les comptes ni le journal.
  await expect(mainMenu(page).getByRole("link", { name: "Comptes du personnel" })).toHaveCount(0);
});

test("directeur : compte, rôle et couleur changés, puis lus dans le journal", async ({ page }) => {
  allowCodeAgain("+243000001001");
  await page.goto(`${ITIG}staff`);
  await enterPassword(page, "0000001001");
  await enterCode(page);

  // Nouveau compte : mot de passe provisoire affiché une fois.
  const phone = newPhone();
  const create = page.locator("section", {
    has: page.getByRole("heading", { name: "Nouveau compte" }),
  });
  await create.getByLabel("Numéro de téléphone").fill(phone);
  const lastName = `Essai${phone.slice(-4)}`;
  await create.getByLabel("Nom", { exact: true }).fill(lastName);
  await create.getByLabel("Prénom").fill("Parcours");
  await create.getByRole("checkbox", { name: "Secrétaire" }).click();
  await create.getByRole("button", { name: "Créer le compte" }).click();
  const password = page.getByRole("dialog", { name: "Mot de passe provisoire" });
  await expect(password.locator("code")).toHaveText(/^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$/);
  await password.getByRole("button", { name: "J'ai noté le mot de passe" }).click();
  await expect(page.getByRole("heading", { name: `Parcours ${lastName}` })).toBeVisible();

  // Rôle créé, permission cochée, puis supprimé (personne ne l'a).
  await mainMenu(page).getByRole("link", { name: "Rôles et permissions" }).click();
  await page.getByRole("button", { name: "Nouveau rôle" }).click();
  await page.getByRole("dialog").getByLabel("Nom du rôle").fill(`Surveillant ${phone}`);
  await page.getByRole("dialog").getByRole("button", { name: "Créer le rôle" }).click();
  await page.getByRole("checkbox", { name: "Voir les élèves" }).click();
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("Rôle enregistré.")).toBeVisible();
  await page.getByRole("button", { name: "Supprimer le rôle" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Supprimer le rôle" }).click();
  await expect(page.getByRole("button", { name: new RegExp(`Surveillant ${phone}`) })).toHaveCount(
    0,
  );

  // Couleur illisible : teinte voisine proposée (même calcul que le serveur), puis remise.
  await mainMenu(page).getByRole("link", { name: "Paramètres de l'école" }).click();
  const color = page.getByLabel("Couleur de l'école");
  await color.fill("#FF0000");
  await page.getByRole("button", { name: "Utiliser #ED0000" }).click();
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("Paramètres enregistrés.")).toBeVisible();
  await color.fill("#003C6C");
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("Paramètres enregistrés.")).toBeVisible();

  // Journal : les actions du parcours, les plus récentes d'abord.
  await mainMenu(page).getByRole("link", { name: "Journal d'audit" }).click();
  const rows = page.getByRole("row");
  await expect(rows.nth(1)).toContainText("Paramètres de l'école modifiés");
  await expect(rows.nth(1)).toContainText("Patrice Muhindo Kambale");
  await expect(page.getByRole("row", { name: /Rôle supprimé/ }).first()).toBeVisible();
  await page
    .getByRole("row", { name: new RegExp(`Compte ajouté.*${lastName} Parcours`) })
    .getByRole("button")
    .click();
  const detail = page.locator("section", {
    has: page.getByRole("heading", { name: "Compte ajouté" }),
  });
  await expect(detail.getByRole("row", { name: "Rôles — Secrétaire" })).toBeVisible();
  await expect(detail.getByRole("row", { name: "Nouveau compte — Oui" })).toBeVisible();
});

test("isolation : Volcans ne voit que ses classes", async ({ page }) => {
  allowCodeAgain("+243000002001");
  await page.goto(`${VOLCANS}organisation`);
  await enterPassword(page, "0000002001");
  await enterCode(page);

  await page.getByRole("tab", { name: "Classes" }).click();
  await expect(page.getByText("4 classes")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ouvrir la classe 1re Scientifique A" }),
  ).toBeVisible();
  await expect(page.getByText("Électricité")).toHaveCount(0);
  await page.getByRole("tab", { name: "Matricule" }).click();
  await expect(page.getByLabel("Modèle")).toHaveValue("LV/{AA}/{0000}");
});
