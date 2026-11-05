// Import des points d'une feuille depuis Excel (8.2.4, maquette `notes-import-excel`) : modèle de
// la feuille, contrôle ligne par ligne par le serveur (rien n'est écrit), puis enregistrement par
// la saisie de la feuille (mêmes droits, motif, journal, notification). Une ligne fausse bloque
// tout : on corrige le classeur et on le renvoie. Le contrôle demande le réseau.
import { api, ApiError, call, type Schemas } from "@mwangaza/api";
import { firstErrorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { keys } from "../../lib/queries";
import { useSyncStatus } from "../../lib/sync/session";
import { termLabels } from "../../lib/terms";
import { LoadError } from "../status/StatusPages";
import { useGrading, useSheet } from "./data";
import { gradableTerms } from "./GradesPage";
import { remember, sendSave, sheetId } from "./offline";
import { ReasonDialog } from "./SheetControl";

type Result = Schemas["GradeImport"];
type Line = Result["lines"][number];

// Les lignes fausses d'abord, puis celles qui seront importées, puis les élèves sans note.
const ORDER: Record<Line["status"], number> = { error: 0, ready: 1, skipped: 2 };

export function GradeImportPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const courseId = params.get("course") ?? "";
  const termId = params.get("term") ?? "";
  const grading = useGrading();
  const sheet = useSheet(courseId, termId);

  if (grading.isPending || sheet.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }
  if (sheet.isError) return <LoadError error={sheet.error} onRetry={() => void sheet.refetch()} />;
  const course = grading.data.classes.flatMap((g) => g.courses).find((c) => c.id === courseId);
  const terms = grading.data.terms;
  const term = gradableTerms(terms, termLabels(terms, t)).find((leaf) => leaf.id === termId);
  return (
    <ImportSheet
      courseId={courseId}
      termId={termId}
      title={t("grades.import.subtitle", {
        className: sheet.data.class_group,
        course: course?.name ?? "",
        term: term?.label ?? "",
      })}
      sheet={sheet.data}
    />
  );
}

type Props = {
  courseId: string;
  termId: string;
  title: string;
  sheet: Schemas["Sheet"];
};

function ImportSheet({ courseId, termId, title, sheet }: Props) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { db } = useSyncStatus();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [reasonFor, setReasonFor] = useState<"edit" | "correct" | null>(null);
  const path = { params: { path: { id: courseId, term: termId } } };
  const base = `/api/courses/${courseId}/terms/${termId}/grades/`;
  const sheetUrl = `/grades?course=${courseId}&term=${termId}`;
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);

  const check = useMutation({
    mutationFn: () => {
      const body = new FormData();
      body.append("file", file!);
      return call(
        api.POST("/api/courses/{id}/terms/{term}/grades/import/", {
          ...path,
          body: body as unknown as { file: string },
        }),
      );
    },
    onSuccess: setResult,
  });
  const save = useMutation({
    mutationFn: (reason: string) =>
      sendSave(db, {
        course: courseId,
        term: termId,
        current: sheet,
        body: {
          // Le serveur donne toujours l'identifiant de la colonne « total » à créer.
          evaluations: result!.evaluations.flatMap((e) => (e.id ? [{ ...e, id: e.id }] : [])),
          removed_evaluations: [],
          grades: result!.grades,
          reason,
        },
      }),
    onSuccess: (saved) => {
      setReasonFor(null);
      queryClient.setQueryData([...keys.gradeSheet, courseId, termId], saved);
      if (db) void remember(db, sheetId(courseId, termId), saved).catch(() => undefined);
    },
    onError: (error, reason) => {
      if (error instanceof ApiError && error.code === "reason_required" && !reason) {
        setReasonFor("correct");
      }
    },
  });
  const restart = () => {
    setFile(null);
    setResult(null);
    check.reset();
    save.reset();
  };
  const confirm = () => (sheet.status === "submitted" ? setReasonFor("edit") : save.mutate(""));
  const asking = save.error instanceof ApiError && save.error.code === "reason_required";
  const error = check.error ?? (asking ? null : save.error);
  const lines = [...(result?.lines ?? [])].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  const changes = result?.grades.length ?? 0;
  const columnTitle = (column: Result["columns"][number]) =>
    t("grades.evaluationColumn", { name: column.name, max: column.max_score });

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to={sheetUrl} className="text-lake underline">
              {t("grades.title")}
            </Link>{" "}
            / {t("grades.import.title")}
          </>
        }
        title={t("grades.import.title")}
        subtitle={title}
        actions={
          <Button asChild variant="outline">
            <a href={`${base}import/`} download>
              <Icon name="download" size={16} />
              {t("grades.import.template")}
            </a>
          </Button>
        }
      />
      {error && <Banner tone="due">{firstErrorMessage(error, t)}</Banner>}
      {save.isSuccess ? (
        <Banner
          tone="ok"
          action={
            <Button asChild variant="outline">
              <Link to={sheetUrl}>{t("grades.import.openSheet")}</Link>
            </Button>
          }
        >
          {t("grades.import.done", { count: changes, number: number(changes) })}
        </Banner>
      ) : (
        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("grades.import.file.title")}</CardTitle>
              <span className="text-sm text-ink-3">{t("grades.import.file.help")}</span>
            </CardHeader>
            <CardContent className="grid gap-4">
              {result ? (
                <p className="text-sm">
                  {t("grades.import.file.read", {
                    file: file?.name ?? "",
                    count: result.lines.length,
                    number: number(result.lines.length),
                  })}
                </p>
              ) : (
                <Field id="grade-import-file" label={t("grades.import.file.file")}>
                  {(control) => (
                    <Input
                      {...control}
                      type="file"
                      accept=".xlsx,.csv"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    />
                  )}
                </Field>
              )}
            </CardContent>
            {!result && (
              <CardFooter className="justify-end">
                <Button disabled={!file || check.isPending} onClick={() => check.mutate()}>
                  {check.isPending
                    ? t("grades.import.file.reading")
                    : t("grades.import.file.check")}
                </Button>
              </CardFooter>
            )}
          </Card>
          {result && (
            <Card>
              <CardHeader>
                <CardTitle>{t("grades.import.check.title")}</CardTitle>
                {result.error_count > 0 ? (
                  <StatusPill tone="due">
                    {t("grades.import.check.errors", {
                      count: result.error_count,
                      number: number(result.error_count),
                    })}
                  </StatusPill>
                ) : (
                  <StatusPill tone="ok">{t("grades.import.check.ready")}</StatusPill>
                )}
              </CardHeader>
              <Table stacked>
                <thead>
                  <tr>
                    <th className="text-right">{t("grades.import.check.line")}</th>
                    <th>{t("grades.columns.student")}</th>
                    {result.columns.map((column) => (
                      <th key={column.evaluation_id} className="text-right">
                        {columnTitle(column)}
                      </th>
                    ))}
                    <th>{t("grades.import.check.result")}</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr key={line.number}>
                      <td
                        data-label={t("grades.import.check.line")}
                        className="text-right tabular-nums"
                      >
                        {line.number}
                      </td>
                      <td>
                        <b>{line.name || "—"}</b>
                        {line.matricule && (
                          <span className="block text-sm text-ink-3">{line.matricule}</span>
                        )}
                      </td>
                      {result.columns.map((column, index) => (
                        <td
                          key={column.evaluation_id}
                          data-label={columnTitle(column)}
                          className="text-right tabular-nums"
                        >
                          {line.values[index] || "—"}
                        </td>
                      ))}
                      <td data-label={t("grades.import.check.result")}>
                        {line.status === "error" ? (
                          <div className="flex flex-wrap gap-1">
                            {line.issues.map((issue, index) => (
                              <StatusPill key={index} tone="due">
                                {t(`grades.import.issues.${issue.code}`, {
                                  column: issue.column ?? "",
                                  value: issue.value ?? "",
                                  max: issue.max ?? "",
                                  line: issue.line ?? "",
                                })}
                              </StatusPill>
                            ))}
                          </div>
                        ) : (
                          <StatusPill tone={line.status === "ready" ? "ok" : undefined}>
                            {t(`grades.import.status.${line.status}`)}
                          </StatusPill>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <CardFooter>
                <span className="text-sm text-ink-2">
                  {result.error_count > 0
                    ? t("grades.import.check.blocked")
                    : t("grades.import.check.summary", {
                        count: changes,
                        number: number(changes),
                        unchanged: number(result.unchanged_count),
                      })}
                </span>
                <div className="flex flex-wrap justify-end gap-2">
                  <Button variant="outline" onClick={restart}>
                    {t("grades.import.again")}
                  </Button>
                  <Button
                    disabled={result.error_count > 0 || changes === 0 || save.isPending}
                    onClick={confirm}
                  >
                    {t("grades.import.confirm", { count: changes, number: number(changes) })}
                  </Button>
                </div>
              </CardFooter>
            </Card>
          )}
        </div>
      )}
      {reasonFor && (
        <ReasonDialog
          kind={reasonFor}
          pending={save.isPending}
          onClose={() => setReasonFor(null)}
          onConfirm={(reason) => save.mutate(reason)}
        />
      )}
    </>
  );
}
