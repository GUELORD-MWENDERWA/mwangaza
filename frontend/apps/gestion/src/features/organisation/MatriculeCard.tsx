// Format du matricule (C3) : aperçu « Prochain matricule » pendant la saisie (calculé par le
// serveur, seul à générer les matricules), enregistrement pour les matricules donnés ensuite.
// Interrupteur (C5) : sur non, ni l'inscription ni l'import ne donnent de matricule.
import { ApiError, api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Skeleton,
  Switch,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, fieldMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useSettled } from "../../lib/settled";
import { LoadError } from "../status/StatusPages";

/** Valeur stable depuis `delay` ms : un aperçu par pause dans la frappe, pas par touche. */

export function MatriculeCard() {
  const { t } = useTranslation();
  const current = useQuery({
    queryKey: keys.matricule,
    queryFn: () => call(api.GET("/api/matricule-format/")),
  });
  if (current.isPending) return <Skeleton label={t("common.loading")} />;
  if (current.isError) {
    return <LoadError error={current.error} onRetry={() => void current.refetch()} />;
  }
  return <MatriculeForm saved={current.data} />;
}

function MatriculeForm({
  saved,
}: {
  saved: { matricule_format: string; auto_matricule: boolean; example: string };
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(saved.matricule_format);
  const settled = useSettled(value.trim(), 400);
  const changed = settled !== saved.matricule_format && settled !== "";
  const preview = useQuery({
    queryKey: [...keys.matricule, "preview", settled],
    queryFn: () =>
      call(api.POST("/api/matricule-format/preview/", { body: { matricule_format: settled } })),
    enabled: changed,
    retry: false,
  });
  const save = useMutation({
    mutationFn: () =>
      call(api.PATCH("/api/matricule-format/", { body: { matricule_format: value.trim() } })),
    onSuccess: (data) => queryClient.setQueryData(keys.matricule, data),
  });
  const toggle = useMutation({
    mutationFn: (on: boolean) =>
      call(api.PATCH("/api/matricule-format/", { body: { auto_matricule: on } })),
    onSuccess: (data) => {
      queryClient.setQueryData(keys.matricule, data);
      // L'écran d'inscription lit ce choix dans l'école.
      void queryClient.invalidateQueries({ queryKey: keys.school });
    },
  });
  const automatic = saved.auto_matricule;
  const error = toggle.error ?? save.error ?? (changed ? preview.error : null);
  const [fieldError] = error instanceof ApiError ? (error.fields.matricule_format ?? []) : [];
  const example = changed ? preview.data?.example : saved.example;

  return (
    <Card>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <CardHeader>
          <CardTitle>{t("organisation.matricule.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="matricule-auto" className="cursor-pointer">
              <b>{t("organisation.matricule.auto")}</b>
              <span className="block text-[.8rem] text-ink-3">
                {t(automatic ? "organisation.matricule.autoOn" : "organisation.matricule.autoOff")}
              </span>
            </label>
            <Switch
              id="matricule-auto"
              checked={automatic}
              disabled={toggle.isPending}
              onCheckedChange={(on) => toggle.mutate(on)}
            />
          </div>
          <Field
            id="matricule-format"
            label={t("organisation.matricule.label")}
            help={t("organisation.matricule.help")}
            error={
              value.trim() === ""
                ? t("validation.matriculeRequired")
                : fieldError
                  ? fieldMessage(fieldError.code, t)
                  : undefined
            }
          >
            {(control) => (
              <Input
                {...control}
                className="font-mono"
                value={value}
                disabled={!automatic}
                onChange={(event) => {
                  setValue(event.target.value);
                  save.reset();
                }}
              />
            )}
          </Field>
          {automatic && example && !fieldError && (
            <Banner tone="info">
              {t("organisation.matricule.next")} <b className="font-mono">{example}</b>
            </Banner>
          )}
          {error && !fieldError && <Banner tone="due">{errorMessage(error, t)}</Banner>}
          {save.isSuccess && (
            <Banner tone="ok" role="status">
              {t("organisation.matricule.saved")}
            </Banner>
          )}
        </CardContent>
        <CardFooter>
          <span className="text-[.8rem] text-ink-3">{t("organisation.matricule.note")}</span>
          <Button
            type="submit"
            variant="outline"
            disabled={
              !automatic ||
              save.isPending ||
              value.trim() === "" ||
              value.trim() === saved.matricule_format
            }
          >
            {t("common.save")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
