// Captures du produit pour le site public (`make captures-site`, WEB.1b) : de vrais écrans sur
// les données de `make demo`, la Gestion sans son menu latéral (1 184 x 740), le Portail au
// téléphone (390 x 844). PNG dans `apercu/captures/produit/`, puis `webp.py` les met en WebP dans
// `backend/apps/core/static/core/site/captures/`. Ouvre une session de caisse sans rien encaisser,
// refermée à la fin. Ne tourne qu'avec `APERCU=produit`.
import { mkdirSync } from "node:fs";

import { type Browser, type Page, test } from "@playwright/test";

import { allowCodeAgain, closeCashSessions, manage, unpaidStudent } from "../e2e/django";
import { enterCode, enterPassword, ITIG } from "../e2e/helpers";

const OUT = new URL("./captures/produit/", import.meta.url).pathname;
const PORTAL = "http://localhost:5174/";
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const TABLET = { width: 820, height: 1180 };
// Menu latéral de la Gestion : hors de la capture.
const SIDEBAR = 256;

test.skip(process.env.APERCU !== "produit", "seulement pour make captures-site");

/** Le guide de première connexion, s'il s'ouvre. */
async function skipGuide(page: Page) {
  const skip = page.getByRole("dialog").getByRole("button", { name: "Passer le guide" });
  if (await skip.isVisible().catch(() => false)) await skip.click();
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
}

/** Bandeaux du moment (annonce de la plateforme, code PIN proposé) : fermés avant la photo. */
async function clearBanners(page: Page) {
  // Bandeau « Démonstration — données fictives » : jamais sur une image du site.
  await page
    .addStyleTag({ content: '[role="note"]{display:none !important}' })
    .catch(() => undefined);
  for (let round = 0; round < 6; round++) {
    let closed = false;
    for (const name of ["Fermer", "Plus tard"]) {
      const button = page.getByRole("button", { name, exact: true }).first();
      if (await button.isVisible().catch(() => false)) {
        await button.click();
        await page.waitForTimeout(300);
        closed = true;
      }
    }
    if (!closed) break;
  }
}

async function desk(page: Page, name: string) {
  await settle(page);
  await clearBanners(page);
  await page.screenshot({
    path: `${OUT}${name}.png`,
    clip: { x: SIDEBAR, y: 0, width: DESKTOP.width - SIDEBAR, height: 740 },
  });
}

async function phone(page: Page, name: string) {
  await page.setViewportSize(MOBILE);
  await settle(page);
  await clearBanners(page);
  await page.screenshot({ path: `${OUT}${name}-mobile.png` });
  await page.setViewportSize(DESKTOP);
}

/** Gestion à la taille d'une tablette ou d'un téléphone : la page entière, menu compris. */
async function device(page: Page, size: typeof MOBILE, name: string) {
  await page.setViewportSize(size);
  await settle(page);
  await clearBanners(page);
  await page.screenshot({ path: `${OUT}${name}.png` });
  await page.setViewportSize(DESKTOP);
}

/** Le premier élève de la démonstration qui a une photo de profil (`students/demo_photos.py`). */
function studentWithPhoto(): string {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Student
with use_school(School.objects.get(code="itig-demo")):
    print("RESULT", Student.objects.exclude(photo="").order_by("matricule").first().pk)`,
  );
  return output.trim().split("\n").at(-1)!.split(" ")[1]!;
}

async function staff(browser: Browser, number: string, withCode: boolean, path = "") {
  const context = await browser.newContext({ viewport: DESKTOP });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.print = () => undefined;
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  if (withCode) allowCodeAgain(`+243${number.slice(1)}`);
  await page.goto(`${ITIG}${path}`);
  await enterPassword(page, number);
  if (withCode) await enterCode(page);
  await page.waitForURL((url) => !url.pathname.includes("login"));
  await settle(page);
  await skipGuide(page);
  return page;
}

/** Un cours déjà noté de la démonstration, sur la première période (ouvert par la directrice des
 *  études, qui peut saisir dans tous les cours). */
function gradedSheet(): string {
  const output = manage(
    "shell",
    "-c",
    `from apps.academics.models import GradeSheet
from apps.core.tenancy import use_school
from apps.schools.models import School
with use_school(School.objects.get(code="itig-demo")):
    sheets = GradeSheet.objects.filter(term__kind="period").order_by(
        "term__order", "course__class_group__level__order", "course__order")
    sheet = (sheets.filter(status="draft").first()
             or sheets.filter(submitted_by__isnull=False).first() or sheets.first())
    print("RESULT", sheet.course_id, sheet.term_id)`,
  );
  const [, course, term] = output.trim().split("\n").at(-1)!.split(" ");
  return `grades?course=${course}&term=${term}`;
}

test("captures du produit pour le site public", async ({ browser }) => {
  mkdirSync(OUT, { recursive: true });

  const head = await staff(browser, "0000001001", true);
  for (const [path, name] of [
    ["dashboard", "gestion-tableau-de-bord"],
    ["unpaid", "gestion-impayes"],
    ["fees", "gestion-frais-baremes"],
  ] as const) {
    await head.goto(`${ITIG}${path}`);
    await desk(head, name);
  }

  await head.goto(`${ITIG}students/${studentWithPhoto()}`);
  await desk(head, "gestion-eleve");
  await head.goto(`${ITIG}dashboard`);
  await device(head, TABLET, "gestion-tableau-de-bord-tablette");
  await head.goto(`${ITIG}dashboard`);
  await device(head, MOBILE, "gestion-tableau-de-bord-mobile");

  const director = await staff(browser, "0000001002", true, gradedSheet());
  // La feuille de notes se charge après la page : attendre que les barres grises disparaissent.
  await director
    .waitForFunction(() => !document.querySelector(".animate-pulse"), undefined, { timeout: 15000 })
    .catch(() => undefined);
  await desk(director, "gestion-notes-saisie");

  // Caisse : ouverture, puis un encaissement préparé mais jamais envoyé, puis la clôture
  // affichée mais pas validée.
  closeCashSessions();
  const cashier = await staff(browser, "0000001005", true, "cash");
  await desk(cashier, "gestion-caisse-ouverture");
  await cashier.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();
  await desk(cashier, "gestion-caisse-accueil");
  const student = unpaidStudent();
  await cashier.getByLabel("Élève qui paie").fill(student.matricule);
  await cashier.getByRole("button", { name: new RegExp(student.matricule) }).click();
  await cashier.getByLabel("Montant reçu en USD").fill("150");
  await desk(cashier, "gestion-caisse-encaissement");
  await phone(cashier, "gestion-caisse");
  await cashier.reload();
  await settle(cashier);
  await cashier.getByRole("button", { name: "Clôturer la caisse" }).click();
  await desk(cashier, "gestion-caisse-cloture");
  closeCashSessions();

  const parentContext = await browser.newContext({ viewport: { width: 1184, height: 740 } });
  const parent = await parentContext.newPage();
  await parent.goto(`${PORTAL}login`);
  await enterPassword(parent, "0002000001");
  await parent.waitForURL((url) => !url.pathname.includes("login"));
  const families = await parent.evaluate(async () => (await fetch("/api/portal/families/")).json());
  const child = (families as { children: { id: string }[] }[])[0]!.children[0]!;
  await parent.goto(`${PORTAL}children/${child.id}`);
  await settle(parent);
  await parent.screenshot({ path: `${OUT}portail-enfant-paiements.png` });
  await parent.setViewportSize(TABLET);
  await parent.goto(`${PORTAL}children/${child.id}`);
  await settle(parent);
  await parent.screenshot({ path: `${OUT}portail-enfant-tablette.png` });
  await parent.setViewportSize(MOBILE);
  for (const [path, name] of [
    ["", "portail-accueil"],
    [`children/${child.id}`, "portail-enfant-paiements"],
    ["announcements", "portail-annonces"],
    ["calendar", "portail-calendrier"],
    ["notifications", "portail-notifications"],
  ] as const) {
    await parent.goto(`${PORTAL}${path}`);
    await settle(parent);
    await parent.screenshot({ path: `${OUT}${name}-mobile.png` });
  }
});
