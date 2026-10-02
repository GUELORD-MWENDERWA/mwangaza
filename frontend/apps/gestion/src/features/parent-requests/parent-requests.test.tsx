import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const change = {
  id: fakeId(70),
  family: {
    id: fakeId(40),
    code: "K7M4P9TX",
    parent: "Kahindo Sarah",
    phone: "+243972145508",
    children: ["KAMBALE MUHINDO Josué"],
  },
  changes: {
    address: {
      before: { commune: "Karisimbi", quartier: "Majengo", avenue: "Kabanda", number: "23" },
      after: { commune: "Goma", quartier: "Himbi", avenue: "Lukanga", number: "7" },
    },
  },
  status: "pending",
  created_at: "2026-10-02T06:12:00Z",
  handled_by: null,
  handled_at: null,
};
const page = (results: unknown[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});

describe("Demandes des parents (M18)", () => {
  it("le secrétariat applique les coordonnées envoyées à la fiche de la famille", async () => {
    const applied = {
      ...change,
      status: "applied",
      handled_by: "Furaha Grâce",
      handled_at: "2026-10-02T08:00:00Z",
    };
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/contact-changes/": page([change]),
      [`POST /api/contact-changes/${change.id}/apply/`]: applied,
    });
    const { user } = renderApp("/parent-requests");

    expect(await screen.findByRole("button", { name: "Kahindo Sarah" })).toBeTruthy();
    expect(screen.getAllByText("Goma, Himbi, Lukanga, 7").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Appeler +243 97 214 55 08" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Appliquer à la fiche" }));

    await waitFor(() =>
      expect(requests.filter((item) => item.method === "POST").map((item) => item.path)).toEqual([
        `/api/contact-changes/${change.id}/apply/`,
      ]),
    );
  });
});
