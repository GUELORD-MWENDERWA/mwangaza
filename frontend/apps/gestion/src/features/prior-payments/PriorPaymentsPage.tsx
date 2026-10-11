// Reprise en cours d'année (E6, maquette `gestion/reprise-paiements`) : fichier, aperçu (totaux,
// erreurs ligne par ligne), puis enregistrement. Les lignes en erreur ne sont jamais
// enregistrées ; un élève qui a déjà sa reprise n'en reçoit pas une seconde.
import { useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
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
  Steps,
  Table,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useRefresh } from "../organisation/data";
import { type PriorLine, type PriorPreview, priorTemplateUrl, sendPriorPayments } from "./data";

type Step = "file" | "check" | "done";
const STEPS: Step[] = ["file", "check", "done"];

export function PriorPaymentsPage() {
  const { t, i18n } = useTranslation();
  const refresh = useRefresh();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PriorPreview | null>(null);
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const check = useMutation({
    mutationFn: () => sendPriorPayments(file!),
    onSuccess: setPreview,
  });
  const record = useMutation({
    mutationFn: () => sendPriorPayments(file!, preview!.totals),
    onSuccess: async (result) => {
      setPreview(result);
      await refresh(keys.students, keys.payments);
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
            <Link to="/fees" className="text-lake underline">
              {t("fees.title")}
            </Link>{" "}
            / {t("priorPayments.crumb")}
          </>
        }
        title={t("priorPayments.title")}
        subtitle={t("priorPayments.subtitle")}
        actions={
          <Button asChild variant="outline">
            <a href={priorTemplateUrl} download>
              <Icon name="download" size={16} />
              {t("priorPayments.template")}
            </a>
          </Button>
        }
      />
      <Card>
        <CardContent>
          <Steps
            steps={STEPS.map((step, index) => ({
              label: t(`priorPayments.steps.${step}`),
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
            <CardTitle>{t("priorPayments.file.title")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <Banner tone="info">{t("priorPayments.file.rules")}</Banner>
            <Field
              id="prior-file"
              label={t("priorPayments.file.file")}
              help={t("priorPayments.file.help")}
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
          </CardContent>
          <CardFooter className="justify-end">
            <Button disabled={!file || check.isPending} onClick={() => check.mutate()}>
              {check.isPending ? t("priorPayments.file.reading") : t("priorPayments.file.check")}
            </Button>
          </CardFooter>
        </Card>
      ) : (
        <>
          {preview.recorded && (
            <Banner tone="ok">
              {t("priorPayments.done.recorded", {
                count: preview.ready_count,
                number: number(preview.ready_count),
              })}
            </Banner>
          )}
          <div className="grid grid-cols-2 gap-4 min-[900px]:grid-cols-4">
            {preview.totals.map((total) => (
              <Kpi
                key={total.currency}
                label={t(
                  preview.recorded ? "priorPayments.totals.recorded" : "priorPayments.totals.ready",
                )}
                value={formatAmount(total.amount_minor, total.currency)}
                tone="ok"
                sub={t("priorPayments.totals.count", {
                  count: total.count,
                  number: number(total.count),
                })}
              />
            ))}
            <Kpi
              label={t("priorPayments.counts.error")}
              value={number(preview.error_count)}
              tone={preview.error_count ? "due" : undefined}
              sub={t("priorPayments.counts.errorHelp")}
            />
            <Kpi
              label={t("priorPayments.counts.empty")}
              value={number(preview.empty_count)}
              sub={t("priorPayments.counts.emptyHelp")}
            />
          </div>
          {preview.error_count > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("priorPayments.errors.title")}</CardTitle>
              </CardHeader>
              <Lines lines={preview.errors} />
              {preview.error_count > preview.errors.length && (
                <CardContent className="text-ink-3">
                  {t("priorPayments.errors.more", {
                    number: number(preview.error_count - preview.errors.length),
                  })}
                </CardContent>
              )}
              <CardContent className="text-ink-3">{t("priorPayments.errors.help")}</CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>
                {t(
                  preview.recorded ? "priorPayments.ready.titleDone" : "priorPayments.ready.title",
                )}
              </CardTitle>
            </CardHeader>
            {preview.ready_count > 0 ? (
              <Lines lines={preview.ready} />
            ) : (
              <CardContent className="text-ink-3">{t("priorPayments.ready.none")}</CardContent>
            )}
            <CardFooter className="flex-wrap items-center justify-between gap-3">
              <span className="text-[.85rem] text-ink-3">
                {preview.recorded
                  ? t("priorPayments.done.footer")
                  : t("priorPayments.ready.footer", {
                      count: preview.ready_count,
                      number: number(preview.ready_count),
                    })}
              </span>
              <div className="flex flex-wrap gap-2.5">
                <Button variant="outline" onClick={restart}>
                  {t("priorPayments.otherFile")}
                </Button>
                {preview.recorded ? (
                  <Button asChild>
                    <Link to="/students">{t("priorPayments.done.students")}</Link>
                  </Button>
                ) : (
                  <Button
                    disabled={preview.ready_count === 0 || record.isPending}
                    onClick={() => record.mutate()}
                  >
                    {record.isPending
                      ? t("priorPayments.ready.recording")
                      : t("priorPayments.ready.record", {
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

/** Lignes du fichier : prêtes (montant réparti) ou en erreur (le montant tel qu'il est écrit). */
function Lines({ lines }: { lines: PriorLine[] }) {
  const { t } = useTranslation();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("priorPayments.columns.line")}</th>
          <th>{t("priorPayments.columns.student")}</th>
          <th className="text-right">{t("priorPayments.columns.amount")}</th>
          <th>{t("priorPayments.columns.detail")}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => (
          <tr key={line.line}>
            <td>{line.line}</td>
            <td>
              <b>{line.student ?? line.matricule}</b>
              <span className="block text-sm text-ink-3">
                {line.student ? [line.matricule, line.class_group].join(" · ") : null}
              </span>
            </td>
            <td className="text-right tabular-nums">
              {line.amount_minor !== null && line.issues.length === 0
                ? formatAmount(line.amount_minor, line.currency as Currency)
                : [line.amount, line.currency].join(" ")}
            </td>
            <td>
              {line.issues.length === 0
                ? line.fee || t("priorPayments.oldestFirst")
                : line.issues.map((issue) => (
                    <span key={issue.code} className="block text-due">
                      {t(`priorPayments.issues.${issue.code}`, {
                        due:
                          issue.due_minor !== undefined && issue.currency
                            ? formatAmount(issue.due_minor, issue.currency as Currency)
                            : "",
                      })}
                    </span>
                  ))}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
