// Faux serveur pour les tests d'écrans : `fetch` remplacé, réponses par « MÉTHODE /chemin ».
import type { Schemas } from "@mwangaza/api";
import { vi } from "vitest";

type Reply = Response | object | ((request: Request) => Response | object | Promise<Response>);
export type Routes = Record<string, Reply>;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function apiError(
  code: string,
  status: number,
  extra: {
    fields?: Schemas["Error"]["fields"];
    retryAfter?: number;
    body?: Record<string, unknown>;
  } = {},
) {
  return json(
    { code, detail: code, ...(extra.fields ? { fields: extra.fields } : {}), ...extra.body },
    status,
    extra.retryAfter ? { "Retry-After": String(extra.retryAfter) } : {},
  );
}

export const noContent = () => new Response(null, { status: 204 });

/** Corps JSON, sinon le texte tel quel (envoi d'un fichier). */
function parse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Remplace `fetch` ; les routes peuvent être changées pendant le test (`routes[…] = …`).
 *  Renvoie les requêtes reçues, avec leur corps JSON. */
export function mockApi(routes: Routes) {
  const requests: {
    method: string;
    path: string;
    query: Record<string, string>;
    body: unknown;
  }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const text = request.method === "GET" ? "" : await request.clone().text();
      requests.push({
        method: request.method,
        path: url.pathname,
        query: Object.fromEntries(url.searchParams),
        body: text ? parse(text) : null,
      });
      const reply = routes[`${request.method} ${url.pathname}`];
      if (reply === undefined) return apiError("not_found", 404);
      const value = typeof reply === "function" ? await reply(request) : reply;
      return value instanceof Response ? value : json(value);
    }),
  );
  return requests;
}

/** Pas de réseau : `fetch` échoue. */
export function offline() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }),
  );
}
