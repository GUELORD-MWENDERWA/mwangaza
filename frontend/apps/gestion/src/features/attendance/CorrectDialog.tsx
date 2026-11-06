// Correction d'une présence (6.6) : « présent en classe, carte oubliée ». Une ligne de plus au
// journal avec son motif, jamais une modification du passage ; droit dédié, au journal d'audit.
import { useTranslation } from "@mwangaza/i18n";
import { Banner, ConfirmDialog, Field, Input, Select } from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { type DayStatus, useCorrect } from "./follow";

export type Target = { kind: "student" | "member"; id: string; name: string; status: DayStatus };

export function CorrectDialog({
  date,
  target,
  onClose,
}: {
  date: string;
  target: Target | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const correct = useCorrect();
  const [status, setStatus] = useState<DayStatus>("present");
  const [reason, setReason] = useState("");
  const [shown, setShown] = useState<Target | null>(null);
  // Une nouvelle personne : on repart d'un formulaire vide (état réglé pendant le rendu).
  if (target !== shown) {
    setShown(target);
    setStatus(target?.status === "present" ? "absent" : "present");
    setReason("");
    correct.reset();
  }
  return (
    <ConfirmDialog
      open={target !== null}
      onOpenChange={(open) => !open && onClose()}
      title={t("follow.correction.title", { name: target?.name ?? "" })}
      confirmLabel={t("follow.correction.confirm")}
      cancelLabel={t("common.cancel")}
      pending={correct.isPending}
      confirmDisabled={reason.trim() === ""}
      onConfirm={() =>
        target &&
        correct.mutate(
          {
            date,
            status,
            reason: reason.trim(),
            ...(target.kind === "student" ? { student: target.id } : { member: target.id }),
          },
          { onSuccess: onClose },
        )
      }
    >
      <p className="text-sm text-ink-2">{t("follow.correction.text")}</p>
      <Field id="correction-status" label={t("follow.correction.status")}>
        {(control) => (
          <Select
            {...control}
            value={status}
            onChange={(event) => setStatus(event.target.value as DayStatus)}
          >
            <option value="present">{t("follow.status.present")}</option>
            <option value="late">{t("follow.status.late")}</option>
            <option value="absent">{t("follow.status.absent")}</option>
          </Select>
        )}
      </Field>
      <Field
        id="correction-reason"
        label={t("follow.correction.reason")}
        help={t("follow.correction.reasonHelp")}
      >
        {(control) => (
          <Input
            {...control}
            maxLength={200}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        )}
      </Field>
      {correct.isError && <Banner tone="due">{errorMessage(correct.error, t)}</Banner>}
    </ConfirmDialog>
  );
}
