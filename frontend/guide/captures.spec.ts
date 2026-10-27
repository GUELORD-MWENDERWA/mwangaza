import { mkdirSync, readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { allowCodeAgain, manage, unpaidStudent } from "../e2e/django";
import { enterCode, ITIG, PASSWORD, skipGuide } from "../e2e/helpers";

// Version du guide et nom de la plateforme, écrits dans la page (`data-guide`) et dans le nom du
// PDF. La version est celle de la Gestion (`apps/gestion/package.json`, affichée au pied de son
// menu) : un seul endroit à changer à la fin d'une version. Le nom vient des paramètres de la
// plateforme (5.1) ; ici seulement, pas dans le texte.
const { version: appVersion } = JSON.parse(
  readFileSync(new URL("../apps/gestion/package.json", import.meta.url), "utf8"),
) as { version: string };
const VERSION = appVersion.split(".").slice(0, 2).join(".");

const CAPTURES = new URL("captures/", import.meta.url).pathname;
// Deux documents, mêmes captures : le guide de la version (pour les écoles) et le guide de
// présentation (pour la personne qui montre la plateforme : commandes, comptes, déroulé).
const DOCUMENTS = [
  { html: "guide.html", pdf: "guide", title: "guide de la version" },
  { html: "presentation.html", pdf: "presentation", title: "guide de présentation, version" },
];
// Domaine du vrai serveur, écrit dans le guide de présentation.
const DOMAIN = "mwangazaschool.com";
const PORTAL = "http://localhost:5174/";
const CONSOLE = "http://admin.localhost:5175/";

test.describe.configure({ mode: "serial" });
test.beforeAll(() => mkdirSync(CAPTURES, { recursive: true }));

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${CAPTURES}${name}.jpg`, type: "jpeg", quality: 72 });
}

/** Écran chargé : plus de requête en cours, titre affiché, synchronisation terminée. */
async function settle(page: Page) {
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /Synchronisation/ })).toHaveCount(0, {
    timeout: 30_000,
  });
}

async function open(page: Page, path: string, name: string) {
  await page.goto(`${ITIG}${path}`);
  await settle(page);
  await shot(page, name);
}

/** Connexion à la Gestion de l'ITIG (code de double authentification si le compte l'a). */
async function login(page: Page, phone: string, { code = false, remember = false } = {}) {
  if (code) allowCodeAgain(`+243${phone.slice(1)}`);
  await page.goto(ITIG);
  await page.getByLabel("Numéro de téléphone").fill(phone);
  await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
  if (!remember) await page.getByLabel("Se souvenir de cet appareil").uncheck();
  await page.getByRole("button", { name: "Se connecter" }).click();
  if (code) await enterCode(page);
  await page.waitForURL((url) => !url.pathname.includes("/login"));
}

/** Un élève inscrit qui a déjà payé et a une réduction : sa fiche montre tout. */
function studentWithHistory(): string {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig-demo")):
    e = (Enrollment.objects.filter(status="active", payments__isnull=False, discounts__isnull=False)
         .order_by("student__matricule").first())
    print(e.student_id)`,
  );
  return output.trim().split("\n").at(-1)!;
}

test("connexion", async ({ page }) => {
  await page.goto(ITIG);
  await expect(page.getByRole("button", { name: "Se connecter" })).toBeVisible();
  await shot(page, "connexion");
});

test("directeur", async ({ page }) => {
  await login(page, "0000001001", { code: true });
  await open(page, "dashboard", "directeur-tableau-de-bord");
  await open(page, "settings", "directeur-parametres");
  await open(page, "roles", "directeur-roles");
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, "dashboard", "tableau-de-bord-telephone");
  await page.setViewportSize({ width: 1280, height: 720 });
});

test("promoteur", async ({ page }) => {
  await login(page, "0000001007");
  // Double authentification : étape obligatoire à la première connexion d'un rôle sensible dans
  // un espace réel. Un espace de démonstration ne la demande pas : on la montre depuis « Mon
  // compte », au format téléphone pour la colonne du guide.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${ITIG}account/two-factor`);
  await settle(page);
  await shot(page, "double-authentification");
  await page.setViewportSize({ width: 1280, height: 720 });
  await open(page, "unpaid", "promoteur-impayes");
  await open(page, "audit", "promoteur-audit");
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, "unpaid", "impayes-telephone");
  await page.setViewportSize({ width: 1280, height: 720 });
});

test("comptable", async ({ page }) => {
  await login(page, "0000001004", { code: true });
  await skipGuide(page);
  await open(page, "fees", "comptable-frais");
  await open(page, `students/${studentWithHistory()}/finances`, "comptable-finances-eleve");
  await open(page, "cancellations", "comptable-annulations");
  await open(page, "cash-closings", "comptable-clotures");
});

test("caissière", async ({ page, context }) => {
  const student = unpaidStudent();
  // Stockage persistant accordé (Chromium sans écran le refuse, M8). Impression : copie du reçu
  // gardée dans la page pour la capture, sans fenêtre d'impression.
  await page.addInitScript(() => {
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
    window.print = () => {
      const area = document.querySelector(".print-area");
      if (!area) return;
      document.getElementById("guide-print")?.remove();
      const copy = area.cloneNode(true) as HTMLElement;
      copy.id = "guide-print";
      copy.className = "";
      copy.hidden = true;
      Object.assign(copy.style, { width: "fit-content", padding: "12px", background: "#fff" });
      document.body.append(copy);
    };
  });
  await login(page, "0000001005", { code: true, remember: true });
  await skipGuide(page);
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();
  await shot(page, "caisse-ouverture");
  await page.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();

  const recorded = page.getByText(/^Paiement enregistré : reçu /);
  async function collect(amount: string, name?: string) {
    await page.getByLabel("Élève qui paie").fill(student.matricule);
    await page.getByRole("button", { name: new RegExp(student.matricule) }).click();
    await page.getByLabel("Montant reçu en USD").fill(amount);
    await expect(page.getByText("Répartition")).toBeVisible();
    if (name) await shot(page, name);
    await page.keyboard.press("F9");
    await expect(recorded).toBeVisible();
  }
  await collect("50", "caisse-encaissement");
  const receipt = page.locator("#guide-print");
  await receipt.evaluate((copy) => (copy.hidden = false));
  await receipt.screenshot({ path: `${CAPTURES}caisse-recu.jpg`, type: "jpeg", quality: 85 });
  await receipt.evaluate((copy) => copy.remove());

  // Sans réseau : la caisse continue, le paiement attend la synchronisation.
  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  await collect("20");
  await expect(indicator).toHaveText(/Hors ligne · \d+ en attente/);
  await shot(page, "caisse-hors-ligne");
  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });

  await page.getByRole("button", { name: "Clôturer la caisse" }).click();
  await page.getByLabel("Argent compté en USD").fill("70");
  await page.getByLabel("Argent compté en FC").fill("0");
  await shot(page, "caisse-cloture");
});

test("secrétaire", async ({ page }) => {
  await login(page, "0000001006");
  await open(page, "students", "secretaire-eleves");
  await open(page, `students/${studentWithHistory()}`, "secretaire-fiche-eleve");
  await open(page, "students/import", "secretaire-import");
  await open(page, "students/invitations", "secretaire-invitations");
  // Au téléphone : une carte par élève (tableau empilé), filtres repliés.
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, "students", "eleves-telephone");
  await page.setViewportSize({ width: 1280, height: 720 });
});

test("directrice des études", async ({ page }) => {
  await login(page, "0000001002");
  await open(page, "organisation", "etudes-organisation");
  await open(page, "courses", "etudes-cours");
  await open(page, "teaching-loads", "etudes-charges");
});

test("directeur de discipline", async ({ page }) => {
  await login(page, "0000001003");
  await open(page, "announcements", "discipline-annonces");
  await open(page, "calendar", "communication-calendrier");
  await open(page, "summons", "communication-convocations");
});

test("enseignant dans deux écoles", async ({ page }) => {
  await login(page, "0000001008");
  await open(page, "schools", "enseignant-ecoles");
});

test.describe("parent", () => {
  test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true });

  test("portail", async ({ page }) => {
    await page.goto(`${PORTAL}login`);
    await page.getByLabel("Numéro de téléphone").fill("0002000001");
    await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Se connecter" }).click();
    // Connexion finie avant la capture : sinon c'est l'écran de connexion qui est pris.
    await page.waitForURL((url) => !url.pathname.includes("/login"));
    await page.waitForLoadState("networkidle");
    const skip = page.getByRole("button", { name: "Passer le guide" });
    if (await skip.isVisible()) await skip.click();
    await settle(page);
    await shot(page, "parent-enfants");
    await page.getByRole("link").filter({ hasText: /ITIG/ }).first().click();
    await expect(page.getByRole("heading", { name: "Détail des frais" })).toBeVisible();
    await settle(page);
    await shot(page, "parent-paiements");
    await page.goto(`${PORTAL}announcements`);
    await settle(page);
    await shot(page, "parent-annonces");
    await page.goto(`${PORTAL}calendar`);
    await expect(page.getByText(/L'école vous attend pour/)).toBeVisible();
    await settle(page);
    await shot(page, "parent-calendrier");
  });
});

test("portail sur ordinateur", async ({ page }) => {
  await page.goto(`${PORTAL}login`);
  await page.getByLabel("Numéro de téléphone").fill("0002000001");
  await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"));
  await page.waitForLoadState("networkidle");
  const skip = page.getByRole("button", { name: "Passer le guide" });
  if (await skip.isVisible()) await skip.click();
  await settle(page);
  await shot(page, "parent-ordinateur");
});

test("super-admin", async ({ page }) => {
  // Console de la plateforme : les espaces par type, puis le choix du type à la création.
  allowCodeAgain("+243000000000");
  await page.goto(CONSOLE);
  await page.getByLabel("Numéro de téléphone").fill("0000000000");
  await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await enterCode(page);
  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
  await page.goto(`${CONSOLE}schools`);
  await page.getByRole("tab", { name: "Démonstration" }).click();
  await expect(page.getByText("ITIG DON BOSCO")).toBeVisible();
  await page.waitForLoadState("networkidle");
  await shot(page, "console-ecoles");
  // Modules de l'école (M.2) : la carte seule, sur la fiche de l'école.
  await page.getByRole("link", { name: "ITIG DON BOSCO" }).click();
  const modules = page
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Fonctions de l'école" }) })
    .last();
  await expect(modules.getByRole("checkbox").first()).toBeVisible();
  await modules.screenshot({ path: `${CAPTURES}console-modules.jpg`, type: "jpeg", quality: 80 });
  await page.goto(`${CONSOLE}schools/new`);
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading").first()).toBeVisible();
  await shot(page, "console-nouvelle-ecole");

  allowCodeAgain("+243000000000");
  await page.goto(`${ITIG}support`);
  await page.getByLabel("Numéro de téléphone").fill("0000000000");
  await page.getByLabel("Mot de passe", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await enterCode(page);
  await page.getByLabel("Motif").fill("Aider la comptable à corriger un barème");
  await page.getByRole("button", { name: "Ouvrir la session support" }).click();
  await open(page, "dashboard", "support-session");
});

test("PDF", async ({ page, request }) => {
  // Nom de la plateforme : celui de ses paramètres (5.1), comme dans les applications.
  const { name: platform } = (await (
    await request.get("http://localhost:8000/api/platform/")
  ).json()) as { name: string };
  const today = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long" }).format(new Date());
  const domain = DOMAIN;
  for (const { html, pdf, title } of DOCUMENTS) {
    await page.goto(new URL(html, import.meta.url).href);
    await page.evaluate(
      (values) => {
        for (const node of document.querySelectorAll<HTMLElement>("[data-guide]"))
          node.textContent = values[node.dataset.guide as keyof typeof values];
        document.title = `${values.platform} — ${values.title} ${values.version}`;
      },
      { version: VERSION, platform, date: today, domain, title },
    );
    await page.evaluate(() => document.fonts.ready);
    // Toutes les captures présentes.
    const missing = await page.$$eval("img", (images) =>
      images.filter((image) => !image.naturalWidth).map((image) => image.getAttribute("src")),
    );
    expect(missing).toEqual([]);
    await page.pdf({
      path: new URL(`../../docs/guide/${pdf}-v${VERSION}.pdf`, import.meta.url).pathname,
      format: "A4",
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: "<span></span>",
      footerTemplate: `<div style="width:100%;font-size:8px;color:#77818f;padding:0 14mm;display:flex;justify-content:space-between"><span>${platform} — ${title} ${VERSION}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
      margin: { top: "14mm", bottom: "16mm", left: "14mm", right: "14mm" },
    });
  }
});
