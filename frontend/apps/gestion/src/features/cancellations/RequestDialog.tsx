// Demander l'annulation d'un paiement (F7, maquette `demande-annulation`) : motif obligatoire.
// Appareil mémorisé (`db`) : par la file, avec ou sans réseau (le paiement passe aussitôt à
// « annulation demandée ») ; sinon au serveur, avec l'identifiant de cette demande (un seul
// envoi). Le paiement compte jusqu'à la validation par un autre compte, en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  List,
  Textarea,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import type { LocalDb } from "../../lib/sync/db";
import { queueCancellation } from "../cash/localData";

type Payment = Pick<
  Schemas["Payment"],
  | "id"
  | "receipt_number"
  | "student"
  | "class_group"
  | "received_amount_minor"
  | "received_currency"
  | "paid_at"
  | "allocations"
>;

type Props = { payment: Payment | null; db?: LocalDb; onClose: () => void; onSent?: () => void };

export function RequestDialog({ payment, ...props }: Props) {
  return (
    <DialogRoot open={payment !== null} onOpenChange={(open) => !open && props.onClose()}>
      {payment && <RequestForm key={payment.id} payment={payment} {...props} />}
    </DialogRoot>
  );
}

function RequestForm({
  payment,
  db,
  onClose,
  onSent,
}: Omit<Props, "payment"> & { payment: Payment }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const client = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  // Un seul identifiant pour cette demande : un second envoi rend la même.
  const [id] = useState(uuidv7);
  const schema = z.object({ reason: z.string().trim().min(1, t("fieldErrors.required")).max(200) });
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { reason: "" } });
  const send = useMutation({
    mutationFn: async ({ reason }: z.output<typeof schema>) => {
      if (db) return queueCancellation(db, payment.id, reason);
      await call(api.POST("/api/cancellations/", { body: { id, payment: payment.id, reason } }));
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.payments });
      void client.invalidateQueries({ queryKey: keys.cancellations });
      onSent?.();
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["reason"], form.setError, t)),
  });
  const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);
  const paidAt = `${formatDate(payment.paid_at, i18n.language, school.timezone).slice(0, 5)} ${formatTime(payment.paid_at, i18n.language, school.timezone)}`;

  return (
    <DialogContent
      title={t("cancellations.request.title", { number: payment.receipt_number })}
      description={t("cancellations.request.subtitle")}
      footer={
        <>
          {db && (
            <span className="mr-auto text-sm text-ink-3">{t("cancellations.request.offline")}</span>
          )}
          <DialogClose asChild>
            <Button variant="outline">{t("common.close")}</Button>
          </DialogClose>
          <Button type="submit" form="cancellation-request" disabled={send.isPending}>
            {t("cancellations.request.send")}
          </Button>
        </>
      }
    >
      <form
        id="cancellation-request"
        noValidate
        className="flex flex-col gap-3"
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          send.mutate(values);
        })}
      >
        {general && <Banner tone="due">{general}</Banner>}
        <List>
          <div className="text-sm">
            <span>{t("cancellations.student")}</span>
            <span>
              <b>{payment.student.full_name}</b> · {payment.class_group}
            </span>
          </div>
          <div className="text-sm">
            <span>{t("cancellations.amount")}</span>
            <span>
              <b>{money(payment.received_amount_minor, payment.received_currency)}</b> ·{" "}
              {t("cancellations.cash")} · {paidAt}
            </span>
          </div>
          <div className="text-sm">
            <span>{t("cancellations.allocation")}</span>
            <span>
              {payment.allocations
                .map(
                  (line) =>
                    `${line.fee_type_name} · ${line.label} ${money(line.amount_minor, line.currency)}`,
                )
                .join(" ; ")}
            </span>
          </div>
        </List>
        <Field
          id="cancellation-reason"
          label={t("cancellations.request.reason")}
          required
          help={t("cancellations.request.reasonHelp")}
          error={form.formState.errors.reason?.message}
        >
          {(control) => <Textarea rows={3} {...control} {...form.register("reason")} />}
        </Field>
        <Banner tone="info">{t("cancellations.request.counts")}</Banner>
      </form>
    </DialogContent>
  );
}
