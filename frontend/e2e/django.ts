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

/** Un élève de la démonstration qui n'a encore rien payé et doit des frais en dollars. */
export function unpaidStudent(): { matricule: string; name: string } {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig")):
    e = (Enrollment.objects.filter(status="active", payments__isnull=True, charges__currency="USD",
         charges__status="active").select_related("student").order_by("student__matricule").first())
    print(e.student.matricule, "|", e.student.last_name.upper(), e.student.middle_name.upper(), e.student.first_name)`,
  );
  // Dernière ligne : le shell annonce d'abord ses imports automatiques.
  const [matricule, name] = output.trim().split("\n").at(-1)!.split(" | ");
  return { matricule: matricule!, name: name!.replace(/\s+/g, " ") };
}

/** Sessions de caisse laissées ouvertes par d'autres parcours : clôturées, comme par `make demo`. */
export function closeCashSessions() {
  shell(`from django.utils import timezone
from apps.core.tenancy import use_school
from apps.finance.models import CashSession
from apps.schools.models import School
with use_school(School.objects.get(code="itig")):
    CashSession.objects.filter(closed_at__isnull=True).update(closed_at=timezone.now())`);
}
