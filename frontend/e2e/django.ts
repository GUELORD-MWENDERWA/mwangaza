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
with use_school(School.objects.get(code="itig-demo")):
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
with use_school(School.objects.get(code="itig-demo")):
    CashSession.objects.filter(closed_at__isnull=True).update(closed_at=timezone.now())`);
}

/** Une dépense de 7,50 $ à payer en espèces, validée d'office (sous le seuil) : son identifiant. */
export function cashExpense(): string {
  const output = manage(
    "shell",
    "-c",
    `from datetime import date
from apps.accounts.models import User
from apps.core.tenancy import use_school
from apps.finance import expenses
from apps.finance.models import ExpenseCategory
from apps.schools.models import School
with use_school(School.objects.get(code="itig-demo")):
    expense, _ = expenses.record_expense(actor=User.objects.get(phone="+243000001005"),
        category=ExpenseCategory.objects.order_by("name").first(), beneficiary="Ets Kahindo",
        reason="Cadenas du magasin", amount_minor=750, currency="USD",
        spent_on=date.today(), account="cash")
    print(expense.pk)`,
  );
  return output.trim().split("\n").at(-1)!;
}

/** Sorties de caisse d'une dépense au serveur : nombre, numéro du bon, état de la dépense et
 *  attendu en dollars de la session, séparés par « | ». */
export function cashOutOf(expense: string): string[] {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.finance import services
from apps.finance.models import CashOut, Expense
from apps.schools.models import School
with use_school(School.objects.get(code="itig-demo")):
    outs = list(CashOut.objects.filter(expense_id="${expense}"))
    usd = [c for c in services.closing_summary(outs[0].cash_session)["currencies"] if c["currency"] == "USD"]
    print(len(outs), outs[0].number, Expense.objects.get(pk="${expense}").status, usd[0]["expected_minor"], sep="|")`,
  );
  return output.trim().split("\n").at(-1)!.split("|");
}

/** Ajoute ou retire une permission aux rôles d'un compte de l'ITIG de démonstration (ex. une
 *  caissière qui inscrit aussi, HL.1). */
export function setPermission(phone: string, permission: string, granted: boolean) {
  shell(`from apps.accounts.models import Role
from apps.core.tenancy import use_school
from apps.schools.models import School
with use_school(School.objects.get(code="itig-demo")):
    for role in Role.objects.filter(memberships__user__phone="${phone}"):
        others = [code for code in role.permissions if code != "${permission}"]
        role.permissions = [*others, "${permission}"] if ${granted ? "True" : "False"} else others
        role.save()`);
}

/** Élèves de l'ITIG de démonstration à ce nom au serveur : nombre, matricule, nombre de
 *  paiements et total reçu (centimes), séparés par « | ». */
export function studentsNamed(lastName: string): string[] {
  const output = manage(
    "shell",
    "-c",
    `from apps.core.tenancy import use_school
from apps.finance.models import Payment
from apps.schools.models import School
from apps.students.models import Student
with use_school(School.objects.get(code="itig-demo")):
    found = list(Student.objects.filter(last_name="${lastName}"))
    paid = list(Payment.objects.filter(enrollment__student__in=found))
    matricule = found[0].matricule if found else ""
    print(len(found), matricule, len(paid), sum(p.received_amount_minor for p in paid), sep="|")`,
  );
  return output.trim().split("\n").at(-1)!.split("|");
}

/** Deux élèves inscrits de l'ITIG de démonstration, sans pointage aujourd'hui (pointage à l'entrée). */
export function studentsToScan(): string[] {
  const output = manage(
    "shell",
    "-c",
    `from django.utils import timezone
from apps.core.tenancy import use_school
from apps.schools.models import School
from apps.students.models import Enrollment
with use_school(School.objects.get(code="itig-demo")):
    rows = (Enrollment.objects.filter(status="active").exclude(student__attendance_records__session__date=timezone.localdate())
            .select_related("student").order_by("-student__matricule")[:2])
    print("|".join(e.student.matricule for e in rows))`,
  );
  return output.trim().split("\n").at(-1)!.split("|");
}

/** Nombre de pointages d'un élève aujourd'hui, côté serveur. */
export function scansToday(matricule: string): number {
  const output = manage(
    "shell",
    "-c",
    `from django.utils import timezone
from apps.attendance.models import AttendanceRecord
print(AttendanceRecord.all_schools.filter(student__matricule="${matricule}", session__date=timezone.localdate()).count())`,
  );
  return Number(output.trim().split("\n").at(-1));
}
