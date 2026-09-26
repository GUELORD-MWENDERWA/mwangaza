import type { LoginStep } from "./queries";

const PATHS: Record<Exclude<LoginStep, "done">, string> = {
  password: "/login",
  totp: "/login/code",
  new_password: "/login/new-password",
  totp_setup: "/login/two-factor",
};

/** Page de l'étape de connexion ; `done` : la page demandée au départ. */
export function stepPath(step: LoginStep, next: string): string {
  if (step === "done") return next;
  return `${PATHS[step]}${next === "/" ? "" : `?next=${encodeURIComponent(next)}`}`;
}

/** Page où revenir après la connexion : seulement une page de l'application (jamais une autre
 *  adresse). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) {
    return "/";
  }
  return value;
}
