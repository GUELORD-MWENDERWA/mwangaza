// Application (8.5.1c, maquette `application`) : cote d'application de chaque élève d'une classe,
// par période. Proposée d'après le pourcentage de la période ; le titulaire de la classe (ou qui
// entre les notes de toutes les classes) la corrige avec un motif, inscrit au journal.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  Field,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useGrading } from "../grades/data";
import { LoadError } from "../status/StatusPages";
import { useClassApplication, type StudentApplication, type TermApplication } from "./data";

const GRADES = ["TB", "B", "AB", "ME", "MA"] as const;
type Grade = (typeof GRADES)[number];

const TONES: Record<string, "ok" | "warn" | "due"> = {
  TB: "ok",
  B: "ok",
  AB: "warn",
  ME: "warn",
  MA: "due",
};

type Target = { student: StudentApplication; term: TermApplication; number: number };

export function ApplicationPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const queryClient = useQueryClient();
  const grading = useGrading();
  const [classId, setClassId] = useState("");
  const [target, setTarget] = useState<Target | null>(null);
  const [newGrade, setNewGrade] = useState<Grade>("TB");
  const [reason, setReason] = useState("");

  const everyClass = can(me, ["grades.enter_any", "grades.validate"]);
  const classes = (grading.data?.classes ?? []).filter((item) => item.is_homeroom || everyClass);
  const groupId = classId || classes[0]?.id || "";
  const table = useClassApplication(groupId);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.application });
  const close = () => {
    setTarget(null);
    setReason("");
  };

  const correct = useMutation({
    mutationFn: ({ student, term }: Target) =>
      call(
        api.PUT("/api/application/enrollments/{id}/", {
          params: { path: { id: student.enrollment } },
          body: { term: term.term, grade: newGrade, reason },
        }),
      ),
    onSuccess: () => {
      close();
      refresh();
    },
  });
  const restore = useMutation({
    mutationFn: ({ student, term }: Target) =>
      call(
        api.DELETE("/api/application/enrollments/{id}/", {
          params: { path: { id: student.enrollment }, query: { term: term.term } },
        }),
      ),
    onSuccess: () => {
      close();
      refresh();
    },
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const mayCorrect = table.data?.may_correct ?? false;
  const periodLabel = (term: TermApplication, number: number) =>
    term.term_name || t("application.term", { n: number });

  return (
    <>
      <PageHeader title={t("application.title")} subtitle={t("application.subtitle")} />
      {classes.length === 0 ? (
        <Banner tone="info">{t("application.noClass")}</Banner>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="max-w-xs">
              <Field id="application-class" label={t("application.class")}>
                {(control) => (
                  <Select
                    {...control}
                    value={groupId}
                    onChange={(event) => setClassId(event.target.value)}
                  >
                    {classes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            {table.isPending ? (
              <Skeleton label={t("common.loading")} />
            ) : table.isError ? (
              <LoadError error={table.error} onRetry={() => void table.refetch()} />
            ) : (
              <>
                <Table stacked>
                  <thead>
                    <tr>
                      <th>{t("application.student")}</th>
                      {table.data.students[0]?.terms.map((term, index) => (
                        <th key={term.term}>{periodLabel(term, index + 1)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {table.data.students.map((student) => (
                      <tr key={student.enrollment}>
                        <td data-label={t("application.student")} data-wrap>
                          {student.full_name}
                        </td>
                        {student.terms.map((term, index) => (
                          <td key={term.term} data-label={periodLabel(term, index + 1)}>
                            {term.percent === null ? (
                              <span className="text-ink-3">{t("application.noGrade")}</span>
                            ) : (
                              <span className="flex flex-wrap items-center gap-2">
                                <StatusPill tone={TONES[term.grade] ?? "warn"}>
                                  {term.grade}
                                </StatusPill>
                                <span className="text-xs text-ink-3">
                                  {t("application.percent", { value: term.percent })}
                                  {term.override_reason && ` · ${t("application.corrected")}`}
                                </span>
                                {mayCorrect && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setNewGrade(term.grade as Grade);
                                      setReason(term.override_reason);
                                      setTarget({ student, term, number: index + 1 });
                                    }}
                                  >
                                    {t("application.correct")}
                                  </Button>
                                )}
                              </span>
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <p className="text-xs text-ink-3">
                  {mayCorrect ? t("application.help") : t("application.readOnly")}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}
      <ConfirmDialog
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) close();
        }}
        title={t("application.correctTitle")}
        confirmLabel={t("application.confirmCorrect")}
        cancelLabel={t("application.keep")}
        pending={correct.isPending || reason.trim() === ""}
        onConfirm={() => target && correct.mutate(target)}
      >
        <div className="flex flex-col gap-3">
          {target && (
            <p className="font-semibold">
              {t("application.forStudent", {
                name: target.student.full_name,
                term: periodLabel(target.term, target.number),
              })}
            </p>
          )}
          <p className="text-ink-3">{t("application.correctHelp")}</p>
          <Field id="application-new-grade" label={t("application.newGrade")}>
            {(control) => (
              <Select
                {...control}
                value={newGrade}
                onChange={(event) => setNewGrade(event.target.value as Grade)}
              >
                {GRADES.map((grade) => (
                  <option key={grade} value={grade}>
                    {t(`application.grade${grade}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="application-reason" label={t("application.reason")} required>
            {(control) => (
              <Textarea
                {...control}
                maxLength={300}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
          {target?.term.override_reason && (
            <Button
              variant="outline"
              disabled={restore.isPending}
              onClick={() => restore.mutate(target)}
            >
              {t("application.restore")}
            </Button>
          )}
          {(correct.isError || restore.isError) && (
            <Banner tone="due">{firstErrorMessage(correct.error ?? restore.error, t)}</Banner>
          )}
        </div>
      </ConfirmDialog>
    </>
  );
}
