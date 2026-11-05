// Fiche de cotes commune (8.1.2a, maquette `notes-fiche-commune`) : l'enseignant d'un cours commun
// à plusieurs classes saisit sur une seule page ; chaque note va à l'élève et au cours de sa classe
// (`joint.ts`). « Enregistrer » envoie la feuille de chaque classe qui change (au serveur, ou sur
// l'appareil hors ligne, 8.2.3) ; « Envoyer et signer » envoie celle de chaque classe encore en
// brouillon. Une classe validée, ou fermée par la date limite, reste en lecture seule.
import { api, call } from "@mwangaza/api";
import { firstErrorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Icon,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { uuidv7 } from "../../lib/ids";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useSyncStatus } from "../../lib/sync/session";
import { termLabels } from "../../lib/terms";
import { LoadError } from "../status/StatusPages";
import { type Grading, type Sheet, sheetQuery, useGrading } from "./data";
import { currentPeriod, EvaluationDialog, gradableTerms, type Leaf } from "./GradesPage";
import {
  buildBodies,
  cellKey,
  type Column,
  columnMax,
  InvalidCell,
  mergeColumns,
  minter,
  original,
  type Part,
  scoreIndex,
  sharedMax,
  totalsColumn,
  withMax,
} from "./joint";
import { dismissRejected, remember, sendSave, sheetId, useSheetsQueue } from "./offline";
import { ControlBanner, isLocked, ReasonDialog, todayIn } from "./SheetControl";
import { parseTenths, percent, periodTenths, type SaveBody } from "./sheet";

type Entry = { course: Grading["classes"][number]["courses"][number]; className: string };
type Group = { id: string; label: string };

export function JointSheetPage() {
  const { t, i18n } = useTranslation();
  const grading = useGrading();
  const [params, setParams] = useSearchParams();
  const groupId = params.get("group") ?? "";

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }
  // Ses cours communs : ceux dont il tient le carnet (le groupe lui donne chaque cours).
  const mine = grading.data.classes.flatMap((group) =>
    group.courses
      .filter((course) => course.course_group && course.access === "notebook")
      .map((course) => ({ course, className: group.name })),
  );
  const list = new Intl.ListFormat(i18n.language, { type: "conjunction" });
  const groups: Group[] = [...new Set(mine.map((entry) => entry.course.course_group!))].map(
    (id) => {
      const members = mine.filter((entry) => entry.course.course_group === id);
      return {
        id,
        label: t("grades.joint.groupOption", {
          course: members[0]!.course.name,
          classes: list.format(members.map((entry) => entry.className)),
        }),
      };
    },
  );
  const group = groups.find((item) => item.id === groupId) ?? groups[0];
  const entries = mine.filter((entry) => entry.course.course_group === group?.id);
  const leaves = gradableTerms(grading.data.terms, termLabels(grading.data.terms, t)).filter(
    (leaf) => leaf.kind === "period" || entries.some((entry) => entry.course.has_exam),
  );
  if (!group || leaves.length === 0) {
    return (
      <>
        <PageHeader title={t("grades.joint.title")} />
        <Banner
          tone="info"
          action={
            <Button asChild variant="outline">
              <Link to="/grades">{t("grades.joint.back")}</Link>
            </Button>
          }
        >
          {t("grades.joint.none")}
        </Banner>
      </>
    );
  }
  const term =
    leaves.find((leaf) => leaf.id === params.get("term")) ?? currentPeriod(leaves) ?? leaves[0]!;
  return (
    <JointSheet
      key={`${group.id}-${term.id}`}
      groups={groups}
      group={group}
      entries={term.kind === "period" ? entries : entries.filter((entry) => entry.course.has_exam)}
      term={term}
      terms={leaves}
      onChoose={(next) => setParams({ group: group.id, term: term.id, ...next })}
    />
  );
}

type SheetProps = {
  groups: Group[];
  group: Group;
  entries: Entry[];
  term: Leaf;
  terms: Leaf[];
  onChoose: (next: { group?: string; term?: string }) => void;
};

function JointSheet({ groups, group, entries, term, terms, onChoose }: SheetProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const { db } = useSyncStatus();
  const sheets = useQueries({
    queries: entries.map((entry) => sheetQuery(db, entry.course.id, term.id)),
  });
  const courses = entries.map((entry) => entry.course.id);
  const queue = useSheetsQueue(db, courses, term.id);
  // Changements pas encore enregistrés : colonnes (`null` : celles des feuilles), colonnes
  // retirées, cases tapées (par classe, élève et colonne).
  const [draft, setDraft] = useState<Column[] | null>(null);
  const [removed, setRemoved] = useState<Column[]>([]);
  const [cells, setCells] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState<{ column: Column | null } | null>(null);
  const [asking, setAsking] = useState<Map<string, SaveBody> | null>(null);
  const [signing, setSigning] = useState(false);
  const [leaving, setLeaving] = useState<{ group?: string; term?: string } | null>(null);
  const [notice, setNotice] = useState<"saved" | "submit" | null>(null);
  const [failures, setFailures] = useState<string[]>([]);
  const [invalid, setInvalid] = useState(false);
  // Saisie « total » : identifiant de l'unique évaluation tant qu'aucune classe n'en a.
  const [totalId] = useState(uuidv7);
  const [mint] = useState(() => minter(uuidv7));

  const sheetKey = (course: string) => [...keys.gradeSheet, course, term.id];
  const keep = (course: string, saved: Sheet) => {
    queryClient.setQueryData(sheetKey(course), saved);
    if (db) void remember(db, sheetId(course, term.id), saved).catch(() => undefined);
  };
  const waiting = queue?.waiting.length ?? 0;
  // Notes de l'appareil parties et reprises par le serveur : les feuilles du serveur reviennent.
  const hadWaiting = useRef(false);
  useEffect(() => {
    if (hadWaiting.current && waiting === 0) {
      for (const course of courses) {
        void queryClient.invalidateQueries({ queryKey: sheetKey(course) });
      }
    }
    hadWaiting.current = waiting > 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting]);

  const nameOf = (course: string) =>
    entries.find((entry) => entry.course.id === course)?.className ?? "";
  // Une classe refusée n'empêche pas les autres : son message, précédé de son nom.
  const refusals = (sent: string[], results: PromiseSettledResult<Sheet>[]) =>
    results.flatMap((result, index) =>
      result.status === "rejected"
        ? [
            t("grades.joint.classState", {
              className: nameOf(sent[index]!),
              text: firstErrorMessage(result.reason, t),
            }),
          ]
        : [],
    );
  const save = useMutation({
    mutationFn: async (bodies: Map<string, SaveBody>) => {
      const sent = [...bodies.keys()];
      const results = await Promise.allSettled(
        sent.map((course) =>
          sendSave(db, {
            course,
            term: term.id,
            current: queryClient.getQueryData<Sheet>(sheetKey(course)),
            body: bodies.get(course)!,
          }),
        ),
      );
      return { sent, results };
    },
    onSuccess: ({ sent, results }) => {
      const done = new Set<string>();
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          keep(sent[index]!, result.value);
          done.add(sent[index]!);
        }
      });
      const errors = refusals(sent, results);
      setFailures(errors);
      setAsking(null);
      if (done.size === 0) return;
      // Colonnes relues des feuilles ; les cases des classes refusées restent tapées.
      setDraft(null);
      setRemoved([]);
      setCells((current) =>
        errors.length === 0
          ? {}
          : Object.fromEntries(
              Object.entries(current).filter(([key]) => !done.has(key.split("|")[0]!)),
            ),
      );
      if (errors.length === 0) setNotice("saved");
    },
  });
  const sign = useMutation({
    mutationFn: async (sent: string[]) => {
      const results = await Promise.allSettled(
        sent.map((course) =>
          call(
            api.POST("/api/courses/{id}/terms/{term}/grades/submit/", {
              params: { path: { id: course, term: term.id } },
            }),
          ),
        ),
      );
      return { sent, results };
    },
    onSuccess: ({ sent, results }) => {
      results.forEach((result, index) => {
        if (result.status === "fulfilled") keep(sent[index]!, result.value);
      });
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
      const errors = refusals(sent, results);
      setFailures(errors);
      setSigning(false);
      if (errors.length === 0) setNotice("submit");
    },
  });

  const dirty = draft !== null || removed.length > 0 || Object.keys(cells).length > 0;
  const choose = (next: { group?: string; term?: string }) =>
    dirty ? setLeaving(next) : onChoose(next);
  const pickers = (
    <>
      {groups.length > 1 && (
        <Select
          aria-label={t("grades.joint.groupChoice")}
          value={group.id}
          onChange={(event) => choose({ group: event.target.value })}
          className="w-auto min-w-[200px]"
        >
          {groups.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </Select>
      )}
      <Select
        aria-label={t("grades.termChoice")}
        value={term.id}
        onChange={(event) => choose({ term: event.target.value })}
        className="w-auto min-w-[150px]"
      >
        {terms.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </Select>
    </>
  );

  if (sheets.some((query) => query.isPending)) return <Skeleton label={t("common.loading")} />;
  const broken = sheets.find((query) => query.isError);
  if (broken) return <LoadError error={broken.error} onRetry={() => void broken.refetch()} />;

  const canValidate = can(me, ["grades.validate"]);
  const today = todayIn(school.timezone);
  const parts: Part[] = entries.map((entry, index) => {
    const sheet = sheets[index]!.data!;
    return {
      course: entry.course.id,
      className: entry.className,
      sheet,
      locked: isLocked(sheet, canValidate, today),
    };
  });
  const editable = parts.filter((part) => !part.locked);
  const drafts = editable.filter((part) => part.sheet.status === "draft");
  const totalsOnly = parts.every((part) => part.sheet.entry === "totals");
  const columns = totalsOnly
    ? [totalsColumn(parts, t("grades.totalName"), totalId)]
    : (draft ?? mergeColumns(parts));
  const index = scoreIndex(parts);
  const decimal = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 });
  const show = (tenths: number) => decimal.format(tenths / 10);
  const rows = parts
    .flatMap((part) => part.sheet.students.map((row) => ({ part, row })))
    .sort((a, b) => a.row.full_name.localeCompare(b.row.full_name, i18n.language));
  const visible = filter === "all" ? rows : rows.filter((item) => item.part.course === filter);
  const textOf = (part: Part, enrollment: string, column: Column) => {
    const key = cellKey(part.course, enrollment, column.key);
    if (key in cells) return cells[key]!;
    const tenths = original(index, part, enrollment, column);
    return tenths === undefined ? "" : show(tenths);
  };
  const header = (column: Column) => {
    const max = sharedMax(column);
    return max === null || totalsOnly
      ? column.name
      : t("grades.evaluationColumn", { name: column.name, max });
  };
  const edit = (change: () => void) => {
    setNotice(null);
    setInvalid(false);
    setFailures([]);
    change();
  };
  const submit = () => {
    let bodies: Map<string, SaveBody>;
    try {
      bodies = buildBodies({ parts, columns, removed, cells, reason: "", mint });
    } catch (error) {
      if (error instanceof InvalidCell) return setInvalid(true);
      throw error;
    }
    if (bodies.size === 0) {
      setDraft(null);
      setRemoved([]);
      setCells({});
      return setNotice("saved");
    }
    // Une classe déjà envoyée : le motif d'abord (il vaut pour toutes).
    const sent = parts.some((part) => bodies.has(part.course) && part.sheet.status === "submitted");
    if (sent) setAsking(bodies);
    else save.mutate(bodies);
  };
  // Entrée : même colonne, élève suivant ; après le dernier, colonne suivante.
  const next = (row: number, column: number) => (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const target =
      document.querySelector<HTMLInputElement>(`[data-cell="${row + 1}:${column}"]`) ??
      document.querySelector<HTMLInputElement>(`[data-cell="0:${column + 1}"]`);
    target?.focus();
    target?.select();
  };
  const filled = (column: Column) =>
    rows.filter(({ part, row }) => !part.locked && textOf(part, row.enrollment_id, column) !== "")
      .length;
  const highest = (column: Column) =>
    Math.max(
      0,
      ...rows.map(({ part, row }) =>
        part.locked ? 0 : (parseTenths(textOf(part, row.enrollment_id, column), 1000) ?? 0),
      ),
    );
  // Bandeaux d'état : la date limite une fois, puis chaque classe envoyée, validée, renvoyée ou
  // fermée, précédée de son nom.
  const notable = parts.filter(
    (part) => part.sheet.status !== "draft" || part.sheet.reopened || part.locked,
  );
  const plain = parts.find((part) => !notable.includes(part));
  const banner = {
    language: i18n.language,
    timeZone: school.timezone,
  };
  const students = rows.length;
  const filterLabel = t("grades.joint.classFilter");
  const filterOptions = [
    { value: "all", label: t("grades.joint.all") },
    ...parts.map((part) => ({ value: part.course, label: part.className })),
  ];

  return (
    <>
      <PageHeader
        title={t("grades.joint.title")}
        subtitle={t("grades.joint.subtitle", { group: group.label, term: term.label })}
        actions={pickers}
      />
      <div className="mb-4 space-y-3">
        <Banner tone="info">{t("grades.joint.banner", { count: parts.length, students })}</Banner>
        {plain && <ControlBanner sheet={plain.sheet} locked={false} {...banner} />}
        {notable.map((part) => (
          <ControlBanner
            key={part.course}
            sheet={part.sheet}
            locked={part.locked}
            className={part.className}
            {...banner}
          />
        ))}
        {waiting > 0 && (
          <Banner tone="warn">{t("grades.offline.waiting", { count: waiting })}</Banner>
        )}
        {queue && queue.rejected.length > 0 && db && (
          <Banner
            tone="due"
            action={
              <Button variant="outline" onClick={() => void dismissRejected(db, queue.rejected)}>
                {t("grades.offline.dismiss")}
              </Button>
            }
          >
            {t("grades.offline.rejected", {
              reason: queue.rejected.at(-1)?.error?.detail ?? "",
            })}
          </Banner>
        )}
        {notice && waiting === 0 && (
          <Banner tone="ok">
            {notice === "saved" ? t("grades.saved") : t("grades.joint.submitted")}
          </Banner>
        )}
        {(invalid || failures.length > 0 || save.isError || sign.isError) && (
          <Banner tone="due">
            {invalid
              ? t("grades.invalidCells")
              : failures.length > 0
                ? failures.join(" ")
                : firstErrorMessage(save.error ?? sign.error, t)}
          </Banner>
        )}
      </div>
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <CardTitle>{t("grades.students", { count: students })}</CardTitle>
          {dirty && <StatusPill tone="warn">{t("grades.unsaved")}</StatusPill>}
          {parts.length <= 3 ? (
            <Segmented
              label={filterLabel}
              value={filter}
              onValueChange={setFilter}
              options={filterOptions}
              className="sm:ml-auto sm:w-auto"
            />
          ) : (
            <Select
              aria-label={filterLabel}
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              className="w-auto min-w-[180px] sm:ml-auto"
            >
              {filterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          )}
        </CardHeader>
        {!totalsOnly && (
          <div className="flex flex-wrap items-center gap-2 border-b border-line-soft px-5 py-3">
            <span className="text-sm text-ink-3">{t("grades.evaluations")}</span>
            {columns.map((column) => (
              <Button
                key={column.key}
                variant="outline"
                size="sm"
                disabled={editable.length === 0}
                onClick={() => setEditing({ column })}
              >
                {header(column)}
                <Icon name="edit" size={14} />
              </Button>
            ))}
            <Button
              variant="ghost"
              size="sm"
              disabled={editable.length === 0}
              onClick={() => setEditing({ column: null })}
            >
              <Icon name="plus" size={14} />
              {t("grades.addEvaluation")}
            </Button>
          </div>
        )}
        {columns.length === 0 || rows.length === 0 ? (
          <p className="px-5 py-6 text-sm text-ink-2">
            {t(columns.length === 0 ? "grades.noEvaluation" : "grades.noStudent")}
          </p>
        ) : (
          <Table stacked freeze>
            <thead>
              <tr>
                <th>{t("grades.columns.student")}</th>
                <th>{t("grades.joint.class")}</th>
                {columns.map((column) => (
                  <th key={column.key} className="text-right">
                    {header(column)}
                  </th>
                ))}
                <th className="text-right">{t("grades.joint.total")}</th>
                <th className="text-right">{t("grades.columns.percent")}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map(({ part, row }, place) => {
                const maxima = columns.map((column) => columnMax(column, part.course));
                const values = columns.map((column, at) =>
                  parseTenths(textOf(part, row.enrollment_id, column), maxima[at]!),
                );
                const wrong = values.some((value) => value === undefined);
                const maximum = part.sheet.maximum;
                const total = wrong
                  ? null
                  : periodTenths(values as (number | null)[], maxima, maximum);
                const share = total === null ? null : percent(total, maximum);
                return (
                  <tr key={row.enrollment_id} data-tone={total === null ? "due" : undefined}>
                    <td>
                      <b>{row.full_name}</b>
                      {row.status !== "active" && (
                        <span className="ml-2 text-sm text-ink-3">{t("grades.left")}</span>
                      )}
                    </td>
                    <td data-label={t("grades.joint.class")} className="whitespace-nowrap">
                      {part.className}
                      {part.locked && (
                        <StatusPill tone="gray" className="ml-2">
                          {t(
                            part.sheet.status === "validated"
                              ? "grades.joint.validated"
                              : "grades.joint.closed",
                          )}
                        </StatusPill>
                      )}
                    </td>
                    {columns.map((column, at) => {
                      const value = values[at];
                      const label = t("grades.evaluationColumn", {
                        name: column.name,
                        max: maxima[at]!,
                      });
                      const key = cellKey(part.course, row.enrollment_id, column.key);
                      return (
                        <td key={column.key} data-label={label} className="text-right">
                          <Input
                            aria-label={t("grades.scoreLabel", {
                              evaluation: column.name,
                              student: row.full_name,
                            })}
                            data-cell={`${place}:${at}`}
                            inputMode="decimal"
                            value={textOf(part, row.enrollment_id, column)}
                            disabled={part.locked}
                            aria-invalid={value === undefined || undefined}
                            onChange={(event) =>
                              edit(() =>
                                setCells((current) => ({ ...current, [key]: event.target.value })),
                              )
                            }
                            onKeyDown={next(place, at)}
                            className={cn(
                              "ml-auto w-[72px] text-right tabular-nums",
                              value === undefined && "border-due",
                            )}
                          />
                        </td>
                      );
                    })}
                    <td
                      data-label={t("grades.joint.total")}
                      className="text-right whitespace-nowrap tabular-nums"
                    >
                      {total === null ? (
                        <span className="text-sm text-due">{t("grades.incomplete")}</span>
                      ) : (
                        <span>
                          <b>{show(total)}</b> / {maximum}
                        </span>
                      )}
                    </td>
                    <td
                      data-label={t("grades.columns.percent")}
                      className={cn(
                        "text-right tabular-nums",
                        share !== null && share < 50 && "text-due",
                      )}
                    >
                      {share === null ? "—" : t("grades.percentValue", { value: share })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
        <CardFooter className="sticky bottom-0 z-10">
          <span className="text-sm text-ink-2">{t("grades.joint.footer")}</span>
          <div className="flex flex-wrap justify-end gap-2">
            {editable.length > 0 && (
              <Button
                variant={drafts.length > 0 ? "outline" : "default"}
                disabled={!dirty || save.isPending}
                onClick={submit}
              >
                {t("grades.save")}
              </Button>
            )}
            {drafts.length > 0 && (
              <Button
                disabled={dirty || sign.isPending || columns.length === 0}
                onClick={() => setSigning(true)}
              >
                {t("grades.submit")}
              </Button>
            )}
          </div>
        </CardFooter>
      </Card>
      {asking && (
        <ReasonDialog
          kind="edit"
          pending={save.isPending}
          onClose={() => setAsking(null)}
          onConfirm={(reason) =>
            save.mutate(new Map([...asking].map(([course, body]) => [course, { ...body, reason }])))
          }
        />
      )}
      {editing && (
        <EvaluationDialog
          evaluation={
            editing.column
              ? {
                  id: editing.column.key,
                  name: editing.column.name,
                  max_score: sharedMax(editing.column) ?? columnMax(editing.column, ""),
                }
              : null
          }
          maximum={parts[0]!.sheet.maximum}
          maxHelp={t("grades.joint.maxHelp")}
          scores={editing.column ? filled(editing.column) : 0}
          highest={editing.column ? highest(editing.column) : 0}
          onClose={() => setEditing(null)}
          onSave={(saved) =>
            edit(() => {
              const open = editable.map((part) => part.course);
              const found = columns.find((column) => column.key === saved.id);
              const base = found ?? { key: saved.id, name: saved.name, ids: {}, maxima: {} };
              const column = withMax(base, open, saved.max_score, saved.name);
              setDraft(
                found
                  ? columns.map((item) => (item.key === saved.id ? column : item))
                  : [...columns, column],
              );
              setEditing(null);
            })
          }
          onRemove={(key) =>
            edit(() => {
              const column = columns.find((item) => item.key === key);
              setDraft(columns.filter((item) => item.key !== key));
              if (column && Object.keys(column.ids).length > 0) {
                setRemoved((current) => [...current, column]);
              }
              setEditing(null);
            })
          }
        />
      )}
      <ConfirmDialog
        open={signing}
        onOpenChange={(open) => !open && setSigning(false)}
        title={t("grades.sign.title")}
        confirmLabel={t("grades.sign.confirm")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => sign.mutate(drafts.map((part) => part.course))}
      >
        {t("grades.joint.signBody", { count: drafts.length })}
      </ConfirmDialog>
      <ConfirmDialog
        open={leaving !== null}
        onOpenChange={(open) => !open && setLeaving(null)}
        title={t("grades.leave.title")}
        confirmLabel={t("grades.leave.confirm")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (leaving) onChoose(leaving);
          setLeaving(null);
        }}
      >
        {t("grades.leave.body")}
      </ConfirmDialog>
    </>
  );
}
