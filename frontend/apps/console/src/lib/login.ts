import type { LoginStep } from "./queries";

// Première connexion (mot de passe provisoire, double authentification à activer) : terminée dans
// l'administration de dépannage, à la même adresse (même session).
const PATHS: Record<Exclude<LoginStep, "done">, string> = {
  password: "/login",
  totp: "/login/code",
  new_password: "/login/finish",
  totp_setup: "/login/finish",
};

/** Page de l'étape de connexion ; `done` : la page demandée au départ. */
export function stepPath(step: LoginStep, next: string): string {
  if (step === "done") return next;
  return `${PATHS[step]}${next === "/" ? "" : `?next=${encodeURIComponent(next)}`}`;
}

/** Page où revenir après la connexion : seulement une page de la console (jamais une autre
 *  adresse). */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) {
    return "/";
  }
  return value;
}
