import { expect, test } from "@playwright/test";

import { allowCodeAgain, closeCashSessions, manage, unpaidStudent } from "./django";
import { enterCode, enterPassword, ITIG, skipGuide } from "./helpers";

/** Inscriptions de l'année en cours de l'ITIG : ce que l'instantané descend sur l'appareil. */
function currentEnrollments(): number {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig-demo")):
    print(Enrollment.objects.filter(academic_year=organisation.current_year()).count())`,
  );
  // Dernière ligne : le shell annonce d'abord ses imports automatiques.
  return Number(output.trim().split("\n").at(-1));
}

test("appareil mémorisé : l'école descend sur l'appareil, puis hors ligne et retour du réseau (3.4)", async ({
  page,
  context,
}) => {
  allowCodeAgain("+243000001005");
  await page.goto(`${ITIG}cash`);
  // « Se souvenir de cet appareil » est cochée par défaut.
  await enterPassword(page, "0000001005");
  await enterCode(page);
  await skipGuide(page);

  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  const stored = await page.evaluate(async () => {
    const databases = await indexedDB.databases();
    const name = databases.find((item) => item.name?.startsWith("mwangaza-sync-"))!.name!;
    return new Promise<number>((resolve, reject) => {
      const request = indexedDB.open(name);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const count = request.result.transaction("enrollments").objectStore("enrollments").count();
        count.onsuccess = () => {
          request.result.close();
          resolve(count.result);
        };
      };
    });
  });
  expect(stored).toBe(currentEnrollments());

  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour");
});

test("démarrage sans réseau : code PIN, puis la caisse encaisse sur l'appareil (3.7.1)", async ({
  page,
  context,
}) => {
  closeCashSessions();
  const student = unpaidStudent();
  await page.addInitScript(() => {
    window.print = () => undefined;
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  allowCodeAgain("+243000001005");
  await page.goto(`${ITIG}account`);
  await enterPassword(page, "0000001005");
  await enterCode(page);
  await skipGuide(page);
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });

  // Code PIN propre à cet appareil (Mon compte).
  await page.getByRole("button", { name: "Définir un code PIN" }).click();
  await page.getByLabel("Nouveau code PIN").fill("2580");
  await page.getByLabel("Confirmer le code PIN").fill("2580");
  await page.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText("Code PIN enregistré sur cet appareil.")).toBeVisible();
  await page.goto(`${ITIG}cash`);
  await expect(page.getByRole("heading", { name: "Ouvrir la caisse" })).toBeVisible();

  // Le serveur ne répond plus (en production, le service worker sert l'application ; ici, Vite).
  // Seulement `/api/…` : les modules de Vite (`packages/api/…`) doivent encore arriver.
  await page.route(new URL("/api/**", ITIG).href, (route) => route.abort("internetdisconnected"));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Bonjour Grâce" })).toBeVisible({
    timeout: 15_000,
  });
  await context.setOffline(true);
  for (const digit of "1111") await page.getByRole("button", { name: digit, exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Code faux. Encore 4 essais.");
  await page.keyboard.type("2580");

  // Déverrouillée : la caisse travaille avec ce que l'appareil garde.
  await expect(indicator).toHaveText("Hors ligne");
  await page.getByRole("button", { name: /^Ouvrir la caisse C/ }).click();
  await page.getByLabel("Élève qui paie").fill(student.matricule);
  await page.getByRole("button", { name: new RegExp(student.matricule) }).click();
  await page.getByLabel("Montant reçu en USD").fill("10");
  await page.keyboard.press("F9");
  await expect(
    page.getByText(/^Paiement enregistré : reçu ITIG-DEMO-P\d+-26-\d{6}\.$/),
  ).toBeVisible();
  await expect(indicator).toHaveText("Hors ligne · 2 en attente");

  // Retour du réseau : la session du serveur est toujours là, tout part.
  await page.unrouteAll();
  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(page.getByText(/Session ouverte à .* · 1 paiement$/)).toBeVisible();
});
