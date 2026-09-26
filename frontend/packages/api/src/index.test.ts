// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, call, ensureCsrf } from "./index";

function reply(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return vi.fn(async (request: Request) => {
    void request;
    return new Response(body === null ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json", ...headers },
    });
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("client de l'API", () => {
  it("renvoie les données d'une réponse réussie", async () => {
    vi.stubGlobal("fetch", reply({ step: "totp" }));

    const data = await call(api.GET("/api/auth/login/"));

    expect(data).toEqual({ step: "totp" });
  });

  it("erreur de l'API : code, erreurs de champ et temps d'attente", async () => {
    vi.stubGlobal(
      "fetch",
      reply(
        {
          code: "invalid",
          detail: "Some fields are invalid.",
          fields: { new_password: [{ code: "password_too_short", detail: "…" }] },
        },
        400,
        { "Retry-After": "600" },
      ),
    );

    const error = await call(
      api.POST("/api/auth/password/", { body: { new_password: "x" } }),
    ).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect([apiError.status, apiError.code]).toEqual([400, "invalid"]);
    expect(apiError.fields.new_password?.[0]?.code).toBe("password_too_short");
    expect(apiError.retryAfter).toBe(600);
  });

  it("pas de réponse du serveur : erreur « network »", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    const error = (await call(api.GET("/api/me/")).catch((caught: unknown) => caught)) as ApiError;

    expect([error.status, error.code]).toEqual([0, "network"]);
  });

  it("réponse sans code (proxy, 502) : un code tiré du statut", async () => {
    vi.stubGlobal("fetch", reply(null, 502));

    const error = (await call(api.GET("/api/me/")).catch((caught: unknown) => caught)) as ApiError;

    expect(error.code).toBe("http_502");
  });

  it("jeton CSRF relu dans le cookie à chaque envoi, jamais pour une lecture", async () => {
    const fetch = reply({ step: "done" });
    vi.stubGlobal("fetch", fetch);
    document.cookie = "csrftoken=first";
    await call(api.POST("/api/auth/logout/"));
    document.cookie = "csrftoken=second";
    await call(api.POST("/api/auth/logout/"));
    await call(api.GET("/api/auth/login/"));

    const tokens = fetch.mock.calls.map(([request]) => request.headers.get("X-CSRFToken"));
    expect(tokens).toEqual(["first", "second", null]);
  });

  it("cookie CSRF demandé seulement s'il manque", async () => {
    const fetch = reply(null, 204);
    vi.stubGlobal("fetch", fetch);

    await ensureCsrf();
    document.cookie = "csrftoken=present";
    await ensureCsrf();

    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
