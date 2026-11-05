import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
const DETAIL = {
  id: "r1",
  number: 42,
  subject: "Le reçu ne s'imprime plus",
  screen: "/app/cash",
  status: "answered",
  last_activity_at: "2026-11-04T09:40:00Z",
  created_at: "2026-11-04T08:12:00Z",
  closed_at: null,
  app_version: "1.14",
  device: "Chrome · Android",
  replies: [
    {
      id: "m1",
      from_platform: false,
      author_name: "Jeanne Kavira",
      body: "Rien ne sort.",
      created_at: "2026-11-04T08:12:00Z",
    },
    {
      id: "m2",
      from_platform: true,
      author_name: "Patrick",
      body: "Choisissez Thermique 80 mm.",
      created_at: "2026-11-04T09:40:00Z",
    },
  ],
};

describe("demandes d'aide (SUP.1)", () => {
  it("« Mes demandes » : le fil de la réponse, puis « C'est réglé » ferme la demande", async () => {
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/help/requests/": () => page([DETAIL]),
      "GET /api/help/requests/r1/": () => DETAIL,
      "POST /api/help/requests/r1/close/": () => ({ ...DETAIL, status: "closed" }),
    });
    const { user } = renderApp("/help/requests/r1");

    expect(await screen.findByText("Choisissez Thermique 80 mm.")).toBeTruthy();
    expect(screen.getAllByText("Réponse reçue").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "C'est réglé, fermer la demande" }));
    expect(
      requests.some((r) => r.method === "POST" && r.path === "/api/help/requests/r1/close/"),
    ).toBe(true);
  });
});
