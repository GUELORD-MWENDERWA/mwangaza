// Écoles dans la console (5.3) : champs communs à la création et à la fiche (identité,
// abonnement) et étiquette de l'abonnement. Le serveur vérifie tout (code libre et non réservé,
// devises) ; ici, seulement ce qui évite un aller-retour.
import type { Schemas } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import { Field, Input, Segmented, StatusPill } from "@mwangaza/ui";
import { useMemo } from "react";
import { Controller, type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

export type School = Schemas["ConsoleSchool"];
export type SchoolStatus = Schemas["SchoolStatusEnum"];
export type SchoolKind = Schemas["SchoolEnvironmentEnum"];

/** Types d'espace (4.15), dans l'ordre des onglets : réel, essai, démonstration. */
export const KINDS = ["live", "test", "demo"] as const satisfies readonly SchoolKind[];

/** Suspendue, arrêtée ou en cours de suppression : personne n'y entre, pas de session support. */
export const isClosed = (school: Pick<School, "status">) =>
  school.status === "suspended" || school.status === "stopped" || school.status === "deleting";

export const SCHOOL_FIELDS = [
  "name",
  "official_name",
  "code",
  "status",
  "plan",
  "trial_ends_on",
  "paid_until",
] as const;

const CODE = /^[a-z0-9][a-z0-9-]{0,28}[a-z0-9]$/;

/** Date du jour sur l'appareil, `AAAA-MM-JJ` (comparable aux dates du serveur). */
export const today = () => new Date().toLocaleDateString("en-CA");

export function useSchoolSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z.object({
        name: z.string().trim().min(1, t("validation.nameRequired")).max(200),
        official_name: z.string().trim().max(255),
        code: z.string().trim().regex(CODE, t("console.schools.fields.codeFormat")),
        status: z.enum(["trial", "active"]),
        plan: z.string().trim().max(50),
        trial_ends_on: z.string(),
        paid_until: z.string(),
      }),
    [t],
  );
}

export type SchoolValues = z.infer<ReturnType<typeof useSchoolSchema>>;

/** Valeurs envoyées au serveur : une date vide devient `null`. */
export const schoolBody = (values: SchoolValues) => ({
  ...values,
  trial_ends_on: values.trial_ends_on || null,
  paid_until: values.paid_until || null,
});

type Form<T extends FieldValues> = UseFormReturn<T>;

/** Nom, nom officiel et code (adresse) de l'école. */
export function IdentityFields<T extends SchoolValues>({
  form,
  codeHelp,
}: {
  form: Form<T>;
  codeHelp: string;
}) {
  const { t } = useTranslation();
  const field = (name: "name" | "official_name" | "code", help?: string, maxLength?: number) => (
    <Field
      id={`school-${name}`}
      label={t(`console.schools.fields.${name}`)}
      help={help}
      error={form.getFieldState(name as Path<T>, form.formState).error?.message}
    >
      {(control) => (
        <Input
          {...control}
          maxLength={maxLength}
          autoCapitalize={name === "code" ? "none" : undefined}
          {...form.register(name as Path<T>)}
        />
      )}
    </Field>
  );
  return (
    <>
      {field("name", t("console.schools.fields.nameHelp"), 200)}
      {field("official_name", t("console.schools.fields.officialNameHelp"), 255)}
      {field("code", codeHelp, 30)}
    </>
  );
}

/** Abonnement saisi à la main (sans facturation, 9.2) : essai gratuit ou active, offre, dates.
 *  `lockedHelp` : école suspendue ou arrêtée, l'état ne se change pas ici. */
export function SubscriptionFields<T extends SchoolValues>({
  form,
  lockedHelp,
}: {
  form: Form<T>;
  lockedHelp?: string;
}) {
  const { t } = useTranslation();
  const date = (name: "trial_ends_on" | "paid_until") => (
    <Field
      id={`school-${name}`}
      label={t(`console.schools.fields.${name}`)}
      error={form.getFieldState(name as Path<T>, form.formState).error?.message}
    >
      {(control) => <Input {...control} type="date" {...form.register(name as Path<T>)} />}
    </Field>
  );
  return (
    <>
      <Field
        id="school-status"
        label={t("console.schools.fields.status")}
        help={lockedHelp}
        error={form.getFieldState("status" as Path<T>, form.formState).error?.message}
      >
        {() => (
          <Controller
            control={form.control}
            name={"status" as Path<T>}
            render={({ field }) => (
              <Segmented
                label={t("console.schools.fields.status")}
                value={field.value as "trial" | "active"}
                onValueChange={field.onChange}
                disabled={lockedHelp !== undefined}
                options={(["trial", "active"] as const).map((value) => ({
                  value,
                  label: t(`console.schools.status.${value}`),
                }))}
              />
            )}
          />
        )}
      </Field>
      <Field
        id="school-plan"
        label={t("console.schools.fields.plan")}
        help={t("console.schools.fields.planHelp")}
        error={form.getFieldState("plan" as Path<T>, form.formState).error?.message}
      >
        {(control) => <Input {...control} maxLength={50} {...form.register("plan" as Path<T>)} />}
      </Field>
      {date("trial_ends_on")}
      {date("paid_until")}
    </>
  );
}

/** Étiquette de l'abonnement : arrêtée, suspendue, essai gratuit jusqu'au…, offre payée
 *  jusqu'au… (échéance dépassée en orange). */
export function SubscriptionPill({ school }: { school: School }) {
  const { t, i18n } = useTranslation();
  const day = (value: string) => formatDay(value, i18n.language);
  if (school.status === "stopped" || school.status === "deleting") {
    return <StatusPill tone="gray">{t(`console.schools.status.${school.status}`)}</StatusPill>;
  }
  if (school.status === "suspended") {
    return <StatusPill tone="due">{t("console.schools.status.suspended")}</StatusPill>;
  }
  if (school.status === "trial") {
    return (
      <StatusPill tone="info">
        {school.trial_ends_on
          ? t("console.schools.trialUntil", { date: day(school.trial_ends_on) })
          : t("console.schools.status.trial")}
      </StatusPill>
    );
  }
  const late = !!school.paid_until && school.paid_until < today();
  const parts = [school.plan || t("console.schools.status.active")];
  if (school.paid_until) {
    const key = late ? "console.schools.overdue" : "console.schools.paidUntil";
    parts.push(t(key, { date: day(school.paid_until) }));
  }
  return <StatusPill tone={late ? "warn" : "ok"}>{parts.join(" · ")}</StatusPill>;
}
