// Liste « Mise en route » d'une école neuve (C4) : en haut du tableau de bord du directeur tant
// que l'école ne l'a pas terminée. Chaque étape mène à son écran et se coche seule.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Icon,
  Tag,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { can, type Permission } from "../../lib/permissions";
import { keys, type School, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";

type Step = Schemas["Setup"]["steps"][number];

// Écran de chaque étape, avec le droit qu'il demande (le lien est caché sans lui).
const SCREENS: Record<Step["key"], { to: string; permissions: readonly Permission[] }> = {
  year: { to: "/organisation", permissions: ["classes.manage"] },
  classes: { to: "/organisation", permissions: ["classes.manage"] },
  fees: { to: "/fees", permissions: ["finance.configure_fees", "finance.set_exchange_rate"] },
  staff: { to: "/staff", permissions: ["roles.manage"] },
  cash: { to: "/settings", permissions: ["school.configure"] },
  students: { to: "/students", permissions: ["students.view"] },
  prior: { to: "/fees/prior-payments", permissions: ["finance.import_prior_payments"] },
  invitations: { to: "/students/invitations", permissions: ["students.view"] },
};

export function SetupChecklist() {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const queryClient = useQueryClient();
  // Une école qui a fini ne demande plus jamais la liste.
  const wanted = !school.setup_done && can(me, ["school.configure"]);
  const setup = useQuery({
    queryKey: keys.setup,
    queryFn: () => call(api.GET("/api/school/setup/")),
    enabled: wanted,
  });
  const finish = useMutation({
    mutationFn: () => call(api.POST("/api/school/setup/finish/")),
    onSuccess: () => {
      queryClient.setQueryData(keys.school, (current: School | undefined) =>
        current ? { ...current, setup_done: true } : current,
      );
    },
  });
  // Sans réseau ou en erreur : le tableau de bord s'affiche sans la liste. Terminée depuis un
  // autre appareil : plus rien à montrer.
  if (!wanted || !setup.data || setup.data.finished_at) return null;

  const { steps, ready } = setup.data;
  const required = steps.filter((step) => !step.optional);
  const next = steps.find((step) => !step.done && !step.optional);

  return (
    <Card aria-labelledby="setup-title">
      <CardHeader>
        <div className="min-w-0">
          <CardTitle id="setup-title">{t("setup.title")}</CardTitle>
          <p className="text-sm text-ink-3">{t("setup.subtitle")}</p>
        </div>
        <Tag className="shrink-0">
          {t("setup.progress", {
            done: required.filter((step) => step.done).length,
            total: required.length,
          })}
        </Tag>
      </CardHeader>
      <CardContent className="py-1">
        <ol>
          {steps.map((step, index) => {
            const screen = SCREENS[step.key];
            const current = step === next;
            return (
              <li
                key={step.key}
                className="flex items-center gap-3 border-b border-line-soft py-3 last:border-b-0"
              >
                <span
                  aria-hidden
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-full text-sm font-bold",
                    step.done
                      ? "bg-ok-50 text-ok"
                      : current
                        ? "bg-lake text-white"
                        : "bg-gray-50 text-ink-3",
                  )}
                >
                  {step.done ? <Icon name="check" size={16} /> : index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={cn("font-bold", step.done && "text-ink-3")}>
                    {t(`setup.steps.${step.key}.title`)}{" "}
                    {step.optional && <Tag>{t("setup.optional")}</Tag>}
                    <span className="sr-only">
                      {" "}
                      — {t(step.done ? "setup.stateDone" : "setup.stateTodo")}
                    </span>
                  </div>
                  {!step.done && (
                    <p className="text-sm text-ink-3">{t(`setup.steps.${step.key}.hint`)}</p>
                  )}
                </div>
                {can(me, screen.permissions) && (
                  <Button
                    asChild
                    size="sm"
                    variant={current ? "default" : step.done ? "ghost" : "outline"}
                    className="shrink-0"
                  >
                    <Link
                      to={screen.to}
                      aria-label={t("setup.openStep", {
                        step: t(`setup.steps.${step.key}.title`),
                      })}
                    >
                      {t(step.done ? "setup.see" : "setup.open")}
                    </Link>
                  </Button>
                )}
              </li>
            );
          })}
        </ol>
        {finish.isError && (
          <Banner tone="due" icon="alert" className="mb-3">
            {errorMessage(finish.error, t)}
          </Banner>
        )}
      </CardContent>
      {ready && (
        <CardFooter>
          <span className="min-w-0 flex-1 text-sm text-ink-2">{t("setup.ready")}</span>
          <Button disabled={finish.isPending} onClick={() => finish.mutate()}>
            {t("setup.finish")}
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
