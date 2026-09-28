import { expect, test } from "@playwright/test";

import { allowCodeAgain, manage } from "./django";
import { enterCode, enterPassword, ITIG } from "./helpers";

/** Inscriptions de l'année en cours de l'ITIG : ce que l'instantané descend sur l'appareil. */
function currentEnrollments(): number {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools import organisation
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig")):
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
