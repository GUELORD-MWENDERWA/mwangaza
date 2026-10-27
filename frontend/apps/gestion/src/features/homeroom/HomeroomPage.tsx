// Ma classe (NB.3, maquette `titulaire`) : l'espace du titulaire. Pour sa classe et une période (ou
// les examens) : les fiches de cotes reçues et ce qui manque, les chiffres de la classe et la
// vérification élève par élève une fois toutes les fiches validées, puis « Bulletins prêts », que
// le directeur des études voit dans « Suivi des notes ». Le serveur refuse tout autre compte.
import { firstErrorMessage, formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Icon,
  Kpi,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCurrentSchool } from "../../lib/school";
import { termLabels } from "../../lib/terms";
import { gradableTerms } from "../grades/GradesPage";
import { LoadError } from "../status/StatusPages";
import { formatPercent, type HomeroomData, useHomeroom, useReady } from "./data";

const TONES = {
  not_started: "gray",
  in_progress: "warn",
  submitted: "info",
  validated: "ok",
  returned: "due",
} as const;
const GOOD = new Set(["TB", "B"]);

type Filter = "missing" | "all";

export function HomeroomPage() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const [classGroup, setClassGroup] = useState(() => params.get("class") ?? "");
  const [termId, setTermId] = useState("");
  const [filter, setFilter] = useState<Filter>("missing");
  const [confirm, setConfirm] = useState(false);
  const query = useHomeroom(classGroup, termId);
  const ready = useReady();

  if (query.isPending) return <Skeleton label={t("common.loading")} />;
  if (query.isError) {
    return <LoadError error={query.error} onRetry={() => void query.refetch()} />;
  }
  const data = query.data;
  if (!data.class_group) {
    return (
      <>
        <PageHeader title={t("homeroom.title")} />
        <Banner tone="info">{t("homeroom.none")}</Banner>
      </>
    );
  }
  const group = data.class_group;
  const labels = termLabels(data.terms, t);
  const leaves = gradableTerms(data.terms, labels);
  const term = data.term ?? "";
  const termLabel = leaves.find((leaf) => leaf.id === term)?.label ?? "";
  const missing = data.courses.filter((row) => row.course.status !== "validated");
  const shown = filter === "missing" ? missing : data.courses;
  const target = { class_group: group.id, term };
  const pct = (value: string | null | undefined) => formatPercent(value, i18n.language);
  const sheets = (kind: "class" | "ranking") =>
    `/grade-sheets?class=${group.id}&kind=${kind}&column=${term}`;

  return (
    <>
      <PageHeader
        title={t("homeroom.title")}
        subtitle={t(group.is_titular ? "homeroom.subtitle" : "homeroom.subtitleCo", {
          class: group.name,
        })}
        actions={
          <div className="flex flex-wrap gap-3 text-left!">
            {data.classes.length > 1 && (
              <Field id="homeroom-class" label={t("homeroom.classGroup")}>
                {(control) => (
                  <Select
                    {...control}
                    value={group.id}
                    onChange={(event) => setClassGroup(event.target.value)}
                    className="min-w-44"
                  >
                    {data.classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
            {leaves.length > 0 && (
              <Field id="homeroom-term" label={t("homeroom.term")}>
                {(control) => (
                  <Select
                    {...control}
                    value={term}
                    onChange={(event) => setTermId(event.target.value)}
                    className="min-w-44"
                  >
                    {leaves.map((leaf) => (
                      <option key={leaf.id} value={leaf.id}>
                        {leaf.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>
        }
      />
      {ready.isSuccess && (
        <div className="mb-4">
          <Banner tone="ok">
            {t(ready.variables.ready ? "homeroom.done" : "homeroom.withdrawn")}
          </Banner>
        </div>
      )}
      {ready.isError && (
        <div className="mb-4">
          <Banner tone="due">{firstErrorMessage(ready.error, t)}</Banner>
        </div>
      )}
      {!data.term ? (
        <Banner tone="info">{t("homeroom.noTerm")}</Banner>
      ) : (
        <>
          <Figures data={data} pct={pct} />
          <div className="mt-4">
            <Readiness
              data={data}
              titular={group.is_titular}
              missing={missing.length}
              pending={ready.isPending}
              onDeclare={() => setConfirm(true)}
              onWithdraw={() => ready.mutate({ ready: false, ...target })}
            />
          </div>
          <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader className="flex-wrap gap-3">
                  <CardTitle>{t("homeroom.sheets.title")}</CardTitle>
                  <Segmented
                    label={t("homeroom.sheets.title")}
                    value={filter}
                    onValueChange={setFilter}
                    options={[
                      {
                        value: "missing",
                        label: t("homeroom.sheets.missing", { count: missing.length }),
                      },
                      {
                        value: "all",
                        label: t("homeroom.sheets.all", { count: data.courses.length }),
                      },
                    ]}
                  />
                </CardHeader>
                {shown.length === 0 ? (
                  <p className="px-5 py-6 text-sm text-ink-2">
                    {data.courses.length
                      ? t("homeroom.sheets.none")
                      : t("homeroom.sheets.noCourse")}
                  </p>
                ) : (
                  <Table stacked freeze>
                    <thead>
                      <tr>
                        <th>{t("homeroom.columns.course")}</th>
                        <th>{t("homeroom.columns.teacher")}</th>
                        <th>{t("homeroom.columns.status")}</th>
                        <th className="text-right">{t("homeroom.columns.average")}</th>
                        <th className="text-right">{t("homeroom.columns.belowHalf")}</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map(({ course, average, below_half }) => (
                        <tr key={course.id}>
                          <td>
                            <b>{course.name}</b>
                          </td>
                          <td data-label={t("homeroom.columns.teacher")}>
                            {course.teacher || t("homeroom.noTeacher")}
                          </td>
                          <td data-label={t("homeroom.columns.status")}>
                            <StatusPill tone={TONES[course.status]}>
                              {t(`gradeValidation.status.${course.status}`)}
                            </StatusPill>
                          </td>
                          <td
                            data-label={t("homeroom.columns.average")}
                            className="text-right whitespace-nowrap tabular-nums"
                          >
                            {pct(average)}
                          </td>
                          <td
                            data-label={t("homeroom.columns.belowHalf")}
                            className="text-right tabular-nums"
                          >
                            {below_half ?? "—"}
                          </td>
                          <td className="text-right">
                            {(course.status === "submitted" || course.status === "validated") && (
                              <Button asChild size="sm" variant="outline">
                                <Link to={`/grade-sheets/totals?course=${course.id}&term=${term}`}>
                                  <Icon name="file" size={14} />
                                  {t("homeroom.open")}
                                </Link>
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>
              <Card>
                <CardHeader>
                  <div>
                    <CardTitle>{t("homeroom.check.title")}</CardTitle>
                    <p className="text-sm text-ink-3">{t("homeroom.check.subtitle")}</p>
                  </div>
                </CardHeader>
                {!data.complete ? (
                  <p className="px-5 py-6 text-sm text-ink-2">{t("homeroom.check.later")}</p>
                ) : (
                  <Table stacked freeze>
                    <thead>
                      <tr>
                        <th>{t("homeroom.columns.student")}</th>
                        <th className="text-right">{t("homeroom.columns.total")}</th>
                        <th className="text-right">{t("homeroom.columns.percent")}</th>
                        <th className="text-right">{t("homeroom.columns.place")}</th>
                        <th>{t("homeroom.columns.conduct")}</th>
                        <th>{t("homeroom.columns.application")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.students.map((student) => (
                        <tr key={student.enrollment_id}>
                          <td>
                            <span className="mr-2 text-ink-3 tabular-nums">{student.number}</span>
                            <b>{student.full_name}</b>{" "}
                            {student.total.score === null && (
                              <StatusPill tone="due">{t("homeroom.check.missingGrade")}</StatusPill>
                            )}
                          </td>
                          <td
                            data-label={t("homeroom.columns.total")}
                            className="text-right whitespace-nowrap tabular-nums"
                          >
                            {student.total.score === null
                              ? "—"
                              : `${Number(student.total.score).toLocaleString(i18n.language)} / ${student.total.maximum}`}
                          </td>
                          <td
                            data-label={t("homeroom.columns.percent")}
                            className="text-right whitespace-nowrap tabular-nums"
                          >
                            {pct(student.total.percent)}
                          </td>
                          <td
                            data-label={t("homeroom.columns.place")}
                            className="text-right tabular-nums"
                          >
                            {student.total.place ?? "—"}
                          </td>
                          <td data-label={t("homeroom.columns.conduct")}>
                            <Grade value={student.conduct} />
                          </td>
                          <td data-label={t("homeroom.columns.application")}>
                            <Grade value={student.application} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>
            </div>
            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>{t("homeroom.fix.title")}</CardTitle>
                </CardHeader>
                <div className="flex flex-col gap-3 px-5 py-4 text-sm">
                  <p>{t("homeroom.fix.application")}</p>
                  <div className="flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link to="/application">
                        <Icon name="tag" size={14} />
                        {t("homeroom.fix.applicationLink")}
                      </Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to="/conduct">
                        <Icon name="alert" size={14} />
                        {t("homeroom.fix.conductLink")}
                      </Link>
                    </Button>
                  </div>
                  <p className="text-ink-3">{t("homeroom.fix.conduct")}</p>
                </div>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>{t("homeroom.print.title")}</CardTitle>
                </CardHeader>
                <div className="flex flex-col gap-3 px-5 py-4 text-sm">
                  <div className="flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link to={sheets("class")}>
                        <Icon name="file" size={14} />
                        {t("homeroom.print.table")}
                      </Link>
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link to={sheets("ranking")}>
                        <Icon name="print" size={14} />
                        {t("homeroom.print.ranking")}
                      </Link>
                    </Button>
                  </div>
                  <p className="text-ink-3">{t("homeroom.print.help")}</p>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("homeroom.confirm.title")}
        confirmLabel={t("homeroom.confirm.action")}
        cancelLabel={t("common.cancel")}
        pending={ready.isPending}
        onConfirm={() =>
          ready.mutate({ ready: true, ...target }, { onSettled: () => setConfirm(false) })
        }
      >
        {t("homeroom.confirm.text", { term: termLabel })}
      </ConfirmDialog>
    </>
  );
}

function Readiness({
  data,
  titular,
  missing,
  pending,
  onDeclare,
  onWithdraw,
}: {
  data: HomeroomData;
  titular: boolean;
  missing: number;
  pending: boolean;
  onDeclare: () => void;
  onWithdraw: () => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const declare = (
    <Button onClick={onDeclare} disabled={!data.complete || pending}>
      <Icon name="check" size={16} />
      {t("homeroom.declare")}
    </Button>
  );
  if (data.ready_at) {
    return (
      <Banner
        tone="ok"
        action={
          titular && (
            <Button variant="outline" onClick={onWithdraw} disabled={pending}>
              {t("homeroom.ready.withdraw")}
            </Button>
          )
        }
      >
        <b>{t("homeroom.ready.title")}</b>{" "}
        {t("homeroom.ready.text", {
          date: formatDate(data.ready_at, i18n.language, school.timezone),
          time: formatTime(data.ready_at, i18n.language, school.timezone),
          name: data.ready_by,
        })}
      </Banner>
    );
  }
  // Cotitulaire (NB.7) : il complète les fiches, le titulaire seul déclare les bulletins prêts.
  if (!titular) {
    return (
      <Banner tone={data.complete ? "info" : "warn"} icon={data.complete ? undefined : "clock"}>
        <b>{t(data.complete ? "homeroom.toDeclare.title" : "homeroom.pending.title")}</b>{" "}
        {t("homeroom.coTitular", { count: missing })}
      </Banner>
    );
  }
  if (data.complete) {
    return (
      <Banner tone="info" action={declare}>
        <b>{t("homeroom.toDeclare.title")}</b> {t("homeroom.toDeclare.text")}
      </Banner>
    );
  }
  return (
    <Banner tone="warn" icon="clock" action={declare}>
      <b>{t("homeroom.pending.title")}</b> {t("homeroom.pending.text", { count: missing })}
    </Banner>
  );
}

function Figures({
  data,
  pct,
}: {
  data: HomeroomData;
  pct: (value: string | null | undefined) => string;
}) {
  const { t } = useTranslation();
  const validated = data.courses.filter((row) => row.course.status === "validated").length;
  const left = data.courses.length - validated;
  const stats = data.stats;
  const later = t("homeroom.stats.later");
  return (
    <div className="grid grid-cols-2 gap-4 min-[1100px]:grid-cols-4">
      <Kpi
        label={t("homeroom.stats.validated")}
        value={`${validated} / ${data.courses.length}`}
        sub={
          left
            ? t("homeroom.stats.validatedSub", { count: left })
            : t("homeroom.stats.validatedDone")
        }
        icon="check"
        chip={left ? "warn" : "ok"}
      />
      <Kpi
        label={t("homeroom.stats.students")}
        value={stats ? stats.students : "—"}
        sub={stats ? t("homeroom.stats.studentsSub", { count: stats.graded }) : later}
        icon="users"
      />
      <Kpi
        label={t("homeroom.stats.average")}
        value={pct(stats?.average)}
        sub={
          stats?.average != null
            ? t("homeroom.stats.averageSub", {
                highest: pct(stats.highest),
                lowest: pct(stats.lowest),
              })
            : later
        }
        icon="journal"
      />
      <Kpi
        label={t("homeroom.stats.atLeastHalf")}
        value={stats ? stats.at_least_half : "—"}
        sub={
          stats?.graded
            ? t("homeroom.stats.atLeastHalfSub", {
                percent: Math.round((stats.at_least_half * 100) / stats.graded),
              })
            : later
        }
        icon="sparkle"
        chip="ok"
      />
    </div>
  );
}

function Grade({ value }: { value: string }) {
  if (!value) return <span className="text-ink-3">—</span>;
  return <StatusPill tone={GOOD.has(value) ? "ok" : "warn"}>{value}</StatusPill>;
}
