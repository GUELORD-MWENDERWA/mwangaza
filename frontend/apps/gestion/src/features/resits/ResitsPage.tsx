// Examens de repêchage (8.4.1, maquette `repechage`) : pour chaque élève de la classe, les cours
// échoués d'après les règles de l'école, la note de repêchage (saisie et signée par l'enseignant
// du cours) et l'issue proposée. La décision prise est celle de la délibération (8.4.2).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useGrading } from "../grades/data";
import { LoadError } from "../status/StatusPages";
import { useClassResits, type ResitCourse, type StudentResits } from "./data";

const TONES: Record<string, "ok" | "warn" | "due" | "gray"> = {
  passed: "ok",
  resit: "warn",
  failed: "due",
  incomplete: "gray",
};

type Target = { enrollment: string; course: string };

export function ResitsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const grading = useGrading();
  const [classId, setClassId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const classes = grading.data?.classes ?? [];
  const groupId = classId || classes[0]?.id || "";
  const table = useClassResits(groupId);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.resits });
  const draftKey = ({ enrollment, course }: Target) => `${enrollment}:${course}`;

  const save = useMutation({
    mutationFn: (target: Target) =>
      call(
        api.PUT("/api/resits/enrollments/{id}/courses/{course_pk}/", {
          params: { path: { id: target.enrollment, course_pk: target.course } },
          body: { percent: (drafts[draftKey(target)] ?? "").replace(",", ".") },
        }),
      ),
    onSuccess: (_data, target) => {
      setDrafts((current) => {
        const rest = { ...current };
        delete rest[draftKey(target)];
        return rest;
      });
      refresh();
    },
  });
  const clear = useMutation({
    mutationFn: (target: Target) =>
      call(
        api.DELETE("/api/resits/enrollments/{id}/courses/{course_pk}/", {
          params: { path: { id: target.enrollment, course_pk: target.course } },
        }),
      ),
    onSuccess: refresh,
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const courseLine = (student: StudentResits, course: ResitCourse) => {
    const target = { enrollment: student.enrollment, course: course.course };
    const key = draftKey(target);
    return (
      <li key={course.course} className="flex flex-wrap items-center gap-2">
        <span>
          <b>{course.course_name}</b>{" "}
          <span className="text-xs text-ink-3">
            {t("resits.percent", { value: course.percent })}
          </span>
        </span>
        <>
          {course.can_enter ? (
            <>
              <Input
                aria-label={t("resits.gradeFor", { course: course.course_name })}
                inputMode="decimal"
                className="w-20 text-right tabular-nums"
                value={drafts[key] ?? course.resit_percent ?? ""}
                onChange={(event) => setDrafts({ ...drafts, [key]: event.target.value })}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={save.isPending || (drafts[key] ?? "").trim() === ""}
                onClick={() => save.mutate(target)}
              >
                {t("resits.save")}
              </Button>
              {course.resit_percent !== null && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={clear.isPending}
                  onClick={() => clear.mutate(target)}
                >
                  {t("resits.clear")}
                </Button>
              )}
            </>
          ) : course.resit_percent !== null ? (
            <span className="whitespace-nowrap tabular-nums">
              {t("resits.percent", { value: course.resit_percent })}
            </span>
          ) : (
            <span className="text-xs text-ink-3">{t("resits.waiting")}</span>
          )}
          {course.signed_by && (
            <span className="text-xs text-ink-3">
              {t("resits.signedBy", { name: course.signed_by })}
            </span>
          )}
        </>
      </li>
    );
  };

  return (
    <>
      <PageHeader title={t("resits.title")} subtitle={t("resits.subtitle")} />
      {classes.length === 0 ? (
        <Banner tone="info">{t("resits.noClass")}</Banner>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="max-w-xs">
              <Field id="resits-class" label={t("resits.class")}>
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
            ) : table.data.students.length === 0 ? (
              <Banner tone="info">{t("resits.none")}</Banner>
            ) : (
              <>
                <Table stacked>
                  <thead>
                    <tr>
                      <th>{t("resits.student")}</th>
                      <th>{t("resits.year")}</th>
                      <th>{t("resits.courses")}</th>
                      <th>{t("resits.outcome")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.data.students.map((student) => (
                      <tr key={student.enrollment}>
                        <td data-label={t("resits.student")} data-wrap>
                          {student.full_name}
                        </td>
                        <td
                          data-label={t("resits.year")}
                          className="whitespace-nowrap tabular-nums"
                        >
                          {student.percent === null
                            ? "—"
                            : t("resits.percent", { value: student.percent })}
                        </td>
                        <td data-label={t("resits.courses")} data-wrap>
                          <ul className="flex flex-col gap-2">
                            {student.courses
                              .filter((course) => course.eligible)
                              .map((course) => courseLine(student, course))}
                            {student.courses.some((course) => !course.eligible) && (
                              <li className="text-xs text-ink-3">
                                {t("resits.notOpenList", {
                                  list: student.courses
                                    .filter((course) => !course.eligible)
                                    .map((course) =>
                                      t("resits.courseAt", {
                                        course: course.course_name,
                                        value: course.percent,
                                      }),
                                    )
                                    .join(", "),
                                })}
                              </li>
                            )}
                          </ul>
                        </td>
                        <td data-label={t("resits.outcome")}>
                          <StatusPill tone={TONES[student.outcome] ?? "gray"}>
                            {t(`resits.outcome_${student.outcome}`)}
                          </StatusPill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                {(save.isError || clear.isError) && (
                  <Banner tone="due">{firstErrorMessage(save.error ?? clear.error, t)}</Banner>
                )}
                <p className="text-xs text-ink-3">
                  {t("resits.help", {
                    pass: table.data.rules.pass_percent,
                    course: table.data.rules.course_pass_percent,
                  })}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
