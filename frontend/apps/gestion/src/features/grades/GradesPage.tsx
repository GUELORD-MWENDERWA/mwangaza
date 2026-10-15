// Saisie des notes (8.2.1, maquette `notes-saisie`) : la feuille d'un cours dans une période ou
// des examens — évaluations libres (nom, maximum) et notes des élèves — s'enregistre d'un seul
// envoi. Note de la période et pourcentage recalculés à chaque frappe (`sheet.ts`, même règle que
// le serveur). Droits `grades.enter` (ses cours, sa classe de titulaire) ou `grades.enter_any`
// (toutes les classes) ; en ligne (hors ligne : 8.2.3 ; date limite et validation : 8.2.2).
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
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type KeyboardEvent, useState } from "react";

import { uuidv7 } from "../../lib/ids";
import { keys } from "../../lib/queries";
import { termLabels, type TermShape } from "../../lib/terms";
import { LoadError } from "../status/StatusPages";
import { type Grading, type GradingCourse, type Sheet, useGrading, useSheet } from "./data";
import { parseTenths, percent, periodTenths, serverTenths, toScore } from "./sheet";

type Term = Grading["terms"][number];
type Choice = { classId: string; courseId: string; termId: string };
type Leaf = {
  id: string;
  kind: string;
  label: string;
  starts_on: string | null;
  ends_on: string | null;
};

/** Périodes et examens de l'année, dans l'ordre, avec leur nom affiché. */
function gradableTerms(terms: Term[], label: Map<TermShape, string>): Leaf[] {
  const leaves: Leaf[] = [];
  const visit = (node: Term | Term["children"][number]) => {
    if (node.kind === "period" || node.kind === "exam") {
      leaves.push({ ...node, label: label.get(node) ?? node.name });
    }
    for (const child of "children" in node ? node.children : []) visit(child);
  };
  terms.forEach(visit);
  return leaves;
}

/** Période du jour d'après ses dates ; à défaut, la première. */
function currentPeriod(leaves: Leaf[]): Leaf | undefined {
  const today = new Date().toISOString().slice(0, 10);
  const periods = leaves.filter((leaf) => leaf.kind === "period");
  return (
    periods.find(
      (leaf) => leaf.starts_on && leaf.ends_on && leaf.starts_on <= today && today <= leaf.ends_on,
    ) ?? periods[0]
  );
}

export function GradesPage() {
  const { t } = useTranslation();
  const grading = useGrading();
  const [choice, setChoice] = useState<Choice | null>(null);

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }
  const { classes, terms } = grading.data;
  const labels = termLabels(terms, t);
  const leaves = gradableTerms(terms, labels);
  if (!grading.data.academic_year || classes.length === 0 || leaves.length === 0) {
    return (
      <>
        <PageHeader title={t("grades.title")} />
        <Banner tone="info">
          {t(grading.data.academic_year ? "grades.noCourse" : "grades.noYear")}
        </Banner>
      </>
    );
  }
  const group = classes.find((item) => item.id === choice?.classId) ?? classes[0]!;
  const course = group.courses.find((item) => item.id === choice?.courseId) ?? group.courses[0]!;
  const usable = leaves.filter((leaf) => leaf.kind === "period" || course.has_exam);
  const term =
    usable.find((leaf) => leaf.id === choice?.termId) ?? currentPeriod(usable) ?? usable[0]!;
  return (
    <GradeSheet
      key={`${course.id}-${term.id}`}
      classes={classes}
      groupId={group.id}
      course={course}
      term={term}
      terms={usable}
      onChoose={setChoice}
    />
  );
}

type SheetProps = {
  classes: Grading["classes"];
  groupId: string;
  course: GradingCourse;
  term: Leaf;
  terms: Leaf[];
  onChoose: (choice: Choice) => void;
};

type EvaluationDraft = { id: string; name: string; max_score: number };
type Editing = { evaluation: EvaluationDraft | null };

const cellKey = (enrollment: string, evaluation: string) => `${enrollment}|${evaluation}`;

function GradeSheet({ classes, groupId, course, term, terms, onChoose }: SheetProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const sheet = useSheet(course.id, term.id);
  // Changements pas encore enregistrés : évaluations (`null` : celles du serveur), évaluations
  // retirées, cases tapées (texte, par élève et évaluation).
  const [evaluations, setEvaluations] = useState<EvaluationDraft[] | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [cells, setCells] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<Editing | null>(null);
  const [leaving, setLeaving] = useState<Choice | null>(null);
  const [notice, setNotice] = useState(false);
  const [invalid, setInvalid] = useState(false);

  const save = useMutation({
    mutationFn: (body: {
      evaluations: EvaluationDraft[];
      removed_evaluations: string[];
      grades: { enrollment_id: string; evaluation_id: string; score: string | null }[];
    }) =>
      call(
        api.PUT("/api/courses/{id}/terms/{term}/grades/", {
          params: { path: { id: course.id, term: term.id } },
          body,
        }),
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData([...keys.gradeSheet, course.id, term.id], saved);
      setEvaluations(null);
      setRemoved([]);
      setCells({});
      setNotice(true);
    },
  });

  if (sheet.isPending) return <Skeleton label={t("common.loading")} />;
  if (sheet.isError) return <LoadError error={sheet.error} onRetry={() => void sheet.refetch()} />;

  const data: Sheet = sheet.data;
  const columns = evaluations ?? data.evaluations;
  const dirty = evaluations !== null || removed.length > 0 || Object.keys(cells).length > 0;
  const decimal = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 });
  const show = (tenths: number) => decimal.format(tenths / 10);
  const original = new Map(
    data.students.flatMap((row) =>
      row.scores.map((cell) => [
        cellKey(row.enrollment_id, cell.evaluation_id),
        serverTenths(cell.score),
      ]),
    ),
  );
  const textOf = (key: string) => {
    if (key in cells) return cells[key]!;
    const tenths = original.get(key);
    return tenths === undefined ? "" : show(tenths);
  };
  const valueOf = (key: string, max: number) => parseTenths(textOf(key), max);

  const edit = (change: () => void) => {
    setNotice(false);
    setInvalid(false);
    change();
  };
  const choose = (next: Partial<Choice>) => {
    const target = { classId: groupId, courseId: course.id, termId: term.id, ...next };
    if (next.classId && next.classId !== groupId) target.courseId = "";
    if (dirty) setLeaving(target);
    else onChoose(target);
  };

  const submit = () => {
    const grades = [];
    for (const [key, text] of Object.entries(cells)) {
      const [enrollment, evaluation] = key.split("|") as [string, string];
      const column = columns.find((item) => item.id === evaluation);
      if (!column) continue;
      const tenths = parseTenths(text, column.max_score);
      if (tenths === undefined) return setInvalid(true);
      if (tenths === (original.get(key) ?? null)) continue;
      grades.push({
        enrollment_id: enrollment,
        evaluation_id: evaluation,
        score: tenths === null ? null : toScore(tenths),
      });
    }
    save.mutate({ evaluations: columns, removed_evaluations: removed, grades });
  };

  // Entrée : même évaluation, élève suivant ; après le dernier, évaluation suivante.
  const next = (row: number, column: number) => (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const target =
      document.querySelector<HTMLInputElement>(`[data-cell="${row + 1}:${column}"]`) ??
      document.querySelector<HTMLInputElement>(`[data-cell="0:${column + 1}"]`);
    target?.focus();
    target?.select();
  };

  const scoresIn = (evaluation: string) =>
    data.students.filter((row) => textOf(cellKey(row.enrollment_id, evaluation)) !== "").length;

  return (
    <>
      <PageHeader
        title={t("grades.title")}
        subtitle={t("grades.subtitle", {
          className: data.class_group,
          course: course.name,
          max: data.maximum,
          term: term.label,
        })}
        actions={
          <>
            <Select
              aria-label={t("grades.classChoice")}
              value={groupId}
              onChange={(event) => choose({ classId: event.target.value })}
              className="w-auto min-w-[180px]"
            >
              {classes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select
              aria-label={t("grades.courseChoice")}
              value={course.id}
              onChange={(event) => choose({ courseId: event.target.value })}
              className="w-auto min-w-[180px]"
            >
              {classes
                .find((item) => item.id === groupId)
                ?.courses.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
            </Select>
            <Select
              aria-label={t("grades.termChoice")}
              value={term.id}
              onChange={(event) => choose({ termId: event.target.value })}
              className="w-auto min-w-[150px]"
            >
              {terms.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </Select>
          </>
        }
      />
      {notice && (
        <div className="mb-4">
          <Banner tone="ok">{t("grades.saved")}</Banner>
        </div>
      )}
      {(invalid || save.isError) && (
        <div className="mb-4">
          <Banner tone="due">
            {invalid ? t("grades.invalidCells") : firstErrorMessage(save.error, t)}
          </Banner>
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle>{t("grades.students", { count: data.students.length })}</CardTitle>
          {dirty && <StatusPill tone="warn">{t("grades.unsaved")}</StatusPill>}
        </CardHeader>
        <div className="flex flex-wrap items-center gap-2 border-b border-line-soft px-5 py-3">
          <span className="text-sm text-ink-3">{t("grades.evaluations")}</span>
          {columns.map((column) => (
            <Button
              key={column.id}
              variant="outline"
              size="sm"
              onClick={() => setEditing({ evaluation: column })}
            >
              {t("grades.evaluationChip", { name: column.name, max: column.max_score })}
              <Icon name="edit" size={14} />
            </Button>
          ))}
          <Button variant="ghost" size="sm" onClick={() => setEditing({ evaluation: null })}>
            <Icon name="plus" size={14} />
            {t("grades.addEvaluation")}
          </Button>
        </div>
        {columns.length === 0 || data.students.length === 0 ? (
          <p className="px-5 py-6 text-sm text-ink-2">
            {t(columns.length === 0 ? "grades.noEvaluation" : "grades.noStudent")}
          </p>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("grades.columns.student")}</th>
                {columns.map((column) => (
                  <th key={column.id} className="text-right">
                    {t("grades.evaluationColumn", { name: column.name, max: column.max_score })}
                  </th>
                ))}
                <th className="text-right">{t("grades.columns.total", { max: data.maximum })}</th>
                <th className="text-right">{t("grades.columns.percent")}</th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((row, index) => {
                const values = columns.map((column) =>
                  valueOf(cellKey(row.enrollment_id, column.id), column.max_score),
                );
                const wrong = values.some((value) => value === undefined);
                const total = wrong
                  ? null
                  : periodTenths(
                      values as (number | null)[],
                      columns.map((column) => column.max_score),
                      data.maximum,
                    );
                const share = total === null ? null : percent(total, data.maximum);
                return (
                  <tr key={row.enrollment_id} data-tone={total === null ? "due" : undefined}>
                    <td>
                      <b>{row.full_name}</b>
                      {row.status !== "active" && (
                        <span className="ml-2 text-sm text-ink-3">{t("grades.left")}</span>
                      )}
                    </td>
                    {columns.map((column, place) => {
                      const key = cellKey(row.enrollment_id, column.id);
                      const value = values[place];
                      const label = t("grades.evaluationColumn", {
                        name: column.name,
                        max: column.max_score,
                      });
                      return (
                        <td key={column.id} data-label={label} className="text-right">
                          <Input
                            aria-label={t("grades.scoreLabel", {
                              evaluation: column.name,
                              student: row.full_name,
                            })}
                            data-cell={`${index}:${place}`}
                            inputMode="decimal"
                            value={textOf(key)}
                            aria-invalid={value === undefined || undefined}
                            onChange={(event) =>
                              edit(() =>
                                setCells((current) => ({ ...current, [key]: event.target.value })),
                              )
                            }
                            onKeyDown={next(index, place)}
                            className={cn(
                              "ml-auto w-[72px] text-right tabular-nums",
                              value === undefined && "border-due",
                            )}
                          />
                        </td>
                      );
                    })}
                    <td
                      data-label={t("grades.columns.total", { max: data.maximum })}
                      className="text-right whitespace-nowrap tabular-nums"
                    >
                      {total === null ? (
                        <span className="text-sm text-due">{t("grades.incomplete")}</span>
                      ) : (
                        <span>
                          <b>{show(total)}</b> / {data.maximum}
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
        {/* Collé en bas de l'écran : au téléphone, une carte par élève fait une longue page. */}
        <CardFooter className="sticky bottom-0 z-10">
          <span className="text-sm text-ink-2">{t("grades.hint")}</span>
          <Button disabled={!dirty || save.isPending} onClick={submit}>
            {t("grades.save")}
          </Button>
        </CardFooter>
      </Card>
      {editing && (
        <EvaluationDialog
          evaluation={editing.evaluation}
          maximum={data.maximum}
          scores={editing.evaluation ? scoresIn(editing.evaluation.id) : 0}
          highest={
            editing.evaluation
              ? Math.max(
                  0,
                  ...data.students.map(
                    (row) => valueOf(cellKey(row.enrollment_id, editing.evaluation!.id), 1000) ?? 0,
                  ),
                )
              : 0
          }
          onClose={() => setEditing(null)}
          onSave={(saved) =>
            edit(() => {
              setEvaluations(
                columns.some((column) => column.id === saved.id)
                  ? columns.map((column) => (column.id === saved.id ? saved : column))
                  : [...columns, saved],
              );
              setEditing(null);
            })
          }
          onRemove={(id) =>
            edit(() => {
              setEvaluations(columns.filter((column) => column.id !== id));
              if (data.evaluations.some((column) => column.id === id)) {
                setRemoved((current) => [...current, id]);
              }
              setEditing(null);
            })
          }
        />
      )}
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

type DialogProps = {
  evaluation: EvaluationDraft | null;
  maximum: number;
  /** Cases remplies dans cette évaluation, et la plus haute note (en dixièmes). */
  scores: number;
  highest: number;
  onClose: () => void;
  onSave: (evaluation: EvaluationDraft) => void;
  onRemove: (id: string) => void;
};

function EvaluationDialog({
  evaluation,
  maximum,
  scores,
  highest,
  onClose,
  onSave,
  onRemove,
}: DialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(evaluation?.name ?? "");
  const [max, setMax] = useState(evaluation ? String(evaluation.max_score) : "");
  const [checked, setChecked] = useState(false);
  const number = Number(max);
  const nameError = checked && !name.trim() ? t("grades.dialog.nameRequired") : undefined;
  const maxError = !checked
    ? undefined
    : !/^\d+$/.test(max) || number < 1 || number > 1000
      ? t("grades.dialog.maxInvalid")
      : highest > number * 10
        ? t("grades.dialog.belowAGrade")
        : undefined;
  const confirm = () => {
    setChecked(true);
    const valid = name.trim() && /^\d+$/.test(max) && number >= 1 && number <= 1000;
    if (!valid || highest > number * 10) return;
    onSave({ id: evaluation?.id ?? uuidv7(), name: name.trim().slice(0, 60), max_score: number });
  };
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("grades.dialog.title")}
        description={t("grades.dialog.help")}
        footer={
          <>
            {evaluation && (
              <Button
                variant="destructive-outline"
                className="mr-auto"
                onClick={() => onRemove(evaluation.id)}
              >
                {t("grades.dialog.remove")}
              </Button>
            )}
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button onClick={confirm}>{t("grades.dialog.confirm")}</Button>
          </>
        }
      >
        <Field id="evaluation-name" label={t("grades.dialog.name")} required error={nameError}>
          {(control) => (
            <Input
              {...control}
              value={name}
              maxLength={60}
              autoFocus
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        <Field
          id="evaluation-max"
          label={t("grades.dialog.max")}
          required
          help={t("grades.dialog.maxHelp", { max: maximum })}
          error={maxError}
        >
          {(control) => (
            <Input
              {...control}
              inputMode="numeric"
              value={max}
              className="w-[120px]"
              onChange={(event) => setMax(event.target.value.replace(/\D/g, ""))}
            />
          )}
        </Field>
        {evaluation && scores > 0 && (
          <Banner tone="warn">{t("grades.dialog.removeWarning", { count: scores })}</Banner>
        )}
      </DialogContent>
    </DialogRoot>
  );
}
