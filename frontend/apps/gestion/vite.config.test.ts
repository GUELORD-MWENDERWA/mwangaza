import { beforeEach, describe, expect, it, vi } from "vitest";

// Le proxy de développement reproduit la production : l'API est sur la même origine que
// l'application, et le sous-domaine de l'école (itig-demo.localhost) arrive tel quel à Django.
async function loadConfig() {
  vi.resetModules();
  return (await import("./vite.config")).default;
}

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.stubEnv("VITE_API_TARGET", undefined);
  vi.stubEnv("VITE_HOST", undefined);
});

describe("serveur de développement de la Gestion", () => {
  it("sert l'application sous /app/ sur le port 5173", async () => {
    const config = await loadConfig();

    expect(config.base).toBe("/app/");
    expect(config.server?.port).toBe(5173);
    expect(config.server?.strictPort).toBe(true);
  });

  it("transmet /api, /admin et /static à Django sans changer l'hôte", async () => {
    const config = await loadConfig();
    const proxy = config.server?.proxy ?? {};

    for (const path of ["/api", "/admin", "/static"]) {
      expect(proxy[path]).toEqual({ target: "http://localhost:8000", changeOrigin: false });
    }
  });

  it("accepte les sous-domaines des écoles", async () => {
    const config = await loadConfig();

    expect(config.server?.allowedHosts).toContain(".localhost");
  });

  it("vise le conteneur Django sous Docker (make dev)", async () => {
    vi.stubEnv("VITE_API_TARGET", "http://backend:8000");
    vi.stubEnv("VITE_HOST", "0.0.0.0");
    const config = await loadConfig();

    expect(config.server?.proxy?.["/api"]).toEqual({
      target: "http://backend:8000",
      changeOrigin: false,
    });
    expect(config.server?.host).toBe("0.0.0.0");
  });
});
