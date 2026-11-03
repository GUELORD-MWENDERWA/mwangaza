// Conditions générales, confidentialité, registre (CTR.1) : dernière version de chaque texte et
// publication d'une nouvelle (une version publiée ne change plus ; chaque école doit l'accepter).
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  Skeleton,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useDay } from "./shared";

type Doc = Schemas["LegalDocument"];
const KINDS = ["terms", "privacy", "register"] as const;
const KEY = ["console", "billing", "legal"];

export function LegalTab({ manage }: { manage: boolean }) {
  const { t } = useTranslation();
  const day = useDay();
  const [publishing, setPublishing] = useState<(typeof KINDS)[number] | null>(null);
  const docs = useQuery({
    queryKey: KEY,
    queryFn: () => call(api.GET("/api/console/billing/legal/")),
  });
  if (docs.isPending) return <Skeleton label={t("console.billing.loading")} />;
  if (docs.isError) return <Banner tone="due">{errorMessage(docs.error, t)}</Banner>;
  const latest = (kind: string) =>
    docs.data.results.filter((d) => d.kind === kind).sort((a, b) => b.version - a.version)[0];
  return (
    <>
      {KINDS.map((kind) => {
        const doc = latest(kind);
        return (
          <Card key={kind}>
            <CardHeader>
              <CardTitle>{t(`console.billing.legal.${kind}`)}</CardTitle>
              <span className="flex-1 text-sm text-ink-3">
                {doc
                  ? t("console.billing.legal.version", {
                      n: doc.version,
                      date: day((doc.published_at ?? "").slice(0, 10)),
                    })
                  : t("console.billing.legal.none")}
              </span>
              {manage && (
                <Button size="sm" variant="outline" onClick={() => setPublishing(kind)}>
                  {t("console.billing.legal.publish")}
                </Button>
              )}
            </CardHeader>
            {doc && (
              <p className="max-h-36 overflow-hidden px-4 py-3 text-md whitespace-pre-line text-ink-2">
                {doc.body_fr}
              </p>
            )}
          </Card>
        );
      })}
      {publishing && (
        <PublishDialog
          kind={publishing}
          previous={latest(publishing)}
          onClose={() => setPublishing(null)}
        />
      )}
    </>
  );
}

function PublishDialog({
  kind,
  previous,
  onClose,
}: {
  kind: Doc["kind"];
  previous?: Doc;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title_fr: previous?.title_fr ?? "",
    title_en: previous?.title_en ?? "",
    body_fr: previous?.body_fr ?? "",
    body_en: previous?.body_en ?? "",
  });
  const publish = useMutation({
    mutationFn: () => call(api.POST("/api/console/billing/legal/", { body: { kind, ...form } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: KEY });
      onClose();
    },
  });
  const set = (name: keyof typeof form) => ({
    value: form[name],
    onChange: (event: { target: { value: string } }) =>
      setForm({ ...form, [name]: event.target.value }),
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.billing.legal.publishTitle", { name: t(`console.billing.legal.${kind}`) })}
      confirmLabel={t("console.billing.legal.publishConfirm")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => publish.mutate()}
      pending={publish.isPending}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-3">{t("console.billing.legal.publishHelp")}</p>
        <Field id="legal-title-fr" label={t("console.billing.legal.titleFr")} required>
          {(control) => <Input {...control} maxLength={160} {...set("title_fr")} />}
        </Field>
        <Field id="legal-body-fr" label={t("console.billing.legal.bodyFr")} required>
          {(control) => <Textarea {...control} rows={6} {...set("body_fr")} />}
        </Field>
        <Field id="legal-title-en" label={t("console.billing.legal.titleEn")} required>
          {(control) => <Input {...control} maxLength={160} {...set("title_en")} />}
        </Field>
        <Field id="legal-body-en" label={t("console.billing.legal.bodyEn")} required>
          {(control) => <Textarea {...control} rows={6} {...set("body_en")} />}
        </Field>
        {publish.isError && <Banner tone="due">{errorMessage(publish.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}
