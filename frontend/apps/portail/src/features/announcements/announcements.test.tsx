import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ACCOUNT, ITIG } from "../../test/fixtures";
import { mockApi, renderApp } from "../../test/render";

const VOLCANS = { ...ITIG, id: "f2", school_name: "Les Volcans", children: [] };

const announcement = (id: string, title: string, read: boolean, extra = {}) => ({
  id,
  school_name: "ITIG Don Bosco Goma",
  school_timezone: "Africa/Lubumbashi",
  classes: [],
  title,
  body: "Samedi à 9 h dans la grande salle.",
  attachment: null,
  published_at: "2026-10-01T08:00:00Z",
  read,
  ...extra,
});

const page = (results: object[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

describe("Annonces du portail", () => {
  it("montre les annonces, marque lues celles qui ne l'étaient pas et filtre par école", async () => {
    const requests = mockApi({
      "GET /api/portal/me/": ACCOUNT,
      "GET /api/portal/families/": [ITIG, VOLCANS],
      "GET /api/portal/announcements/": page([
        announcement("a2", "Réunion des parents de 3e", false, {
          classes: ["3e Électricité A"],
          attachment: "/api/portal/announcements/a2/attachment/",
        }),
        announcement("a1", "Congé de la Toussaint", true),
      ]),
      "POST /api/portal/announcements/read/": new Response(null, { status: 204 }),
    });
    const { user } = renderApp("/announcements");

    expect(await screen.findByText("Réunion des parents de 3e")).toBeTruthy();
    expect(screen.getByText("ITIG Don Bosco Goma · 3e Électricité A")).toBeTruthy();
    expect(screen.getAllByText("Nouvelle")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Pièce jointe (PDF)" }).getAttribute("href")).toBe(
      "/api/portal/announcements/a2/attachment/",
    );
    await waitFor(() =>
      expect(requests.filter((r) => r.method === "POST").map((r) => r.body)).toEqual([
        { ids: ["a2"] },
      ]),
    );

    await user.click(screen.getByRole("button", { name: "Les Volcans" }));
    await waitFor(() => expect(requests.map((r) => r.search)).toContain("?family=f2"));
  });
});
