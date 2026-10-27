// Fiche de cotes reçue (NB.1, maquette `notes-fiche-cotes`) : le total de chaque élève dans un
// cours et une période (examens : leur propre fiche), une fois envoyée et signée par l'enseignant ;
// ses évaluations restent dans son carnet. Le directeur des études (`grades.validate`) la valide ou
// la renvoie avec ses remarques ; le titulaire et le secrétariat la lisent. `?course=…&term=…`.
import { api, call } from "@mwangaza/api";
import { firstErrorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  Icon,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { type TotalsSheet, useTotalsSheet } from "./data";
import { ReasonDialog, SheetHistory } from "./SheetControl";
import { percent, serverTenths } from "./sheet";

type State = "draft" | "submitted" | "validated" | "returned";
const TONES = { draft: "gray", submitted: "info", validated: "ok", returned: "warn" } as const;

export function GradeTotalsPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const course = params.get("course") ?? "";
  const term = params.get("term") ?? "";
  const sheet = useTotalsSheet(course, term);

  if (!course || !term) return <Banner tone="info">{t("gradeTotals.missing")}</Banner>;
  if (sheet.isPending) return <Skeleton label={t("common.loading")} />;
  if (sheet.isError) return <LoadError error={sheet.error} onRetry={() => void sheet.refetch()} />;
  return <Totals data={sheet.data} />;
}

function Totals({ data }: { data: TotalsSheet }) {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [returning, setReturning] = useState(false);
  const [done, setDone] = useState<"validate" | "reopen" | null>(null);
  const canValidate = can(me, ["grades.validate"]);
  const path = { params: { path: { id: data.course.id, term: data.term } } };

  const act = useMutation({
    mutationFn: (input: { action: "validate" | "reopen"; reason?: string }) =>
      input.action === "validate"
        ? call(api.POST("/api/courses/{id}/terms/{term}/grades/validate/", path))
        : call(
            api.POST("/api/courses/{id}/terms/{term}/grades/reopen/", {
              ...path,
              body: { reason: input.reason ?? "" },
            }),
          ),
    onSuccess: (saved, input) => {
      queryClient.setQueryData([...keys.gradeSheet, "totals", data.course.id, data.term], saved);
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
      setReturning(false);
      setDone(input.action);
    },
  });

  const when = (value: string | null) =>
    value ? formatDateTime(value, i18n.language, school.timezone) : "";
  const state: State = data.status === "draft" && data.returned ? "returned" : data.status;
  const totals = data.students.flatMap((row) => (row.total ? [serverTenths(row.total)] : []));
  const decimal = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 });
  const show = (tenths: number) => decimal.format(tenths / 10);
  // Sous la moitié du maximum (dixièmes de point).
  const below = (tenths: number) => {
    return 2 * tenths < 10 * data.maximum;
  };

  return (
    <>
      <PageHeader
        title={t("gradeTotals.title")}
        subtitle={t("gradeTotals.subtitle", {
          course: data.course.name,
          className: data.class_group,
          term: data.term_label,
          max: data.maximum,
        })}
        crumbs={
          canValidate ? (
            <Link to="/grade-validation" className="underline">
              {t("gradeTotals.back")}
            </Link>
          ) : undefined
        }
        actions={
          <>
            <StatusPill tone={TONES[state]}>{t(`gradeTotals.status.${state}`)}</StatusPill>
            <Button asChild variant="outline">
              <Link to={`/grade-sheets?course=${data.course.id}`}>
                <Icon name="print" size={16} />
                {t("gradeTotals.print")}
              </Link>
            </Button>
          </>
        }
      />
      <div className="mb-4 flex flex-col gap-3">
        {done && <Banner tone="ok">{t(`gradeTotals.done.${done}`)}</Banner>}
        {act.isError && <Banner tone="due">{firstErrorMessage(act.error, t)}</Banner>}
        {state === "draft" && <Banner tone="info">{t("gradeTotals.notSent")}</Banner>}
        {state === "returned" && data.returned && (
          <Banner tone="warn">
            {t("gradeTotals.returned", {
              name: data.returned.by,
              date: when(data.returned.at),
              remarks: data.returned.reason,
            })}
          </Banner>
        )}
        {(state === "submitted" || state === "validated") && (
          <Banner tone={state === "validated" ? "ok" : "info"}>
            {data.submitted_by
              ? t("gradeTotals.signed", { name: data.submitted_by, date: when(data.submitted_at) })
              : t("gradeTotals.signedAt", { date: when(data.submitted_at) })}
            {state === "validated" &&
              ` ${t("gradeTotals.validated", { name: data.validated_by, date: when(data.validated_at) })}`}
          </Banner>
        )}
      </div>
      {data.students.length > 0 && (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader className="flex-wrap gap-y-1">
              <CardTitle className="whitespace-nowrap">
                {t("gradeTotals.students", { count: data.students.length })}
              </CardTitle>
              <span className="text-sm text-ink-3">{t("gradeTotals.studentsHelp")}</span>
            </CardHeader>
            <Table stacked freeze>
              <thead>
                <tr>
                  <th>{t("gradeTotals.columns.student")}</th>
                  <th className="text-right">
                    {t("gradeTotals.columns.total", { max: data.maximum })}
                  </th>
                  <th className="text-right">{t("gradeTotals.columns.percent")}</th>
                </tr>
              </thead>
              <tbody>
                {data.students.map((row, index) => {
                  const tenths = row.total ? serverTenths(row.total) : null;
                  const low = tenths !== null && below(tenths);
                  return (
                    <tr key={row.enrollment_id}>
                      <td>
                        <span className="inline-block min-w-6 text-ink-3">{index + 1}</span>
                        <b>{row.full_name}</b>
                      </td>
                      <td
                        className={low ? "text-right text-due" : "text-right"}
                        data-label={t("gradeTotals.columns.total", { max: data.maximum })}
                      >
                        {tenths === null ? (
                          "—"
                        ) : (
                          <span>
                            <b>{show(tenths)}</b> / {data.maximum}
                          </span>
                        )}
                      </td>
                      <td
                        className={low ? "text-right text-due" : "text-right"}
                        data-label={t("gradeTotals.columns.percent")}
                      >
                        {tenths === null
                          ? "—"
                          : t("grades.percentValue", { value: percent(tenths, data.maximum) })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
            {canValidate && (
              <CardFooter>
                <span className="text-sm text-ink-2">{t("gradeTotals.hint")}</span>
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="outline"
                    disabled={act.isPending}
                    onClick={() => setReturning(true)}
                  >
                    {t("gradeTotals.sendBack")}
                  </Button>
                  {data.status === "submitted" && (
                    <Button
                      disabled={act.isPending}
                      onClick={() => act.mutate({ action: "validate" })}
                    >
                      <Icon name="check" size={16} />
                      {t("gradeTotals.validate")}
                    </Button>
                  )}
                </div>
              </CardFooter>
            )}
          </Card>
          <div className="flex flex-col gap-4">
            <Summary totals={totals} maximum={data.maximum} show={show} below={below} />
            <SheetHistory
              sheet={data}
              language={i18n.language}
              timeZone={school.timezone}
              className=""
            />
          </div>
        </div>
      )}
      {data.students.length === 0 && (
        <SheetHistory sheet={data} language={i18n.language} timeZone={school.timezone} />
      )}
      {returning && (
        <ReasonDialog
          kind="reopen"
          pending={act.isPending}
          onClose={() => setReturning(false)}
          onConfirm={(reason) => act.mutate({ action: "reopen", reason })}
        />
      )}
    </>
  );
}

/** Moyenne, plus haute et plus basse note, élèves sous la moitié (comme la fiche imprimée). */
function Summary({
  totals,
  maximum,
  show,
  below,
}: {
  totals: number[];
  maximum: number;
  show: (tenths: number) => string;
  below: (tenths: number) => boolean;
}) {
  const { t } = useTranslation();
  if (totals.length === 0) return null;
  const average = Math.round(totals.reduce((sum, value) => sum + value, 0) / totals.length);
  const under = totals.filter(below).length;
  const rows: [string, string, boolean][] = [
    [
      t("gradeTotals.summary.average"),
      t("gradeTotals.summary.averageValue", {
        value: show(average),
        max: maximum,
        percent: percent(average, maximum),
      }),
      false,
    ],
    [t("gradeTotals.summary.highest"), show(Math.max(...totals)), false],
    [t("gradeTotals.summary.lowest"), show(Math.min(...totals)), false],
    [
      t("gradeTotals.summary.below"),
      t("gradeTotals.summary.belowValue", { count: under }),
      under > 0,
    ],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("gradeTotals.summary.title")}</CardTitle>
      </CardHeader>
      <dl className="py-2">
        {rows.map(([label, value, alert]) => (
          <div key={label} className="flex items-center justify-between gap-3 px-5 py-2">
            <dt className="text-sm text-ink-3">{label}</dt>
            <dd className={alert ? "font-bold text-due" : "font-bold"}>{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
