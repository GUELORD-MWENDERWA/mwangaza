// Client de l'API Mwangaza, typé par le schéma OpenAPI du serveur (`make api` régénère
// `openapi.yaml` puis `src/schema.d.ts`) : une API changée fait échouer la compilation du front.
import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];
export type FieldErrors = Record<string, Schemas["FieldError"][]>;

/** Erreur de l'API : `code` stable (l'interface le traduit), `fields` pour une saisie refusée,
 *  `retryAfter` (secondes) après trop d'essais. `status` 0 : pas de réponse du serveur. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldErrors;
  readonly retryAfter: number | null;
  /** Réponse entière : précisions propres à une erreur (ex. `duplicates`). */
  readonly body: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    detail: string,
    fields: FieldErrors = {},
    retryAfter: number | null = null,
    body: Record<string, unknown> = {},
  ) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
    this.body = body;
  }
}

function cookie(name: string): string | undefined {
  const prefix = `${name}=`;
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}

// Jeton CSRF relu à chaque envoi : Django en change la valeur à la connexion.
const csrf: Middleware = {
  onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      const token = cookie("csrftoken");
      if (token) request.headers.set("X-CSRFToken", token);
    }
    return request;
  },
};

/** Même origine que l'application : cookies de session de l'adresse de l'école. `fetch` lu à
 *  chaque appel (les tests le remplacent). */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  credentials: "same-origin",
  fetch: (request) => globalThis.fetch(request),
});
api.use(csrf);

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Réponse de l'API, ou `ApiError` : `await call(api.GET("/api/me/"))`. */
export async function call<T>(request: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await request;
  } catch {
    throw new ApiError(0, "network", "No response from the server.");
  }
  if (result.response.ok) return result.data as T;
  throw toApiError(result.response, result.error);
}

function toApiError(response: Response, body: unknown): ApiError {
  const error = (typeof body === "object" && body !== null ? body : {}) as Partial<
    Schemas["Error"]
  >;
  const retryAfter = Number(response.headers.get("Retry-After"));
  return new ApiError(
    response.status,
    error.code ?? `http_${response.status}`,
    error.detail ?? response.statusText,
    error.fields ?? {},
    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
    error as Record<string, unknown>,
  );
}

/** Cookie CSRF avant le premier envoi (connexion). */
export function ensureCsrf() {
  if (cookie("csrftoken")) return Promise.resolve();
  return call(api.GET("/api/auth/csrf/")).then(() => undefined);
}
