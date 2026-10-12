import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId as id, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const meeting = {
  id: id(300),
  title: "Réunion des parents",
  description: "Grande salle.",
  kind: "meeting",
  audience: "everyone",
  starts_on: "2026-10-24",
  ends_on: "2026-10-24",
  start_time: "09:00:00",
};
const exams = {
  ...meeting,
  id: id(301),
  title: "Examens de la période",
  kind: "exam",
  audience: "staff",
  starts_on: "2026-11-02",
  ends_on: "2026-11-06",
  start_time: null,
};
const page = { count: 2, next: null, previous: null, results: [meeting, exams] };

describe("Calendrier de l'école", () => {
  it("tout le personnel le lit, rangé par mois ; sans le droit, rien à modifier", async () => {
    mockApi({
      "GET /api/me/": me("cashier"),
      "GET /api/school/": school,
      "GET /api/calendar-events/": page,
    });
    renderApp("/calendar");

    expect(await screen.findByText("Réunion des parents")).toBeTruthy();
    expect(screen.getByText("24/10/2026 · 09:00")).toBeTruthy();
    expect(screen.getByText("02/11/2026 – 06/11/2026")).toBeTruthy();
    expect(screen.getByText("Personnel seulement")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "novembre 2026" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Ajouter un événement" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Modifier" })).toBeNull();
  });

  it("avec le droit : un événement d'une journée part sans fin ni heure", async () => {
    const requests = mockApi({
      "GET /api/me/": me("study_director"),
      "GET /api/school/": school,
      "GET /api/calendar-events/": page,
      "POST /api/calendar-events/": { ...meeting, id: id(302), title: "Journée sportive" },
    });
    const { user } = renderApp("/calendar");

    await user.click(await screen.findByRole("button", { name: "Ajouter un événement" }));
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect((await screen.findAllByText("Ce champ est obligatoire.")).length).toBe(2);

    await user.type(screen.getByLabelText("Titre"), "Journée sportive");
    await user.type(screen.getByLabelText("Début"), "2026-11-14");
    await user.selectOptions(screen.getByLabelText("Sorte"), "Activité");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(requests.filter((r) => r.method === "POST").map((r) => r.body)).toEqual([
        {
          title: "Journée sportive",
          description: "",
          kind: "activity",
          audience: "everyone",
          starts_on: "2026-11-14",
          ends_on: null,
          start_time: null,
        },
      ]),
    );
  });
});
