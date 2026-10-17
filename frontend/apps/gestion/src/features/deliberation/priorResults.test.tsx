import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { json, mockApi, type Routes } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";
import { priorPercent } from "./data";

const line = {
  line: 2,
  matricule: "ITIG-2026-0001",
  student: "KAMBALE Josué",
  class_group: "8EB C",
  decision_text: "Admis",
  decision: "pass",
  percent_text: "62,5",
  percent: "62.5",
  issues: [],
};
const preview = {
  recorded: false,
  ready_count: 1,
  error_count: 1,
  empty_count: 0,
  class_count: 1,
  changed_count: 0,
  errors: [
    { ...line, line: 3, percent_text: "130", percent: null, issues: [{ code: "invalid_percent" }] },
  ],
  ready: [line],
};

describe("reprise des résultats (8.4.7)", () => {
  it("vérifie le fichier, puis l'enregistre avec le nombre de lignes et la date", async () => {
    const all: Routes = {
      "GET /api/school/": school,
      "GET /api/me/": me("study_director"),
      "POST /api/deliberation/prior-results/": json(preview),
    };
    const requests = mockApi(all);
    const posted = () => requests.filter((request) => request.method === "POST");
    const { user } = renderApp("/deliberation/prior-results");

    // `FormData` et fichier de Node : le `Request` de Node ne lit pas ceux de jsdom.
    const form = await new Response(new URLSearchParams("a=b")).formData();
    vi.stubGlobal("FormData", form.constructor);
    const blob = await new Response("xlsx").blob();
    const file = Object.assign(blob, { name: "resultats.xlsx" }) as unknown as File;
    await user.upload(await screen.findByLabelText(/Fichier Excel/), file);
    await user.type(screen.getByLabelText("Date de la délibération"), "2027-06-30");
    await user.click(screen.getByRole("button", { name: "Vérifier le fichier" }));

    expect(await screen.findByText(/Pourcentage illisible/)).toBeTruthy();
    expect(String(posted()[0]?.body)).not.toContain('name="expected"');
    all["POST /api/deliberation/prior-results/"] = json(
      { ...preview, recorded: true, changed_count: 1 },
      201,
    );
    await user.click(screen.getByRole("button", { name: "Enregistrer 1 décision" }));

    expect(await screen.findByText(/1 décision écrite/)).toBeTruthy();
    const sent = String(posted()[1]?.body);
    expect(sent).toMatch(/name="expected"\r\n\r\n1\r\n/);
    expect(sent).toContain("2027-06-30");
  });

  it("envoie le pourcentage tapé à la française", () => {
    expect([priorPercent(" 62,5 "), priorPercent("")]).toEqual(["62.5", null]);
  });
});
