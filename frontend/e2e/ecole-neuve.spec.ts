import { type Browser, type BrowserContext, expect, type Page, test } from "@playwright/test";

import { allowCodeAgain, manage, shell } from "./django";
import {
  activateTwoFactor,
  choosePassword,
  enterCode,
  enterPassword,
  mainMenu,
  skipGuide,
} from "./helpers";

const CONSOLE = "http://admin.localhost:5175/";
const PORTAL = "http://localhost:5174/";
const ADMIN = "+243000000000";

// Un espace neuf à chaque passage : code et numéros tirés au hasard, hors de la plage `000`
// réservée aux espaces de démonstration (un compte = un numéro, pour toute la plateforme).
const run = String(100000 + Math.floor(Math.random() * 900000));
const CODE = `neuve-${run}`;
const SCHOOL = `École neuve ${run}`;
const GESTION = `http://${CODE}.localhost:5173/app/`;
const HEAD = `0109${run}`;
const CASHIER = `0108${run}`;
const GUARDIAN = `0107${run}`;
const NEW_PASSWORD = "parcours-neuf-2026";

// Année scolaire qui contient aujourd'hui (rentrée en septembre).
const today = new Date();
const startYear = today.getMonth() >= 8 ? today.getFullYear() : today.getFullYear() - 1;
const YEAR = `${startYear}-${startYear + 1}`;

// Appareils ouverts par le parcours, fermés à la fin : sinon ils restent ouverts (et la caisse
// continue de se synchroniser) pendant les parcours suivants.
const devices: BrowserContext[] = [];

/** Une personne sur son propre appareil. Pas de fenêtre d'impression : on garde ce qui serait
 *  imprimé. Stockage persistant accordé (Chromium sans écran le refuse : caisse bloquée, M8). */
async function person(browser: Browser): Promise<Page> {
  const context = await browser.newContext();
  devices.push(context);
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.print = () => {
      document.body.dataset.printed = document.querySelector(".print-area")?.textContent ?? "";
    };
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  return page;
}

/** Ce que le serveur a gardé de l'espace : paiements (reçu, montant en entiers, taux utilisé),
 *  ce que l'élève doit encore en dollars, et la clôture par devise (attendu et compté). */
function serverMoney(): string {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import CashClosing, Payment
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="${CODE}")):
    payments = [f"{p.receipt_number}:{p.received_amount_minor}:{p.received_currency}:{p.rate_used.normalize():f}" for p in Payment.objects.all()]
    usd = next(c for c in services.balance(services.charges_of(Enrollment.objects.get().pk)).currencies if c.currency == "USD")
    closings = [f"{c.currency}:{c.expected_minor}:{c.counted_minor}" for c in CashClosing.objects.order_by("currency")]
    print(" ".join(payments), "|", usd.paid_minor, "|", " ".join(closings))`,
  );
  // Dernière ligne : le shell annonce d'abord ses imports automatiques.
  return output.trim().split("\n").at(-1)!;
}

/** L'espace d'essai du parcours est supprimé (permis pour un essai, jamais pour un espace réel) :
 *  la base de développement ne garde pas un espace par passage. */
function deleteSpace() {
  shell(`from apps.accounts.models import User
from apps.schools import services
from apps.schools.models import School
school = School.objects.filter(code="${CODE}").first()
if school:
    services.delete_space(school, actor=User.objects.get(phone="${ADMIN}"), confirm=school.code)`);
}

test("école neuve de bout en bout : espace créé dans la console, mise en route, inscription, encaissement et reçu, clôture, le parent voit le reçu (4.20.2)", async ({
  page,
  browser,
}) => {
  // Trois applications, quatre personnes : plus long que les autres parcours.
  test.setTimeout(300_000);
  try {
    // Console : le super-admin crée un espace d'essai — vide comme un espace réel, mais supprimable.
    allowCodeAgain(ADMIN);
    await page.goto(CONSOLE);
    await enterPassword(page, "0000000000");
    await enterCode(page);
    await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
    await page.goto(`${CONSOLE}schools/new?type=test`);
    await page.locator("#school-name").fill(SCHOOL);
    await page.locator("#school-code").fill(CODE);
    await page.locator("#head-phone").fill(HEAD);
    await page.locator("#head-last_name").fill("Bahati");
    await page.locator("#head-first_name").fill("Espérance");
    // Les modules se choisissent à la création (M.2.2) : les six sont cochés d'office, on retire
    // les annonces pour vérifier qu'un module absent n'apparaît nulle part (menu du directeur).
    await page.getByRole("checkbox", { name: "Annonces" }).uncheck();
    await page.getByRole("button", { name: "Créer l'école" }).click();
    await expect(page.getByRole("heading", { name: `École créée : ${SCHOOL}` })).toBeVisible();
    const temporary = await page.locator("code").innerText();
    allowCodeAgain(ADMIN);

    // Directeur : mot de passe provisoire remplacé, double authentification obligatoire, et la
    // liste « Mise en route » dès l'accueil, sans chercher le tableau de bord.
    const head = await person(browser);
    await head.goto(GESTION);
    await enterPassword(head, HEAD, temporary);
    await choosePassword(head, NEW_PASSWORD);
    await activateTwoFactor(head);
    const setup = head.locator("section", {
      has: head.getByRole("heading", { name: "Mise en route" }),
    });
    await expect(setup.getByText("0 / 6 étapes")).toBeVisible();
    await expect(mainMenu(head).getByRole("link", { name: "Annonces" })).toHaveCount(0);
    await expect(mainMenu(head).getByRole("link", { name: "Élèves" })).toBeVisible();

    // 1 et 2. Année, niveau et classe.
    await setup.getByRole("link", { name: "Créer l'année scolaire : ouvrir l'écran" }).click();
    await head.getByRole("button", { name: "Nouvelle année" }).click();
    let dialog = head.getByRole("dialog");
    await dialog.getByLabel(/Début/).fill(`${startYear}-09-01`);
    await dialog.getByLabel(/Fin/).fill(`${startYear + 1}-07-02`);
    await dialog.getByRole("button", { name: "Créer l'année" }).click();
    await expect(dialog).toHaveCount(0);
    await head.getByRole("tab", { name: "Niveaux et options" }).click();
    await head.getByRole("textbox", { name: /^Niveau/ }).fill("7e EB");
    await head.getByLabel("Cycle").selectOption("basic");
    await head.getByRole("button", { name: "Ajouter un niveau" }).click();
    await expect(head.getByRole("button", { name: "Supprimer 7e EB" })).toBeVisible();
    await head.getByRole("tab", { name: "Classes" }).click();
    await head.getByRole("button", { name: "Ajouter une classe" }).click();
    dialog = head.getByRole("dialog");
    await dialog.getByLabel(/Niveau/).selectOption({ label: "7e EB" });
    await dialog.getByLabel("Section").fill("a");
    await dialog.getByLabel("Capacité").fill("40");
    await dialog.getByRole("button", { name: "Ajouter" }).click();
    await expect(head.getByText("1 classe")).toBeVisible();

    // 3. Un frais, son barème en dollars et le taux de l'année (l'école a deux devises).
    await mainMenu(head).getByRole("link", { name: "Frais et barèmes" }).click();
    await head.getByRole("button", { name: "Type de frais" }).click();
    dialog = head.getByRole("dialog");
    await dialog.getByLabel("Nom").fill("Minerval");
    await dialog.getByRole("button", { name: "Enregistrer" }).click();
    await expect(dialog).toHaveCount(0);
    await head.getByRole("button", { name: "Barème" }).click();
    await head.getByLabel(/Total annuel/).fill("120");
    await head.getByRole("radio", { name: "Unique" }).click();
    await head.getByRole("button", { name: "Enregistrer", exact: true }).click();
    await head.getByLabel(/^Taux/).fill("2 800");
    await head.getByRole("button", { name: "Enregistrer le taux" }).click();
    await expect(head.getByText("1 $ = 2 800 FC")).toBeVisible();

    // 4. Le compte du caissier : le directeur ne peut pas encaisser.
    await mainMenu(head).getByRole("link", { name: "Comptes du personnel" }).click();
    const create = head.locator("section", {
      has: head.getByRole("heading", { name: "Nouveau compte" }),
    });
    await create.getByLabel("Numéro de téléphone").fill(CASHIER);
    await create.getByLabel("Nom", { exact: true }).fill("Kavira");
    await create.getByLabel("Prénom").fill("Aline");
    await create.getByRole("checkbox", { name: "Caissier" }).click();
    await create.getByRole("button", { name: "Créer le compte" }).click();
    const password = head.getByRole("dialog", { name: "Mot de passe provisoire" });
    const cashierTemporary = await password.locator("code").innerText();
    await password.getByRole("button", { name: "J'ai noté le mot de passe" }).click();

    // 5. La caisse, puis le caissier se connecte une fois sur l'appareil de la caisse.
    await mainMenu(head).getByRole("link", { name: "Paramètres de l'école" }).click();
    await head.getByRole("button", { name: "Ajouter une caisse" }).click();
    dialog = head.getByRole("dialog");
    await dialog.getByLabel("Nom").fill("Caisse 1");
    await dialog.getByLabel("Code").fill("C1");
    await dialog.getByRole("button", { name: "Enregistrer" }).click();
    await expect(dialog).toHaveCount(0);
    const cashier = await person(browser);
    await cashier.goto(`${GESTION}cash`);
    await enterPassword(cashier, CASHIER, cashierTemporary);
    await choosePassword(cashier, NEW_PASSWORD);
    await activateTwoFactor(cashier);
    await skipGuide(cashier);

    // 6. Le premier élève, avec sa famille.
    await mainMenu(head).getByRole("link", { name: "Tableau de bord" }).click();
    await expect(setup.getByText("5 / 6 étapes")).toBeVisible();
    await setup.getByRole("link", { name: "Inscrire les élèves : ouvrir l'écran" }).click();
    await expect(head.getByText("Aucun élève inscrit pour le moment.")).toBeVisible();
    await head.getByRole("link", { name: "Nouvel élève" }).click();
    // L'année chargée d'abord : le formulaire est alors complet.
    await expect(head.getByRole("heading", { name: `Scolarité ${YEAR}` })).toBeVisible();
    await head.getByLabel(/^Classe/).selectOption({ label: "7e EB A" });
    await head.getByLabel(/^Nom/).fill("Mugisho");
    await head.getByLabel(/^Post-nom/).fill("Bahati");
    await head.getByLabel(/^Prénom/).fill("Daniel");
    await head.getByRole("radio", { name: "Masculin" }).click();
    await head.getByLabel(/^Date de naissance/).fill(`${startYear - 12}-03-12`);
    await head.getByRole("radio", { name: "Nouvelle famille" }).click();
    await head.getByLabel(/^Nom complet/).fill("Bahati Marie");
    await head.getByLabel(/^Lien/).selectOption("mère");
    await head.getByLabel(/^Téléphone/).fill(GUARDIAN);
    await head.getByRole("button", { name: "Enregistrer et inscrire" }).click();
    const enrolled = head.getByText(/est inscrit en 7e EB A/);
    await expect(enrolled).toBeVisible();
    const familyCode = /code famille ([A-Z0-9]{8})/.exec(await enrolled.innerText())![1]!;

    // L'école peut encaisser : le directeur termine la mise en route, la liste disparaît.
    await mainMenu(head).getByRole("link", { name: "Tableau de bord" }).click();
    await expect(setup.getByText("6 / 6 étapes")).toBeVisible();
    await setup.getByRole("button", { name: "Terminer la mise en route" }).click();
    await expect(setup).toHaveCount(0);

    // Caissier : ouvre sa caisse, encaisse, le reçu s'imprime ; puis clôture.
    await cashier.reload();
    const indicator = cashier.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
    await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
    await cashier.getByRole("button", { name: /^Ouvrir la caisse C1/ }).click();
    await expect(cashier.getByText(/Session ouverte à .* · 0 paiement$/)).toBeVisible();
    await cashier.getByLabel("Élève qui paie").fill("Mugisho");
    await cashier.getByRole("button", { name: /MUGISHO/ }).click();
    await cashier.getByLabel("Montant reçu en USD").fill("50");
    await expect(cashier.getByText("Répartition")).toBeVisible();
    await cashier.keyboard.press("F9");
    const recorded = cashier.getByText(/^Paiement enregistré : reçu \S+\.$/);
    await expect(recorded).toBeVisible();
    const receipt = /reçu (\S+)\.$/.exec(await recorded.innerText())![1]!;
    const printed = cashier.locator("body");
    await expect(printed).toHaveAttribute(
      "data-printed",
      new RegExp(`Reçu n° ${receipt}.*Cinquante dollars`),
    );
    await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
    await cashier.getByRole("button", { name: "Clôturer la caisse" }).click();
    await cashier.getByLabel("Argent compté en USD").fill("50");
    await cashier.getByLabel("Argent compté en FC").fill("0");
    await cashier.getByRole("checkbox").check();
    await cashier.getByRole("button", { name: "Clôturer et imprimer le bordereau" }).click();
    await expect(printed).toHaveAttribute("data-printed", /Bordereau de clôture/);
    await cashier.getByRole("button", { name: "Terminer" }).click();
    await expect(cashier.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();
    await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
    // Sur le serveur : un seul paiement, en entiers, avec le taux de l'année ; 50 $ payés sur
    // 120 ; clôture sans écart.
    await expect
      .poll(serverMoney, { timeout: 30_000, intervals: [2_000, 5_000] })
      .toBe(`${receipt}:5000:USD:2800 | 5000 | CDF:0:0 USD:5000:5000`);

    // Parent : active son compte du portail avec le code famille et voit le reçu.
    const parent = await person(browser);
    await parent.goto(`${PORTAL}activate`);
    await parent.getByLabel("Numéro de téléphone").fill(GUARDIAN);
    await parent.getByLabel("Code famille").fill(familyCode);
    await parent.getByLabel("Choisissez un mot de passe").fill(NEW_PASSWORD);
    await parent.getByRole("button", { name: "Activer mon compte" }).click();
    await expect(parent.getByRole("heading", { name: "Bienvenue, Bahati Marie" })).toBeVisible();
    await parent.getByRole("button", { name: "Passer" }).click();
    await parent.getByRole("button", { name: "Plus tard" }).click();
    await expect(parent.getByRole("heading", { name: "Mes enfants" })).toBeVisible();
    await expect(parent.getByText("50,00 $ sur 120,00 $")).toBeVisible();
    await parent
      .getByRole("link", { name: /Daniel/ })
      .first()
      .click();
    await expect(parent.getByText(receipt)).toBeVisible();
  } finally {
    await Promise.all(devices.map((device) => device.close()));
    deleteSpace();
  }
});
