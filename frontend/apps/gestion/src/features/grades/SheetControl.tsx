// Contrôle de la feuille de notes (8.2.2) : bandeau d'état (brouillon, envoyée, validée, date
// limite), motif d'une modification après envoi ou d'une réouverture, historique de la feuille.
import { formatDate, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
} from "@mwangaza/ui";
import { useState } from "react";

import type { Sheet } from "./data";

/** « 2026-11-09 » dans le fuseau de l'école : pour comparer à la date limite. */
export function todayIn(timeZone: string): string {
  return new Date().toLocaleDateString("en-CA", { timeZone });
}

/** Feuille fermée à la saisie : validée, ou date limite passée sans réouverture (sauf pour qui
 *  valide les notes, que la date ne ferme pas). */
export function isLocked(sheet: Sheet, canValidate: boolean, today: string): boolean {
  if (sheet.status === "validated") return true;
  const late = sheet.due_on !== null && sheet.due_on < today;
  return late && !sheet.reopened && !canValidate;
}

export function ControlBanner({
  sheet,
  locked,
  language,
  timeZone,
}: {
  sheet: Sheet;
  locked: boolean;
  language: string;
  timeZone: string;
}) {
  const { t } = useTranslation();
  const day = (value: string) => formatDate(value, language, timeZone);
  if (sheet.status === "validated") {
    return (
      <Banner tone="ok">
        {t("grades.control.validated", {
          date: sheet.validated_at ? day(sheet.validated_at) : "",
          name: sheet.validated_by,
        })}
      </Banner>
    );
  }
  if (sheet.status === "submitted") {
    return (
      <Banner tone="info">
        {t("grades.control.sent", {
          date: sheet.submitted_at ? day(sheet.submitted_at) : "",
          name: sheet.submitted_by,
        })}
      </Banner>
    );
  }
  if (sheet.reopened) return <Banner tone="warn">{t("grades.control.reopened")}</Banner>;
  if (sheet.due_on === null) return null;
  return locked ? (
    <Banner tone="due">{t("grades.control.closed", { date: day(sheet.due_on) })}</Banner>
  ) : (
    <Banner tone="info">{t("grades.control.open", { date: day(sheet.due_on) })}</Banner>
  );
}

/** Motif demandé avant d'enregistrer une feuille déjà envoyée, ou de la rouvrir. */
export function ReasonDialog({
  kind,
  pending,
  onClose,
  onConfirm,
}: {
  kind: "edit" | "reopen";
  pending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState(false);
  const confirm = () => {
    if (reason.trim().length < 3) return setMissing(true);
    onConfirm(reason.trim());
  };
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t(`grades.reason.${kind}.title`)}
        description={t(`grades.reason.${kind}.help`)}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button disabled={pending} onClick={confirm}>
              {t(`grades.reason.${kind}.confirm`)}
            </Button>
          </>
        }
      >
        <Field
          id="grades-reason"
          label={t("grades.reason.label")}
          required
          error={missing ? t("grades.reason.required") : undefined}
        >
          {(control) => (
            <Input
              {...control}
              value={reason}
              maxLength={300}
              autoFocus
              onChange={(event) => setReason(event.target.value)}
            />
          )}
        </Field>
      </DialogContent>
    </DialogRoot>
  );
}

/** Ce qui s'est passé sur la feuille, le plus récent d'abord (le journal de l'école). */
export function SheetHistory({
  sheet,
  language,
  timeZone,
}: {
  sheet: Sheet;
  language: string;
  timeZone: string;
}) {
  const { t } = useTranslation();
  if (sheet.history.length === 0) return null;
  const actionLabel = (action: string, changes: number) => {
    if (action === "grades.submitted") return t("grades.history.submitted");
    if (action === "grades.validated") return t("grades.history.validated");
    if (action === "grades.reopened") return t("grades.history.reopened");
    return t("grades.history.changed", { count: changes });
  };
  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>{t("grades.history.title")}</CardTitle>
      </CardHeader>
      <ul className="divide-y divide-line-soft">
        {sheet.history.map((entry, index) => (
          <li key={index} className="px-5 py-3 text-sm">
            <b>{actionLabel(entry.action, entry.changes)}</b>
            <span className="text-ink-3">
              {" · "}
              {entry.by} · {formatDateTime(entry.at, language, timeZone)}
            </span>
            {entry.reason && <p className="text-ink-2">« {entry.reason} »</p>}
          </li>
        ))}
      </ul>
    </Card>
  );
}
