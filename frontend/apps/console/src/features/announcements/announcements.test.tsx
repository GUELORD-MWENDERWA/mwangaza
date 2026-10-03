import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderApp } from "../../test/render";

const ADMIN = {
  id: "a1",
  phone: "+243000000000",
  last_name: "Mwenderwa",
  middle_name: "",
  first_name: "Guelord",
  language: "fr",
  is_platform_admin: true,
};
const ALPHA = { id: "s1", code: "alpha", name: "École Alpha" };
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

afterEach(() => vi.unstubAllGlobals());

describe("Annonces aux écoles", () => {
  it("demande au moins une école, puis publie pour celles choisies", async () => {
    const published: unknown[] = [];
    const requests = mockApi({
      "GET /api/me/": ADMIN,
      "GET /api/console/announcements/": () => page(published),
      "GET /api/console/schools/": page([{ ...ALPHA, status: "active" }]),
      "POST /api/console/announcements/": () => {
        const announcement = {
          id: "n1",
          title: "Maintenance samedi",
          body: "Coupure de 22 h à minuit.",
          audience: "schools",
          schools: [ALPHA],
          published_at: "2026-10-03T08:00:00Z",
          published_by: null,
          archived_at: null,
          read_by: 0,
        };
        published.push(announcement);
        return announcement;
      },
    });
    const { user } = renderApp("/announcements");

    await user.type(await screen.findByLabelText("Titre"), "Maintenance samedi");
    await user.type(screen.getByLabelText("Message"), "Coupure de 22 h à minuit.");
    await user.click(screen.getByRole("radio", { name: "Certaines écoles" }));
    await user.click(screen.getByRole("button", { name: "Publier pour 0 école" }));
    expect(await screen.findByText("Choisissez au moins une école.")).toBeTruthy();

    await user.type(screen.getByLabelText(/Ajouter une école/), "alp");
    await user.click(await screen.findByRole("button", { name: "+ École Alpha" }));
    await user.click(screen.getByRole("button", { name: "Publier pour 1 école" }));

    expect(await screen.findByText(/École Alpha · .* · lue par 0 personne/)).toBeTruthy();
    const posts = requests.filter((r) => r.method === "POST");
    expect(posts.map((r) => r.body)).toEqual([
      {
        title: "Maintenance samedi",
        body: "Coupure de 22 h à minuit.",
        audience: "schools",
        schools: ["s1"],
      },
    ]);
  });
});
