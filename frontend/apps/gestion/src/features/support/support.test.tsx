import { act, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { apiError, mockApi, noContent, type Routes } from "../../test/api";
import { me, PERMISSIONS, platformAdmin, school } from "../../test/fixtures";
import { renderApp } from "../../test/render";

const session = {
  school: { code: school.code, name: school.name, status: "active" as const },
  reason: "Demande du directeur (fictive)",
  started_at: "2026-09-26T08:42:00Z",
  expires_at: "2026-09-26T09:42:00Z",
};

/** Session ouverte : droits de l'école sauf la caisse, aucun rôle. */
const inSession = platformAdmin({
  school: {
    code: school.code,
    name: school.name,
    roles: [],
    permissions: PERMISSIONS.head,
  },
  support: session,
});

function routes(account = platformAdmin(), extra: Routes = {}): Routes {
  return { "GET /api/school/": school, "GET /api/me/": account, ...extra };
}

describe("session support (A3)", () => {
  it("super-admin sans session : l'ouverture, avec les règles", async () => {
    mockApi(routes());
    const { router } = renderApp("/");

    expect(await screen.findByRole("heading", { name: "Ouvrir une session support" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/support");
    expect(screen.getByText(/sauf la caisse/)).toBeTruthy();
  });

  it("motif obligatoire, 200 caractères au plus", async () => {
    const requests = mockApi(routes());
    const { user } = renderApp("/support");

    await user.click(await screen.findByRole("button", { name: "Ouvrir la session support" }));

    expect(await screen.findByText("Indiquez le motif.")).toBeTruthy();
    expect(requests.some((r) => r.method === "POST")).toBe(false);
    expect((screen.getByLabelText(/Motif/) as HTMLTextAreaElement).maxLength).toBe(200);
  });

  it("ouverte : bandeau rouge avec l'école, l'heure de fin (heure de l'école) et le motif", async () => {
    const api = routes(platformAdmin(), { "POST /api/support/": session });
    const requests = mockApi(api);
    const { user, router } = renderApp("/support");

    await user.type(await screen.findByLabelText(/Motif/), session.reason);
    api["GET /api/me/"] = inSession;
    await user.click(screen.getByRole("button", { name: "Ouvrir la session support" }));

    const banner = await screen.findByRole("region", { name: "Session support" });
    // 09:42 UTC = 11:42 à Goma.
    expect(banner.textContent).toContain(`vous agissez en tant que ${school.name}, jusqu'à 11:42.`);
    expect(within(banner).getByText(`Motif : ${session.reason}`)).toBeTruthy();
    expect(router.state.location.pathname).toBe("/");
    expect(requests.find((r) => r.method === "POST")?.body).toEqual({ reason: session.reason });
    // Rôle affiché : le support, jamais un rôle de l'école.
    expect(screen.getByText("Support Mwangaza")).toBeTruthy();
  });

  it("« Quitter » ferme la session : retour à l'ouverture", async () => {
    const api = routes(inSession, { "DELETE /api/support/": noContent() });
    mockApi(api);
    const { user, router } = renderApp("/");

    const banner = await screen.findByRole("region", { name: "Session support" });
    api["GET /api/me/"] = platformAdmin();
    await user.click(within(banner).getByRole("button", { name: "Quitter" }));

    expect(await screen.findByRole("heading", { name: "Ouvrir une session support" })).toBeTruthy();
    expect(router.state.location.pathname).toBe("/support");
  });

  it("à l'heure de fin, le compte est relu : la session n'existe plus", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-26T09:41:00Z"));
    const api = routes(inSession);
    mockApi(api);
    renderApp("/");

    await screen.findByRole("region", { name: "Session support" });
    api["GET /api/me/"] = platformAdmin();
    await act(() => vi.advanceTimersByTimeAsync(62_000));

    expect(await screen.findByRole("heading", { name: "Ouvrir une session support" })).toBeTruthy();
  });

  it("refusée par le serveur (double authentification) : message traduit", async () => {
    mockApi(routes(platformAdmin(), { "POST /api/support/": apiError("totp_required", 403) }));
    const { user } = renderApp("/support");

    await user.type(await screen.findByLabelText(/Motif/), "Vérification (fictive)");
    await user.click(screen.getByRole("button", { name: "Ouvrir la session support" }));

    expect(
      await screen.findByText("Reconnectez-vous avec la double authentification."),
    ).toBeTruthy();
  });

  it("un compte de l'école n'ouvre pas de session support", async () => {
    mockApi(routes(me("head")));
    const { router } = renderApp("/support");

    await screen.findByRole("heading", { name: /Bonjour/ });
    expect(router.state.location.pathname).toBe("/");
  });
});
