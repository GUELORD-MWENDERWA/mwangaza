import { expect, test } from "@playwright/test";

import { shell } from "./django";
import { VOLCANS } from "./helpers";

const SUSPEND = (status: string) =>
  `from apps.schools.models import School; School.objects.filter(code='volcans').update(status='${status}')`;

test("école suspendue : aucune donnée, seulement le message (A1)", async ({ page }) => {
  shell(SUSPEND("suspended"));
  try {
    await page.goto(VOLCANS);
    await expect(page.getByText("L'accès à cette école est suspendu")).toBeVisible();
    await expect(page.getByLabel("Numéro de téléphone")).toHaveCount(0);
  } finally {
    shell(SUSPEND("active"));
  }
});

test("adresse sans école", async ({ page }) => {
  await page.goto("http://inconnue.localhost:5173/app/");
  await expect(page.getByText("Aucune école à cette adresse")).toBeVisible();
});
