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

async function visit(page: Page, url: string, app: string, name: string) {
  if (ONLY && !`${app}/${name}`.startsWith(ONLY) && ONLY !== app) return;
  await page.setViewportSize(WIDTHS[2]!);
  await page.goto(url);
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
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
      "unpaid",
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
      "accounts",
      "announcements",
      "devices",
      "identity",
      "journal",
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
