import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { fakeId, me, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const waiver = {
  id: fakeId(80),
  family: null,
  student: fakeId(81),
  target_name: "KAMBALE MUHINDO Josué",
  reason: "Père en voyage, paie vendredi",
  until: "2026-11-30",
  granted_by_name: "Emmanuel Bahati",
  created_at: "2026-11-03T08:00:00Z",
  lifted_at: null,
  active: true,
};

describe("Dérogations de bulletin (8.4.6)", () => {
  it("le préfet lève une dérogation active", async () => {
    const requests = mockApi({
      "GET /api/school/": school,
      "GET /api/me/": me("head"),
      "GET /api/fee-waivers/": { count: 1, next: null, previous: null, results: [waiver] },
      [`POST /api/fee-waivers/${waiver.id}/lift/`]: { ...waiver, active: false, lifted_at: "x" },
    });
    const { user } = renderApp("/waivers");

    expect(await screen.findByText("KAMBALE MUHINDO Josué")).toBeTruthy();
    expect(screen.getByText("Père en voyage, paie vendredi")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Lever" }));

    await waitFor(() =>
      expect(requests.filter((item) => item.method === "POST").map((item) => item.path)).toEqual([
        `/api/fee-waivers/${waiver.id}/lift/`,
      ]),
    );
  });
});
