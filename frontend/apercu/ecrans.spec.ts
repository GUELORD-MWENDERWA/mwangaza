// Aperçu de tous les écrans à trois largeurs (`make apercu`) : captures dans `apercu/captures/`
// (<app>/<largeur>/<écran>.png) et `rapport.json` (éléments qui dépassent de l'écran).
import { mkdirSync, writeFileSync } from "node:fs";

import { type Browser, type Page, test } from "@playwright/test";

import { allowCodeAgain } from "../e2e/django";
import { enterCode, enterPassword, ITIG } from "../e2e/helpers";

const OUT = new URL("./captures/", import.meta.url).pathname;
const WIDTHS = [
  { width: 390, height: 844 },
  { width: 820, height: 1180 },
  { width: 1440, height: 900 },
];
const PORTAL = "http://localhost:5174/";
const CONSOLE = "http://admin.localhost:5175/";
const SITE = "http://localhost:8000/";
// Une seule application ou un seul écran : `APERCU=gestion` ou `APERCU=gestion/dashboard`.
const ONLY = process.env.APERCU ?? "";
const report: Record<string, string[]> = {};

/** Éléments qui dépassent à droite de l'écran hors d'un conteneur qui défile (3 au plus). */
function overflow() {
  const width = window.innerWidth;
  const out: string[] = [];
  for (const el of document.body.querySelectorAll("*")) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.right <= width + 1) continue;
    let parent = el.parentElement;
    while (
      parent &&
      parent !== document.body &&
      !["auto", "scroll", "hidden"].includes(getComputedStyle(parent).overflowX)
    ) {
      parent = parent.parentElement;
    }
    if (parent && parent !== document.body) continue;
    const cls = typeof el.className === "string" ? el.className.trim().split(/\s+/)[0] : "";
    out.push(
      `${el.tagName.toLowerCase()}${cls ? `.${cls}` : ""} +${Math.round(rect.right - width)} px`,
    );
  }
  const page = document.documentElement.scrollWidth - width;
  return [...out.slice(0, 3), ...(page > 1 ? [`page +${page} px`] : [])];
}

async function shoot(page: Page, app: string, name: string) {
  for (const size of WIDTHS) {
    await page.setViewportSize(size);
    await page.waitForTimeout(300);
    const dir = `${OUT}${app}/${size.width}`;
    mkdirSync(dir, { recursive: true });
    await page.screenshot({ path: `${dir}/${name}.png`, fullPage: true });
    const found = await page.evaluate(overflow);
    if (found.length) report[`${app}/${size.width}/${name}`] = found;
  }
}

async function visit(
  page: Page,
  url: string,
  app: string,
  name: string,
  before?: (page: Page) => Promise<void>,
) {
  if (ONLY && !`${app}/${name}`.startsWith(ONLY) && ONLY !== app) return;
  await page.setViewportSize(WIDTHS[2]!);
  await page.goto(url);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
  await before?.(page);
  await shoot(page, app, name);
}

async function skipGuide(page: Page) {
  const skip = page.getByRole("dialog").getByRole("button", { name: "Passer le guide" });
  if (await skip.isVisible().catch(() => false)) await skip.click();
}

async function json<T>(page: Page, url: string): Promise<T> {
  return page.evaluate(async (path) => (await fetch(path)).json(), url) as Promise<T>;
}

async function staff(browser: Browser, phone: string, withCode: boolean) {
  const page = await (await browser.newContext()).newPage();
  if (withCode) allowCodeAgain(`+243${phone.slice(1)}`);
  await page.goto(ITIG);
  await enterPassword(page, phone);
  if (withCode) await enterCode(page);
  await page.waitForURL((url) => !url.pathname.includes("login"));
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await skipGuide(page);
  return page;
}

test("tous les écrans à 390, 820 et 1440 px", async ({ browser }) => {
  const guest = await (await browser.newContext()).newPage();
  await visit(guest, `${ITIG}login`, "gestion", "connexion");
  await visit(guest, `${PORTAL}login`, "portail", "connexion");
  await visit(guest, `${PORTAL}activate`, "portail", "activation");
  await visit(guest, `${PORTAL}forgot-password`, "portail", "mot-de-passe-oublie");
  await visit(guest, `${CONSOLE}login`, "console", "connexion");
  // Site public de la plateforme (WEB.1b), rendu par Django ; animations réduites : les sections
  // qui apparaissent au défilement sont toutes visibles sur la capture pleine page.
  await guest.emulateMedia({ reducedMotion: "reduce" });
  for (const [path, name] of [
    ["", "accueil"],
    ["ecoles/", "ecoles"],
    ["parents/", "parents"],
    ["modules/", "modules"],
    ["demonstration/", "demonstration"],
    ["trouver-mon-ecole/", "trouver-mon-ecole"],
    ["mentions-legales/", "mentions"],
    ["en/", "accueil-en"],
    ["en/schools/", "ecoles-en"],
  ] as const) {
    await visit(guest, `${SITE}${path}`, "site", name, async (page) => {
      // Images en chargement différé : on descend jusqu'en bas pour qu'elles arrivent.
      for (let y = 0; y < (await page.evaluate(() => document.body.scrollHeight)); y += 600) {
        await page.evaluate((top) => window.scrollTo(0, top), y);
        await page.waitForTimeout(60);
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForLoadState("networkidle").catch(() => undefined);
    });
  }
  await guest.emulateMedia({ reducedMotion: null });

  if (!ONLY || ONLY.startsWith("gestion")) {
    const head = await staff(browser, "0000001001", true);
    const pages = [
      "",
      "dashboard",
      "students",
      "students/new",
      "students/class-list",
      "students/invitations",
      "students/import",
      "courses",
      "teaching-loads",
      "time-grid",
      "rooms",
      "timetable-checks",
      "timetable",
      "timetable/calculate",
      "unpaid",
      "unpaid/export",
      "cash-closings/register",
      "fees",
      "fees/prior-payments",
      "cancellations",
      "cash-closings",
      "credits",
      "staff-news",
      "calendar",
      "announcements",
      "summons",
      "parent-requests",
      "promotion",
      "settings",
      "organisation",
      "staff",
      "roles",
      "devices",
      "audit",
      "account",
      "notifications",
      "platform-news",
    ];
    for (const path of pages)
      await visit(head, `${ITIG}${path}`, "gestion", path.replace(/\//g, "-") || "accueil");
    // Éditeur de l'horaire (EDT.2b) : vues par enseignant, par salle, horaire général.
    for (const view of ["teacher", "room", "all"])
      await visit(head, `${ITIG}timetable?view=${view}`, "gestion", `timetable-${view}`);
    // Publication (EDT.4a) : la version publiée de make demo en lecture, la fenêtre « Publier ».
    await visit(head, `${ITIG}timetable`, "gestion", "timetable-published", async (page) => {
      const select = page.getByLabel("Brouillon");
      const value = await select.locator("option", { hasText: "publiée" }).getAttribute("value");
      await select.selectOption(value ?? "");
      await page.getByText("Lecture seule").first().waitFor();
    });
    await visit(head, `${ITIG}timetable`, "gestion", "timetable-publish", async (page) => {
      await page.getByRole("button", { name: "Publier", exact: true }).click();
      await page.getByRole("dialog").waitFor();
    });
    // Emploi du temps (EDT.1b) : vue « Emploi du temps » des cours, fenêtre des disponibilités.
    await visit(head, `${ITIG}courses`, "gestion", "courses-placement", async (page) => {
      await page.getByRole("radio", { name: "Emploi du temps" }).click();
    });
    await visit(
      head,
      `${ITIG}teaching-loads`,
      "gestion",
      "teaching-loads-disponibilites",
      async (page) => {
        await page
          .getByRole("button", { name: /^Régler les disponibilités/ })
          .first()
          .click();
        await page.getByRole("dialog").waitFor();
      },
    );
    const { results } = await json<{ results: { id: string }[] }>(
      head,
      "/api/students/?page_size=1",
    );
    const id = results[0]!.id;
    for (const tab of ["", "/family", "/finances", "/history", "/statement", "/form"]) {
      await visit(head, `${ITIG}students/${id}${tab}`, "gestion", `eleve${tab.replace("/", "-")}`);
    }
    const families = await json<{ results: { id: string }[] }>(head, "/api/families/?page_size=1");
    await visit(head, `${ITIG}families/${families.results[0]!.id}`, "gestion", "famille");
    const cashier = await staff(browser, "0000001005", true);
    await visit(cashier, `${ITIG}cash`, "gestion", "caisse");
    // Saisie des notes (8.2.1) : l'enseignant, sur ses cours.
    const teacher = await staff(browser, "0000001008", false);
    await visit(teacher, `${ITIG}grades`, "gestion", "grades");
    // Ma classe (NB.3) : le titulaire, dans la classe qui attend une dernière fiche.
    const own = await json<{ classes: { id: string; name: string }[] }>(teacher, "/api/homeroom/");
    const titular = own.classes.find((item) => item.name === "3HT ÉLECTRICITÉ A") ?? own.classes[0];
    await visit(teacher, `${ITIG}homeroom?class=${titular!.id}`, "gestion", "homeroom");
    // Mon horaire (EDT.4b) : ses séances dans l'horaire publié.
    await visit(teacher, `${ITIG}my-timetable`, "gestion", "my-timetable");
    // Suivi des notes (8.2.2, NB.2) : la directrice des études (double authentification).
    const director = await staff(browser, "0000001002", true);
    await visit(director, `${ITIG}grade-validation`, "gestion", "grade-validation");
    await visit(director, `${ITIG}report-cards`, "gestion", "report-cards");
    await visit(director, `${ITIG}grade-sheets`, "gestion", "grade-sheets");
    // Fiche de cotes (NB.1) : la première envoyée, lue par la directrice des études ; palmarès
    // de sa classe pour la période (NB.2).
    const board = await json<{
      term: string;
      classes: { id: string; courses: { id: string; status: string }[] }[];
    }>(director, "/api/grading/validation/");
    const group = board.classes.find((item) => item.courses.some((c) => c.status === "submitted"))!;
    const one = group.courses.find((c) => c.status === "submitted")!;
    await visit(
      director,
      `${ITIG}grade-sheets/totals?course=${one.id}&term=${board.term}`,
      "gestion",
      "fiche-cotes",
    );
    await visit(
      director,
      `${ITIG}grade-sheets?class=${group.id}&kind=ranking&column=${board.term}`,
      "gestion",
      "palmares",
    );
    // Conduite (8.5.1a) : l'enseignant attribue, le directeur de discipline tient le barème.
    await visit(teacher, `${ITIG}conduct`, "gestion", "conduct");
    const discipline = await staff(browser, "0000001003", false);
    await visit(discipline, `${ITIG}conduct-scale`, "gestion", "conduct-scale");
    // Application (8.5.1c) : le directeur des études corrige la cote de n'importe quelle classe.
    await visit(director, `${ITIG}application`, "gestion", "application");
    // Repêchage (8.4.1) : une classe complète de la démonstration, qui a des cours échoués.
    await visit(director, `${ITIG}resits`, "gestion", "resits", async (page) => {
      await page.getByLabel("Classe").selectOption({ label: "3HT ÉLECTRONIQUE A" });
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(500);
    });
    // Délibération (8.4.2) : même classe, décisions proposées reprises par la démonstration.
    await visit(director, `${ITIG}deliberation`, "gestion", "deliberation", async (page) => {
      await page.getByLabel("Classe").selectOption({ label: "3HT ÉLECTRONIQUE A" });
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(500);
    });
    // Reprise des résultats (8.4.7) : la 8EB C, sans aucune note, la moitié de ses élèves repris.
    await visit(
      director,
      `${ITIG}deliberation`,
      "gestion",
      "deliberation-reprise",
      async (page) => {
        await page.getByLabel("Classe").selectOption({ label: "8EB C" });
        await page.waitForLoadState("networkidle").catch(() => undefined);
        await page.waitForTimeout(500);
      },
    );
    await visit(director, `${ITIG}deliberation/prior-results`, "gestion", "reprise-resultats");
    // Situations (8.4.4) : la classe que la démonstration proclame.
    await visit(director, `${ITIG}situations`, "gestion", "situations", async (page) => {
      await page.getByLabel("Classe").selectOption({ label: "4HT MÉCANIQUE AUTOMOBILE A" });
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(800);
    });
  }

  if (!ONLY || ONLY.startsWith("portail")) {
    const parent = await (await browser.newContext()).newPage();
    await parent.goto(`${PORTAL}login`);
    await enterPassword(parent, "0002000001");
    await parent.waitForURL((url) => !url.pathname.includes("login"));
    for (const path of [
      "",
      "announcements",
      "calendar",
      "notifications",
      "profile",
      "guide",
      "add-school",
    ]) {
      await visit(parent, `${PORTAL}${path}`, "portail", path || "accueil");
    }
    const families = await json<{ children: { id: string }[] }[]>(parent, "/api/portal/families/");
    const child = families.flatMap((family) => family.children)[0]!;
    await visit(parent, `${PORTAL}children/${child.id}`, "portail", "enfant");
  }

  if (!ONLY || ONLY.startsWith("console")) {
    const admin = await (await browser.newContext()).newPage();
    allowCodeAgain("+243000000000");
    await admin.goto(CONSOLE);
    await enterPassword(admin, "0000000000");
    await enterCode(admin);
    await admin.waitForURL((url) => !url.pathname.includes("login"));
    for (const path of [
      "",
      "schools",
      "schools/new",
      "demo-requests",
      "accounts",
      "announcements",
      "site",
      "devices",
      "identity",
      "journal",
      "team",
    ]) {
      await visit(
        admin,
        `${CONSOLE}${path}`,
        "console",
        path.replace(/\//g, "-") || "tableau-de-bord",
      );
    }
    const schools = await json<{ results: { id: string }[] }>(
      admin,
      "/api/console/schools/?page_size=1",
    );
    await visit(admin, `${CONSOLE}schools/${schools.results[0]!.id}`, "console", "ecole");
  }

  mkdirSync(OUT, { recursive: true });
  writeFileSync(`${OUT}rapport.json`, JSON.stringify(report, null, 2));
});
