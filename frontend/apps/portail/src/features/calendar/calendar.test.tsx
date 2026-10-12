import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT, ITIG } from "../../test/fixtures";
import { mockApi, renderApp } from "../../test/render";

const page = (results: object[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
const summons = {
  id: "s1",
  school_name: "ITIG Don Bosco Goma",
  school_timezone: "Africa/Lubumbashi",
  student_id: "c1",
  student_name: "KASEREKA Muhindo Jean",
  class_name: "3e Électricité A",
  reason: "Résultats de la période.",
  meeting_at: "2099-10-22T08:00:00Z",
  meet_with: "Préfet des études",
  seen: false,
};
const event = {
  id: "e1",
  school_name: "ITIG Don Bosco Goma",
  title: "Réunion des parents",
  description: "Grande salle.",
  kind: "meeting",
  starts_on: "2099-10-24",
  ends_on: "2099-10-24",
  start_time: "09:00:00",
};

describe("Calendrier du portail", () => {
  it("montre la convocation, la note vue, puis les événements par mois", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG],
      "GET /api/portal/summons/": page([summons]),
      "GET /api/portal/calendar/": page([event]),
      "POST /api/portal/summons/seen/": new Response(null, { status: 204 }),
    });
    renderApp("/calendar");

    expect(await screen.findByText("L'école vous attend pour KASEREKA Muhindo Jean")).toBeTruthy();
    expect(screen.getByText("22/10/2099 10:00")).toBeTruthy();
    expect(screen.getByText("Se présenter auprès de : Préfet des études")).toBeTruthy();
    expect(await screen.findByText("Réunion des parents")).toBeTruthy();
    expect(screen.getByText("24/10/2099 · 09:00")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "octobre 2099" })).toBeTruthy();
    await waitFor(() =>
      expect(requests.filter((r) => r.method === "POST").map((r) => r.body)).toEqual([
        { ids: ["s1"] },
      ]),
    );
  });
});
