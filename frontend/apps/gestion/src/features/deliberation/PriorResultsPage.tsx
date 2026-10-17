// Reprise des résultats (8.4.7, maquette `gestion/reprise-resultats`) : élèves de l'année en
// cours sans aucune note (année que l'école clôt en arrivant, année tenue sur papier). Fichier et
// date, aperçu (erreurs ligne par ligne), puis enregistrement : chaque ligne devient la décision
// de l'élève dans la délibération de sa classe, à proclamer ensuite. Droit `grades.validate`.
import { formatDay, useTranslation } from "@mwangaza/i18n";
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
  Kpi,
  PageHeader,
  StatusPill,
  Steps,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import {
  type Decision,
  type PriorResultLine,
  type PriorResultPreview,
  priorResultsTemplateUrl,
  sendPriorResults,
  TONES,
} from "./data";

type Step = "file" | "check" | "done";
const STEPS: Step[] = ["file", "check", "done"];

export function PriorResultsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [heldOn, setHeldOn] = useState("");
  const [preview, setPreview] = useState<PriorResultPreview | null>(null);
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const check = useMutation({ mutationFn: () => sendPriorResults(file!), onSuccess: setPreview });
  const record = useMutation({
    mutationFn: () => sendPriorResults(file!, { expected: preview!.ready_count, heldOn }),
    onSuccess: async (result) => {
      setPreview(result);
      await queryClient.invalidateQueries({ queryKey: keys.deliberation });
    },
  });
  const restart = () => {
    setFile(null);
    setPreview(null);
    check.reset();
    record.reset();
  };
  const current: Step = !preview ? "file" : preview.recorded ? "done" : "check";
  const position = STEPS.indexOf(current);
  const error = record.error ?? check.error;
  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/deliberation" className="text-lake underline">
              {t("deliberation.title")}
            </Link>{" "}
            / {t("priorResults.title")}
          </>
        }
        title={t("priorResults.title")}
        subtitle={t("priorResults.subtitle")}
        actions={
          <Button asChild variant="outline">
            <a href={priorResultsTemplateUrl} download>
              <Icon name="download" size={16} />
              {t("priorResults.template")}
            </a>
          </Button>
        }
      />
      <Card>
        <CardContent>
          <Steps
            steps={STEPS.map((step, index) => ({
              label: t(`priorResults.steps.${step}`),
              state:
                index < position || current === "done"
                  ? "done"
                  : index === position
                    ? "current"
                    : "todo",
            }))}
          />
        </CardContent>
      </Card>
      {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
      {!preview ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("priorResults.file.title")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <Banner tone="info">{t("priorResults.file.rules")}</Banner>
            <Field
              id="prior-results-file"
              label={t("priorResults.file.file")}
              help={t("priorResults.file.help")}
            >
              {(control) => (
                <Input
                  {...control}
                  type="file"
                  accept=".xlsx,.csv"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              )}
            </Field>
            <div className="max-w-xs">
              <Field
                id="prior-results-date"
                label={t("priorResults.file.date")}
                help={t("priorResults.file.dateHelp")}
              >
                {(control) => (
                  <Input
                    {...control}
                    type="date"
                    value={heldOn}
                    onChange={(e) => setHeldOn(e.target.value)}
                  />
                )}
              </Field>
            </div>
          </CardContent>
          <CardFooter className="justify-end">
            <Button disabled={!file || !heldOn || check.isPending} onClick={() => check.mutate()}>
              {check.isPending ? t("priorResults.file.reading") : t("priorResults.file.check")}
            </Button>
          </CardFooter>
        </Card>
      ) : (
        <>
          <p className="text-sm text-ink-3">
            {t("priorResults.summary", {
              date: formatDay(heldOn, i18n.language),
              file: file?.name ?? "",
            })}
          </p>
          {preview.recorded && (
            <Banner tone="ok">
              {preview.changed_count === 0
                ? t("priorResults.done.unchanged")
                : t("priorResults.done.recorded", {
                    count: preview.changed_count,
                    number: number(preview.changed_count),
                  })}
            </Banner>
          )}
          <div className="grid grid-cols-1 gap-4 min-[600px]:grid-cols-3">
            <Kpi
              label={t(
                preview.recorded ? "priorResults.counts.recorded" : "priorResults.counts.ready",
              )}
              value={number(preview.ready_count)}
              tone="ok"
              sub={t("priorResults.counts.classes", {
                count: preview.class_count,
                number: number(preview.class_count),
              })}
            />
            <Kpi
              label={t("priorResults.counts.error")}
              value={number(preview.error_count)}
              tone={preview.error_count ? "due" : undefined}
              sub={t("priorResults.counts.errorHelp")}
            />
            <Kpi
              label={t("priorResults.counts.empty")}
              value={number(preview.empty_count)}
              sub={t("priorResults.counts.emptyHelp")}
            />
          </div>
          {preview.error_count > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("priorResults.errors.title")}</CardTitle>
              </CardHeader>
              <Lines lines={preview.errors} />
              {preview.error_count > preview.errors.length && (
                <CardContent className="text-ink-3">
                  {t("priorResults.errors.more", {
                    number: number(preview.error_count - preview.errors.length),
                  })}
                </CardContent>
              )}
              <CardContent className="text-ink-3">{t("priorResults.errors.help")}</CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>
                {t(preview.recorded ? "priorResults.ready.titleDone" : "priorResults.ready.title")}
              </CardTitle>
            </CardHeader>
            {preview.ready_count > 0 ? (
              <Lines lines={preview.ready} />
            ) : (
              <CardContent className="text-ink-3">{t("priorResults.ready.none")}</CardContent>
            )}
            <CardFooter className="flex-wrap items-center justify-between gap-3">
              <span className="text-sm text-ink-3">
                {preview.recorded
                  ? t("priorResults.done.footer")
                  : t("priorResults.ready.footer", {
                      count: preview.ready_count,
                      number: number(preview.ready_count),
                    })}
              </span>
              <div className="flex flex-wrap gap-2.5">
                <Button variant="outline" onClick={restart}>
                  {t("priorResults.otherFile")}
                </Button>
                {preview.recorded ? (
                  <Button asChild>
                    <Link to="/deliberation">{t("priorResults.done.deliberation")}</Link>
                  </Button>
                ) : (
                  <Button
                    disabled={preview.ready_count === 0 || record.isPending}
                    onClick={() => record.mutate()}
                  >
                    {record.isPending
                      ? t("priorResults.ready.recording")
                      : t("priorResults.ready.record", {
                          count: preview.ready_count,
                          number: number(preview.ready_count),
                        })}
                  </Button>
                )}
              </div>
            </CardFooter>
          </Card>
        </>
      )}
    </>
  );
}

/** Lignes du fichier : prêtes (décision reconnue) ou en erreur (ce qui est écrit, et pourquoi). */
function Lines({ lines }: { lines: PriorResultLine[] }) {
  const { t } = useTranslation();
  return (
    <Table stacked>
      <thead>
        <tr>
          <th>{t("priorResults.columns.line")}</th>
          <th>{t("priorResults.columns.student")}</th>
          <th>{t("priorResults.columns.decision")}</th>
          <th className="text-right">{t("priorResults.columns.percent")}</th>
          <th>{t("priorResults.columns.problem")}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => (
          <tr key={line.line}>
            <td data-label={t("priorResults.columns.line")}>{line.line}</td>
            <td data-label={t("priorResults.columns.student")} data-wrap>
              <b>{line.student ?? line.matricule}</b>
              {line.student && (
                <span className="block text-sm text-ink-3">
                  {[line.matricule, line.class_group].join(" · ")}
                </span>
              )}
            </td>
            <td data-label={t("priorResults.columns.decision")}>
              {line.decision && line.issues.length === 0 ? (
                <StatusPill tone={TONES[line.decision] ?? "gray"}>
                  {t(`deliberation.decision_${line.decision as Decision}`)}
                </StatusPill>
              ) : (
                line.decision_text || "—"
              )}
            </td>
            <td data-label={t("priorResults.columns.percent")} className="text-right tabular-nums">
              {line.percent !== null && line.issues.length === 0
                ? t("deliberation.percent", { value: line.percent })
                : line.percent_text || "—"}
            </td>
            <td data-label={t("priorResults.columns.problem")} data-wrap>
              {line.issues.length === 0
                ? "—"
                : line.issues.map((issue) => (
                    <span key={issue.code} className="block text-due">
                      {t(`priorResults.issues.${issue.code}`)}
                    </span>
                  ))}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
