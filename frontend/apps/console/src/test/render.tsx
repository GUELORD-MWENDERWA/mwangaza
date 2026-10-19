// Tests d'écrans de la console : toute l'application, `fetch` remplacé par un faux
// serveur (réponses par « MÉTHODE /chemin »).
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { createQueryClient } from "../lib/queryClient";
import { ALL_RIGHTS } from "../lib/rights";
import { routes } from "../routes";

/** Rôle et droits du propriétaire de la plateforme (EQ.1) : le compte des tests d'écrans. */
export const OWNER = { platform_roles: ["owner"], platform_permissions: ALL_RIGHTS };

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const apiError = (code: string, status: number, fields?: object) =>
  json({ code, detail: code, ...(fields ? { fields } : {}) }, status);

/** Remplace `fetch` ; renvoie les requêtes reçues, avec leur corps JSON. */
export function mockApi(routes: Record<string, Response | object | (() => Response | object)>) {
  const requests: { method: string; path: string; search: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const { pathname, search } = new URL(request.url);
      const text = request.method === "GET" ? "" : await request.clone().text();
      requests.push({
        method: request.method,
        path: pathname,
        search,
        body: text ? JSON.parse(text) : null,
      });
      const reply = routes[`${request.method} ${pathname}`];
      if (reply === undefined) return apiError("not_found", 404);
      const value = typeof reply === "function" ? reply() : reply;
      return value instanceof Response ? value.clone() : json(value);
    }),
  );
  return requests;
}

export function renderApp(path = "/") {
  const queryClient = createQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { user, router };
}
