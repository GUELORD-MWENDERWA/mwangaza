// « Écrire au support » (SUP.1, maquette `gestion/aide-demande`) : sujet et message, plus ce qui
// est joint d'office (écran, école, version, appareil, numéro) et que la personne voit avant
// d'envoyer. En ligne seulement : bouton grisé sans connexion, le texte tapé reste.
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Textarea,
} from "@mwangaza/ui";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation } from "react-router";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { displayName } from "../../lib/people";
import { useOnline } from "../../lib/online";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { deviceLabel, useOpenRequest } from "./data";

export function SupportDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <DialogRoot open={open} onOpenChange={(next) => !next && onClose()}>
      {open && <SupportForm onClose={onClose} />}
    </DialogRoot>
  );
}

function SupportForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const school = useCurrentSchool();
  const me = useCurrentMe();
  const online = useOnline();
  const [sent, setSent] = useState<number | null>(null);
  const [general, setGeneral] = useState<string | null>(null);
  const schema = z.object({
    subject: z.string().trim().min(1, t("fieldErrors.required")).max(120),
    body: z.string().trim().min(1, t("fieldErrors.required")).max(5000),
  });
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { subject: "", body: "" } });
  const open = useOpenRequest();
  const device = deviceLabel();
  const { errors } = form.formState;

  if (sent !== null) {
    return (
      <DialogContent
        title={t("helpRequests.form.title")}
        footer={
          <>
            <Button variant="outline" onClick={onClose}>
              {t("common.close")}
            </Button>
            <Link
              to="/help/requests"
              onClick={onClose}
              className="inline-flex h-10 items-center rounded-lg bg-lake px-4 text-sm font-semibold text-white"
            >
              {t("helpRequests.form.seeRequests")}
            </Link>
          </>
        }
      >
        <Banner tone="ok">{t("helpRequests.form.sent", { number: sent })}</Banner>
      </DialogContent>
    );
  }
  return (
    <DialogContent
      title={t("helpRequests.form.title")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="outline">{t("common.cancel")}</Button>
          </DialogClose>
          <Button type="submit" form="support-request" disabled={!online || open.isPending}>
            {t("helpRequests.form.send")}
          </Button>
        </>
      }
    >
      <form
        id="support-request"
        noValidate
        className="flex flex-col gap-3"
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          open.mutate(
            { ...values, screen: pathname, app_version: __APP_VERSION__, device },
            {
              onSuccess: (created) => setSent(created.number),
              onError: (error) =>
                setGeneral(applyServerErrors(error, ["subject", "body"], form.setError, t)),
            },
          );
        })}
      >
        <p className="text-sm text-ink-2">{t("helpRequests.form.intro")}</p>
        {!online && <Banner tone="warn">{t("helpRequests.form.offline")}</Banner>}
        {general && <Banner tone="due">{general}</Banner>}
        <Field
          id="support-subject"
          label={t("helpRequests.form.subject")}
          required
          error={errors.subject?.message}
        >
          {(control) => <Input {...control} maxLength={120} {...form.register("subject")} />}
        </Field>
        <Field
          id="support-body"
          label={t("helpRequests.form.body")}
          required
          help={t("helpRequests.form.bodyHelp")}
          error={errors.body?.message}
        >
          {(control) => (
            <Textarea {...control} rows={5} maxLength={5000} {...form.register("body")} />
          )}
        </Field>
        <div className="rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink-2">
          <b className="text-ink">{t("helpRequests.form.attached")}</b>
          <ul className="mt-1 list-disc pl-5">
            <li>{t("helpRequests.form.screen", { screen: pathname })}</li>
            <li>{t("helpRequests.form.school", { name: school.name, code: school.code })}</li>
            <li>
              {t("helpRequests.form.version", { version: __APP_VERSION__ })}
              {device && ` · ${device}`}
            </li>
            {me && (
              <li>{t("helpRequests.form.account", { name: displayName(me), phone: me.phone })}</li>
            )}
          </ul>
        </div>
      </form>
    </DialogContent>
  );
}
