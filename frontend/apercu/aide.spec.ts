// Captures de l'aide (`make captures-aide`) : les écrans cités par les articles de
// `backend/apps/core/help/`, sur les données de `make demo`, sans menu latéral (1 184 x 740), le
// Portail au téléphone (390 x 844). Français puis anglais (langue gardée sur l'appareil) ; PNG dans
// `apercu/captures/aide/<langue>/`, puis `webp-aide.py` les met en WebP. La caisse (parcours en
// français) n'est prise qu'en français. Ne tourne qu'avec `APERCU=aide`.
import { mkdirSync } from "node:fs";

import { type Browser, type Page, test } from "@playwright/test";

import { allowCodeAgain, closeCashSessions, manage, unpaidStudent } from "../e2e/django";
import { enterCode, enterPassword } from "../e2e/helpers";
import { ITIG, PORTAL } from "./adresses";

const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const SIDEBAR = 256;

test.skip(process.env.APERCU !== "aide", "seulement pour make captures-aide");

async function settle(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page
    .locator(
      '[role="status"][aria-label^="Chargement"], [role="status"]:has-text("Synchronisation")',
    )
    .first()
    .waitFor({ state: "hidden", timeout: 20_000 })
    .catch(() => undefined);
  await page
    .waitForFunction(() => !document.querySelector(".animate-pulse"), undefined, {
      timeout: 15_000,
    })
    .catch(() => undefined);
  await page.waitForTimeout(600);
}

async function clean(page: Page) {
  await page
    .addStyleTag({ content: '[role="note"]{display:none !important}' })
    .catch(() => undefined);
  for (let round = 0; round < 6; round++) {
    let closed = false;
    for (const name of ["Fermer", "Plus tard", "Close", "Later"]) {
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

async function open(browser: Browser, size = DESKTOP) {
  const page = await (await browser.newContext({ viewport: size })).newPage();
  await page.addInitScript(() => {
    window.print = () => undefined;
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  return page;
}

async function staff(browser: Browser, number: string, withCode: boolean) {
  const page = await open(browser);
  if (withCode) allowCodeAgain(`+243${number.slice(1)}`);
  await page.goto(ITIG);
  await enterPassword(page, number);
  if (withCode) await enterCode(page);
  await page.waitForURL((url) => !url.pathname.includes("login"));
  await settle(page);
  const skip = page.getByRole("dialog").getByRole("button", { name: "Passer le guide" });
  if (await skip.isVisible().catch(() => false)) await skip.click();
  return page;
}

/** La langue est celle du compte : on la change pour les trois comptes des captures. */
function setLanguage(lang: string) {
  manage(
    "shell",
    "-c",
    `from apps.accounts.models import User; User.objects.filter(phone__in=['+243000001001','+243002000001']).update(language='${lang}')`,
  );
}

async function english(page: Page) {
  await page.evaluate(() => localStorage.setItem("mwangaza.language", "en"));
  await page.reload();
  await settle(page);
}

async function shot(page: Page, lang: string, name: string, mobile = false) {
  await settle(page);
  await clean(page);
  const path = `${new URL(`./captures/aide/${lang}/`, import.meta.url).pathname}${name}.png`;
  if (mobile) await page.screenshot({ path });
  else
    await page.screenshot({
      path,
      clip: { x: SIDEBAR, y: 0, width: DESKTOP.width - SIDEBAR, height: 740 },
    });
}

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

test("captures de l'aide", async ({ browser }) => {
  for (const lang of ["fr", "en"])
    mkdirSync(new URL(`./captures/aide/${lang}`, import.meta.url).pathname, { recursive: true });
  const photo = studentWithPhoto();

  const head = await staff(browser, "0000001001", true);
  const cashier = await staff(browser, "0000001005", true);
  const parent = await open(browser, MOBILE);
  await parent.goto(`${PORTAL}login`);
  await enterPassword(parent, "0002000001");
  await parent.waitForURL((url) => !url.pathname.includes("login"));
  const families = await parent.evaluate(async () => (await fetch("/api/portal/families/")).json());
  const child = (families as { children: { id: string }[] }[])[0]!.children[0]!;

  for (const lang of ["fr", "en"]) {
    if (lang === "en") {
      setLanguage("en");
      await english(head);
      await english(parent);
    }
    for (const [path, name] of [
      [`students/${photo}`, "eleve"],
      ["unpaid", "impayes"],
      ["fees", "frais"],
    ] as const) {
      await head.goto(`${ITIG}${path}`);
      await shot(head, lang, name);
    }
    await parent.goto(`${PORTAL}children/${child.id}`);
    await shot(parent, lang, "enfant", true);
  }

  setLanguage("fr");

  // Caisse : parcours en français seulement.
  closeCashSessions();
  await cashier.goto(`${ITIG}cash`);
  await cashier.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();
  await settle(cashier);
  const student = unpaidStudent();
  await cashier.getByLabel("Élève qui paie").fill(student.matricule);
  await cashier.getByRole("button", { name: new RegExp(student.matricule) }).click();
  await cashier.getByLabel("Montant reçu en USD").fill("150");
  await shot(cashier, "fr", "caisse");
  await cashier.reload();
  await settle(cashier);
  closeCashSessions();
});
