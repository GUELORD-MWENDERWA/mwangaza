import { expect, test } from "@playwright/test";

import { manage } from "./django";
import { enterPassword, ITIG } from "./helpers";

/** Un cours de l'enseignant de démonstration (`0000001008`) sur la 1re période, remis en
 *  brouillon sans date limite ; rend le cours et la période. */
function prepareSheet(): { course: string; term: string } {
  const output = manage(
    "shell",
    "-c",
    `from apps.academics.models import Course, GradeDeadline, GradeSheet
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.schools.models import School, Term
with use_school(School.objects.get(code="itig-demo")):
    teacher = User.objects.get(phone="+243000001008")
    course = Course.objects.filter(teacher=teacher).order_by("class_group__level__order", "class_group__section", "order").first()
    term = Term.objects.filter(academic_year=course.class_group.academic_year, kind="period").order_by("order").first()
    GradeSheet.objects.filter(course=course, term=term).delete()
    GradeDeadline.objects.filter(term=term).delete()
    print("RESULT", course.pk, term.pk)`,
  );
  const [, course, term] = output.trim().split("\n").at(-1)!.split(" ");
  return { course: course!, term: term! };
}

test("notes sans réseau : deux enregistrements gardés sur l'appareil, envoyés une seule fois au retour du réseau (8.2.3)", async ({
  page,
  context,
}) => {
  const { course, term } = prepareSheet();
  await page.addInitScript(() => {
    navigator.storage.persist = async () => true;
    navigator.storage.persisted = async () => true;
  });
  await page.goto(`${ITIG}grades?course=${course}&term=${term}`);
  await enterPassword(page, "0000001008");
  const indicator = page.getByRole("status").filter({ hasText: /ligne|Synchronisation/ });
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  const first = page.locator('[data-cell="0:0"]');
  const second = page.locator('[data-cell="1:0"]');
  await expect(first).toBeVisible();

  await context.setOffline(true);
  await expect(indicator).toHaveText("Hors ligne");
  await first.fill("4,5");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByText(/1 enregistrement de notes attend/)).toBeVisible();
  await second.fill("3");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await expect(page.getByText(/2 enregistrements de notes attendent/)).toBeVisible();
  await expect(first).toHaveValue("4,5");
  await expect(second).toHaveValue("3");

  await context.setOffline(false);
  await expect(indicator).toHaveText("En ligne · à jour", { timeout: 30_000 });
  await expect(page.getByText(/enregistrements? de notes attendent?/)).toHaveCount(0);

  // Le serveur a les deux notes, une seule fois : la feuille relue est la sienne.
  await page.reload();
  await expect(page.locator('[data-cell="0:0"]')).toHaveValue("4,5");
  await expect(page.locator('[data-cell="1:0"]')).toHaveValue("3");
});
