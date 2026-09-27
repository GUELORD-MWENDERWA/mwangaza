// Commandes Django des parcours : données de démonstration, code de double authentification.
import { execFileSync } from "node:child_process";

const backend = new URL("../../backend", import.meta.url).pathname;

export function manage(...args: string[]): string {
  return execFileSync("uv", ["run", "python", "manage.py", ...args], {
    cwd: backend,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
}

/** Code du moment (clé commune des comptes de `make demo`, ou `key`) ; si le code expire dans
 *  moins de 5 secondes, celui d'après. */
export async function totp(key?: string): Promise<string> {
  for (;;) {
    const output = manage("totp", ...(key ? ["--key", key] : []));
    const left = Number(/(\d+)\s*s\)/.exec(output)?.[1] ?? 30);
    if (left >= 5) return output.split("(")[0]!.replace(/\D/g, "");
    await new Promise((resolve) => setTimeout(resolve, (left + 1) * 1000));
  }
}

/** Code Python exécuté dans `manage.py shell` (ex. suspendre l'école de démonstration). */
export function shell(code: string) {
  manage("shell", "-c", code);
}

/** Un code ne sert qu'une fois par compte : pour reconnecter un compte de démonstration déjà
 *  connecté par un autre parcours dans la même période de 30 s, on oublie le dernier code. */
export function allowCodeAgain(phone: string) {
  shell(
    `from apps.accounts.models import User; User.objects.filter(phone='${phone}').update(totp_last_step=0)`,
  );
}
