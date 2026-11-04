import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OWNER, mockApi, renderApp } from "../../test/render";

const ADMIN = {
  id: "a1",
  phone: "+243000000000",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
  ...OWNER,
};

const REQUEST = {
  id: "r1",
  created_at: "2026-10-18T07:42:00Z",
  updated_at: "2026-10-18T07:42:00Z",
  name: "MUHINDO KAKULE Jean-Paul",
  role: "prefect",
  school_name: "Institut Les Volcans",
  town: "Goma",
  phone: "+243971234567",
  size: "300-800",
  email: "",
  message: "Voir la caisse.",
  language: "fr",
  status: "new",
  notes: "",
  assignee: null,
  assignee_name: "",
  follow_up_on: null,
  lost_reason: "",
  school_code: "",
  overdue: false,
};

afterEach(() => vi.unstubAllGlobals());

describe("Prospects de la console", () => {
  it("montre les nouvelles d'abord, enregistre le suivi et n'efface qu'après confirmation", async () => {
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/demo-requests/": {
        count: 1,
        next: null,
        previous: null,
        results: [REQUEST],
      },
      "GET /api/console/demo-requests/assignees/": [{ id: "u1", name: "Commercial" }],
      "PATCH /api/console/demo-requests/r1/": { ...REQUEST, status: "lost", notes: "Jeudi" },
      "DELETE /api/console/demo-requests/r1/": () => new Response(null, { status: 204 }),
    });
    const { user } = renderApp("/demo-requests");

    expect(await screen.findByText("Institut Les Volcans")).toBeTruthy();
    expect(screen.getByText(/préfet des études/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /WhatsApp/ }).getAttribute("href")).toBe(
      "https://wa.me/243971234567",
    );
    expect(requests.find((r) => r.path === "/api/console/demo-requests/")?.search).toContain(
      "status=new",
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "Étape" }), "lost");
    await user.type(screen.getByLabelText(/Motif de perte/), "Trop cher");
    await user.selectOptions(await screen.findByRole("combobox", { name: "Responsable" }), "u1");
    await user.type(screen.getByLabelText("Note interne"), "Jeudi");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));
    const patch = requests.find((r) => r.method === "PATCH");
    expect(patch?.body).toEqual({
      status: "lost",
      notes: "Jeudi",
      assignee: "u1",
      follow_up_on: null,
      lost_reason: "Trop cher",
    });

    await user.click(screen.getByRole("button", { name: "Effacer" }));
    const dialog = await screen.findByRole("dialog");
    expect(requests.some((r) => r.method === "DELETE")).toBe(false);
    await user.click(within(dialog).getByRole("button", { name: "Effacer" }));
    expect(requests.filter((r) => r.method === "DELETE")).toHaveLength(1);
  });
});
