// Aperçu des documents imprimables (`make apercu`) : chaque document du serveur (situation
// financière, fiche d'inscription, liste de classe, impayés, lettres, circulaire, convocation,
// page de vérification d'un reçu) dans `apercu/captures/documents/`, rendu comme son PDF (même
// gabarit, aperçu HTML). La fiche d'accès n'existe que pour une démonstration créée dans la console.
import { mkdirSync } from "node:fs";

import { test } from "@playwright/test";

import { allowCodeAgain, manage } from "../e2e/django";
import { enterCode, enterPassword, ITIG } from "../e2e/helpers";

const OUT = new URL("./captures/documents/", import.meta.url).pathname;
const ONLY = process.env.APERCU ?? "";

/** Identifiants pris dans les données de `make demo`. */
function ids(): Record<string, string> {
  const code = `
import json
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Enrollment, Family
from apps.notifications.models import Announcement, Summons
from apps.finance.models import Payment
itig = School.objects.get(code="itig")
with use_school(itig):
    enrollment = Enrollment.objects.filter(status="active").order_by("created_at").first()
    print(json.dumps({
        "enrollment": str(enrollment.pk),
        "class_group": str(enrollment.class_group_id),
        "family": str(Family.objects.order_by("created_at").first().pk),
        "announcement": str(Announcement.objects.order_by("-published_at").first().pk),
        "summons": str(Summons.objects.order_by("created_at").first().pk),
        "payment": str(Payment.objects.filter(origin="cash").order_by("-paid_at").first().pk),
    }))
`;
  return JSON.parse(manage("shell", "-c", code).trim().split("\n").at(-1)!);
}

test("documents imprimables", async ({ browser }) => {
  test.skip(Boolean(ONLY) && !ONLY.startsWith("documents"), "autre écran demandé");
  mkdirSync(OUT, { recursive: true });
  const id = ids();
  const head = await (
    await browser.newContext({ viewport: { width: 1000, height: 1400 } })
  ).newPage();
  allowCodeAgain("+243000001001");
  await head.goto(ITIG);
  await enterPassword(head, "0000001001");
  await enterCode(head);
  await head.waitForURL((url) => !url.pathname.includes("login"));
  const documents: [string, string][] = [
    [
      "situation-financiere",
      `/api/student-charges/statement/?output=html&upcoming=true&payments=true&hide_paid=false&enrollment=${id.enrollment}`,
    ],
    [
      "fiche-inscription",
      `/api/enrollments/${id.enrollment}/form/?output=html&paper=a4&family_code=true&fees=true`,
    ],
    [
      "liste-classe",
      `/api/enrollments/class-list/?class_group=${id.class_group}&output=html&blank_columns=2&order=name&columns=matricule&columns=guardian_phone`,
    ],
    [
      "impayes",
      `/api/unpaid/export/?output=html&group=class&page_per_class=false&phone=true&detail=true`,
    ],
    ["lettres-invitation", `/api/families/letters/?class_group=${id.class_group}&output=html`],
    ["circulaire", `/api/announcements/${id.announcement}/circular/?output=html`],
    ["convocation", `/api/summons/${id.summons}/letter/?output=html`],
  ];
  for (const [name, path] of documents) {
    await head.goto(`${ITIG.replace("/app/", "")}${path}`);
    await head.screenshot({ path: `${OUT}${name}.png`, fullPage: true });
  }
  await head.goto(`http://itig.localhost:8000/v/${id.payment}`);
  await head.screenshot({ path: `${OUT}verification-recu.png`, fullPage: true });
});
