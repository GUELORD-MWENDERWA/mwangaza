// Fiche d'une école dans la console (5.3) : noms, adresse et abonnement ; suspendre (après
// confirmation) ou réactiver ; derniers changements (journal de la plateforme). Couleur, fuseau,
// devises et logo sont réglés par l'école elle-même (M5).
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  errorMessage,
  formatDateTime,
  formatDay,
  type TFunction,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  PageHeader,
  Skeleton,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useParams } from "react-router";

import { keys } from "../../lib/queries";
import { SupportLink } from "./SchoolsPage";
import {
  IdentityFields,
  SCHOOL_FIELDS,
  SchoolValues,
  SubscriptionFields,
  SubscriptionPill,
  schoolBody,
  useSchoolSchema,
} from "./schoolForm";

type Detail = Schemas["ConsoleSchoolDetail"];
type Change = Schemas["PlatformChange"];

const valuesOf = (school: Detail): SchoolValues => ({
  name: school.name,
  official_name: school.official_name,
  code: school.code,
  // Suspendue : le champ est grisé, la valeur n'est pas envoyée.
  status: school.status === "active" ? "active" : "trial",
  plan: school.plan,
  trial_ends_on: school.trial_ends_on ?? "",
  paid_until: school.paid_until ?? "",
});

export function SchoolPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const school = useQuery({
    queryKey: [...keys.schools, id],
    queryFn: () => call(api.GET("/api/console/schools/{id}/", { params: { path: { id } } })),
  });
  if (school.isPending) return <Skeleton label={t("common.loading")} />;
  if (school.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(school.error, t)}</Banner>
        <Button variant="outline" className="w-fit" onClick={() => void school.refetch()}>
          {t("common.retry")}
        </Button>
      </>
    );
  }
  return <SchoolForm key={school.data.id} school={school.data} />;
}

function SchoolForm({ school }: { school: Detail }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const suspended = school.status === "suspended";
  const form = useForm<SchoolValues>({
    resolver: zodResolver(useSchoolSchema()),
    defaultValues: valuesOf(school),
  });
  const path = { params: { path: { id: school.id } } };
  const saved = (data: Detail) => {
    queryClient.setQueryData([...keys.schools, school.id], data);
    // La liste ; pas cette fiche, déjà à jour.
    void queryClient.invalidateQueries({
      queryKey: keys.schools,
      predicate: (query) => query.queryKey[2] !== school.id,
    });
    void queryClient.invalidateQueries({ queryKey: keys.dashboard });
    form.reset(valuesOf(data));
  };
  const save = useMutation({
    mutationFn: (values: SchoolValues) => {
      const { status, ...body } = schoolBody(values);
      return call(
        api.PATCH("/api/console/schools/{id}/", {
          ...path,
          body: suspended ? body : { ...body, status },
        }),
      );
    },
    onSuccess: saved,
    onError: (error) => setGeneral(applyServerErrors(error, [...SCHOOL_FIELDS], form.setError, t)),
  });
  const toggle = useMutation({
    mutationFn: () =>
      call(
        suspended
          ? api.POST("/api/console/schools/{id}/reactivate/", path)
          : api.POST("/api/console/schools/{id}/suspend/", path),
      ),
    onSuccess: (data) => {
      setConfirm(false);
      saved(data);
    },
    onError: (error) => {
      setConfirm(false);
      setGeneral(errorMessage(error, t));
    },
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <>
      <PageHeader
        title={school.name}
        subtitle={school.url.replace(/^\w+:\/\//, "")}
        actions={
          <div className="flex flex-wrap gap-2">
            <SupportLink school={school} />
            {suspended ? (
              <Button variant="outline" size="sm" onClick={() => toggle.mutate()}>
                {t("console.schools.reactivate")}
              </Button>
            ) : (
              <Button variant="destructive" size="sm" onClick={() => setConfirm(true)}>
                {t("console.schools.suspend")}
              </Button>
            )}
          </div>
        }
      />
      {suspended && <Banner tone="due">{t("console.schools.suspendedBanner")}</Banner>}
      {general && <Banner tone="due">{general}</Banner>}
      {save.isSuccess && !form.formState.isDirty && (
        <Banner tone="ok" role="status">
          {t("console.schools.saved")}
        </Banner>
      )}
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            save.reset();
            save.mutate(values);
          })}
        >
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.identityTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              <IdentityFields form={form} codeHelp={t("console.schools.fields.codeChangeHelp")} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.subscriptionTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              <SubscriptionFields form={form} suspended={suspended} />
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={save.isPending}>
                {t("console.schools.save")}
              </Button>
            </CardFooter>
          </Card>
        </form>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.summaryTitle")}</CardTitle>
            </CardHeader>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 pt-3 pb-4 text-[.9rem] [&_dt]:text-ink-3">
              <dt>{t("console.schools.subscription")}</dt>
              <dd>
                <SubscriptionPill school={school} />
              </dd>
              <dt>{t("console.schools.students")}</dt>
              <dd className="tabular-nums">{school.student_count.toLocaleString(i18n.language)}</dd>
              <dt>{t("console.schools.lastActivity")}</dt>
              <dd>
                {school.last_activity_at
                  ? formatDateTime(school.last_activity_at, i18n.language, timeZone)
                  : "—"}
              </dd>
              <dt>{t("console.schools.fields.currencies")}</dt>
              <dd>{school.enabled_currencies.join(", ")}</dd>
              <dt>{t("console.schools.createdAt")}</dt>
              <dd>{formatDay(school.created_at.slice(0, 10), i18n.language)}</dd>
            </dl>
          </Card>
          <History changes={school.history} />
        </div>
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("console.schools.suspendTitle", { name: school.name })}
        confirmLabel={t("console.schools.suspend")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => toggle.mutate()}
        pending={toggle.isPending}
        destructive
      >
        {t("console.schools.suspendText")}
      </ConfirmDialog>
    </>
  );
}

function History({ changes }: { changes: Change[] }) {
  const { t, i18n } = useTranslation();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.historyTitle")}</CardTitle>
      </CardHeader>
      {changes.length === 0 && (
        <CardContent className="text-[.9rem] text-ink-3">
          {t("console.identity.noChange")}
        </CardContent>
      )}
      <ul className="m-0 list-none p-0">
        {changes.map((change) => (
          <li
            key={change.id}
            className="flex flex-col gap-0.5 border-t border-line px-4 py-2.5 text-[.9rem] first:border-t-0"
          >
            <b>{t(`console.actions.${change.action}`)}</b>
            <span className="text-[.82rem] text-ink-3">
              {formatDateTime(change.created_at, i18n.language, timeZone)}
              {change.actor && ` · ${[change.actor.first_name, change.actor.last_name].join(" ")}`}
            </span>
            {change.action === "school.updated" && <Differences change={change} t={t} />}
          </li>
        ))}
      </ul>
    </Card>
  );
}

const SHOWN = new Set<string>(SCHOOL_FIELDS);

function Differences({ change, t }: { change: Change; t: TFunction }) {
  const before = (change.before ?? {}) as Record<string, string | null>;
  const after = (change.after ?? {}) as Record<string, string | null>;
  const shown = (field: string, value: string | null | undefined) =>
    !value
      ? t("console.identity.empty")
      : field === "status"
        ? t(`console.schools.status.${value as "trial"}`)
        : value;
  return (
    <>
      {Object.keys(after)
        .filter((field) => SHOWN.has(field))
        .map((field) => (
          <span key={field} className="text-[.85rem] break-words">
            {t("console.identity.difference", {
              field: t(`console.schools.fields.${field as (typeof SCHOOL_FIELDS)[number]}`),
              before: shown(field, before[field]),
              after: shown(field, after[field]),
            })}
          </span>
        ))}
    </>
  );
}
