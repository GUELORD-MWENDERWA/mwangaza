import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "../../test/api";
import { AiButton } from "./AiButton";

const CREDITS = {
  month: "2026-11-01",
  has_module: true,
  granted_credits: 2000,
  spent_credits: 2000,
  remaining_credits: 0,
  blocked: "",
  uses: [{ code: "timetable_review", label: "Analyse de l'horaire", blocked: "ai_no_credits" }],
};

function show(credits: object) {
  mockApi({ "GET /api/ai/credits/": credits });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AiButton use="timetable_review" onClick={() => undefined}>
        Analyser
      </AiButton>
    </QueryClientProvider>,
  );
}

describe("Bouton IA (IA.1.2)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("grisé avec la raison quand le serveur refuserait à coup sûr", async () => {
    show(CREDITS);
    expect(await screen.findByText("Crédits du mois épuisés")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Analyser" }).hasAttribute("disabled")).toBe(true);
  });

  it("actif quand l'usage est donné et qu'il reste des crédits", async () => {
    show({ ...CREDITS, uses: [{ ...CREDITS.uses[0], blocked: "" }] });
    const button = await screen.findByRole("button", { name: "Analyser" });
    await vi.waitFor(() => expect(button.hasAttribute("disabled")).toBe(false));
    expect(screen.queryByText("Crédits du mois épuisés")).toBeNull();
  });
});
