// Contrôle de la feuille de notes (8.2.2, NB.1) : bandeau d'état (brouillon, envoyée et signée,
// validée, renvoyée avec remarques, date limite), motif d'une modification après envoi ou
// remarques d'un renvoi, historique de la feuille (carnet et fiche de cotes).
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
import { type ComponentProps, useState } from "react";

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

type BannerTone = NonNullable<ComponentProps<typeof Banner>["tone"]>;

export function ControlBanner({
  sheet,
  locked,
  language,
  timeZone,
  className,
}: {
  sheet: Sheet;
  locked: boolean;
  language: string;
  timeZone: string;
  /** Fiche commune (8.1.2a) : le message est précédé du nom de la classe. */
  className?: string;
}) {
  const { t } = useTranslation();
  const day = (value: string) => formatDate(value, language, timeZone);
  const state = ((): [BannerTone, string] | null => {
    if (sheet.status === "validated") {
      return [
        "ok",
        t("grades.control.validated", {
          date: sheet.validated_at ? day(sheet.validated_at) : "",
          name: sheet.validated_by,
        }),
      ];
    }
    if (sheet.status === "submitted") {
      return [
        "info",
        t("grades.control.sent", {
          date: sheet.submitted_at ? day(sheet.submitted_at) : "",
          name: sheet.submitted_by,
        }),
      ];
    }
    if (sheet.reopened && sheet.returned) {
      return [
        "warn",
        t("grades.control.returned", {
          name: sheet.returned.by,
          date: day(sheet.returned.at),
          remarks: sheet.returned.reason,
        }),
      ];
    }
    if (sheet.reopened) return ["warn", t("grades.control.reopened")];
    if (sheet.due_on === null) return null;
    return locked
      ? ["due", t("grades.control.closed", { date: day(sheet.due_on) })]
      : ["info", t("grades.control.open", { date: day(sheet.due_on) })];
  })();
  if (state === null) return null;
  const [tone, text] = state;
  return (
    <Banner tone={tone}>
      {className ? t("grades.joint.classState", { className, text }) : text}
    </Banner>
  );
}

/** Motif demandé avant d'enregistrer une feuille déjà envoyée, ou remarques pour la renvoyer. */
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
          label={t(`grades.reason.${kind}.label`)}
          required
          error={missing ? t(`grades.reason.${kind}.required`) : undefined}
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
  className = "mt-4",
}: {
  sheet: Pick<Sheet, "history">;
  language: string;
  timeZone: string;
  className?: string;
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
    <Card className={className}>
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
