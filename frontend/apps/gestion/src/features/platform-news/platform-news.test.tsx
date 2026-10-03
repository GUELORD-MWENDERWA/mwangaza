import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi, noContent } from "../../test/api";
import { me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const NEWS = {
  id: "n1",
  title: "Maintenance du serveur samedi soir",
  body: "L'application sera indisponible samedi de 22 h à minuit.",
  published_at: "2026-10-02T08:00:00Z",
  is_read: false,
};
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

describe("annonces de la plateforme (5.4.3)", () => {
  it("bandeau de la dernière non lue : « Fermer » la note comme lue pour ce compte", async () => {
    let read = false;
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("cashier"),
      "GET /api/platform-announcements/": () => page(read ? [] : [NEWS]),
      "POST /api/platform-announcements/read/": () => {
        read = true;
        return noContent();
      },
    });
    const { user } = renderApp("/");

    const banner = await screen.findByRole("region", { name: "Annonce de la plateforme" });
    expect(within(banner).getByText(NEWS.title)).toBeTruthy();
    await user.click(within(banner).getByRole("button", { name: "Fermer" }));

    expect(screen.queryByRole("region", { name: "Annonce de la plateforme" })).toBeNull();
    const posts = requests.filter((r) => r.method === "POST");
    expect(posts.map((r) => r.body)).toEqual([{ ids: ["n1"] }]);
  });
});
