// Validation des notes (8.2.2, maquette `notes-validation`) : les feuilles que les enseignants ont
// envoyées, à ouvrir pour les valider ou les renvoyer, et la date limite de saisie de chaque
// période. Droit `grades.validate` (double authentification).
import { api, call } from "@mwangaza/api";
import { firstErrorMessage, formatDate, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  Input,
  PageHeader,
  Skeleton,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { termLabels } from "../../lib/terms";
import { LoadError } from "../status/StatusPages";
import { useValidation } from "./data";
import { gradableTerms } from "./GradesPage";

export function GradeValidationPage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const validation = useValidation();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const setDeadline = useMutation({
    mutationFn: (input: { term: string; due_on: string | null }) =>
      call(
        api.PUT("/api/terms/{term}/grades-deadline/", {
          params: { path: { term: input.term } },
          body: { due_on: input.due_on },
        }),
      ),
    onSuccess: (_result, input) => {
      setDrafts((all) =>
        Object.fromEntries(Object.entries(all).filter(([id]) => id !== input.term)),
      );
      setSaved(true);
      void queryClient.invalidateQueries({ queryKey: keys.gradeValidation });
      void queryClient.invalidateQueries({ queryKey: keys.gradeSheet });
    },
  });

  if (validation.isPending) return <Skeleton label={t("common.loading")} />;
  if (validation.isError) {
    return <LoadError error={validation.error} onRetry={() => void validation.refetch()} />;
  }
  const { terms, deadlines, sheets } = validation.data;
  const labels = termLabels(terms, t);
  const leaves = gradableTerms(terms, labels);
  const label = new Map(leaves.map((leaf) => [leaf.id, leaf.label]));
  const due = new Map(deadlines.map((row) => [row.term, row.due_on]));

  return (
    <>
      <PageHeader title={t("gradeValidation.title")} subtitle={t("gradeValidation.subtitle")} />
      {saved && (
        <div className="mb-4">
          <Banner tone="ok">{t("gradeValidation.deadlines.saved")}</Banner>
        </div>
      )}
      {setDeadline.isError && (
        <div className="mb-4">
          <Banner tone="due">{firstErrorMessage(setDeadline.error, t)}</Banner>
        </div>
      )}
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>{t("gradeValidation.waiting", { count: sheets.length })}</CardTitle>
          </CardHeader>
          {sheets.length === 0 ? (
            <p className="px-5 py-6 text-sm text-ink-2">{t("gradeValidation.none")}</p>
          ) : (
            <Table stacked>
              <thead>
                <tr>
                  <th>{t("gradeValidation.columns.course")}</th>
                  <th>{t("gradeValidation.columns.term")}</th>
                  <th>{t("gradeValidation.columns.sentBy")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {sheets.map((row) => (
                  <tr key={`${row.course}-${row.term}`}>
                    <td data-label={t("gradeValidation.columns.course")}>
                      <b>{row.course_name}</b>
                      <div className="text-sm text-ink-3">{row.class_group}</div>
                    </td>
                    <td data-label={t("gradeValidation.columns.term")}>
                      {label.get(row.term) ?? ""}
                    </td>
                    <td data-label={t("gradeValidation.columns.sentBy")}>
                      {row.submitted_by || "—"}
                      <div className="text-sm text-ink-3">
                        {formatDateTime(row.submitted_at, i18n.language, school.timezone)}
                      </div>
                    </td>
                    <td className="text-right">
                      <Button asChild size="sm">
                        <Link to={`/grades?course=${row.course}&term=${row.term}`}>
                          {t("gradeValidation.open")}
                        </Link>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("gradeValidation.deadlines.title")}</CardTitle>
          </CardHeader>
          <p className="px-5 pt-3 text-sm text-ink-2">{t("gradeValidation.deadlines.help")}</p>
          <ul className="divide-y divide-line-soft">
            {leaves.map((leaf) => {
              const current = due.get(leaf.id) ?? "";
              const value = drafts[leaf.id] ?? current;
              return (
                <li key={leaf.id} className="flex flex-wrap items-center gap-2 px-5 py-3">
                  <span className="mr-auto text-sm font-medium">{leaf.label}</span>
                  <Input
                    type="date"
                    aria-label={t("gradeValidation.deadlines.dateOf", { term: leaf.label })}
                    value={value}
                    onChange={(event) => {
                      setSaved(false);
                      setDrafts((all) => ({ ...all, [leaf.id]: event.target.value }));
                    }}
                    className="w-auto"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={value === current || setDeadline.isPending}
                    onClick={() => setDeadline.mutate({ term: leaf.id, due_on: value || null })}
                  >
                    {t("common.save")}
                  </Button>
                  {current && (
                    <span className="basis-full text-sm text-ink-3">
                      {t("gradeValidation.deadlines.until", {
                        date: formatDate(current, i18n.language, school.timezone),
                      })}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </>
  );
}
