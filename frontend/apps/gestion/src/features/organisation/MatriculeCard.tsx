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

const VARIABLES = ["{AAAA}", "{AA}", "{0000}", "{OPT}", "{C}"] as const;

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
  saved: {
    matricule_format: string;
    auto_matricule: boolean;
    example: string;
    range: { range_start: number; range_end: number | null; next_number: number } | null;
    range_limit: number;
  };
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(saved.matricule_format);
  const [start, setStart] = useState(String(saved.range?.range_start ?? 1));
  const [end, setEnd] = useState(saved.range?.range_end ? String(saved.range.range_end) : "");
  const [next, setNext] = useState(String(saved.range?.next_number ?? 1));
  const rangeChanged =
    saved.range !== null &&
    (Number(start) !== saved.range.range_start ||
      (end === "" ? null : Number(end)) !== saved.range.range_end ||
      Number(next) !== saved.range.next_number);
  const rangeValid =
    Number(start) >= 1 &&
    Number(next) >= Number(start) &&
    (end === "" || Number(end) >= Number(next));
  const formatChanged = value.trim() !== saved.matricule_format;
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
      call(
        api.PATCH("/api/matricule-format/", {
          body: {
            ...(formatChanged ? { matricule_format: value.trim() } : {}),
            ...(rangeChanged
              ? {
                  range: {
                    range_start: Number(start),
                    range_end: end === "" ? null : Number(end),
                    next_number: Number(next),
                  },
                }
              : {}),
          },
        }),
      ),
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
              <span className="block text-xs text-ink-3">
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
          <div className="flex flex-wrap gap-2" aria-label={t("organisation.matricule.variables")}>
            {VARIABLES.map((variable) => (
              <Button
                key={variable}
                type="button"
                size="sm"
                variant={variable === "{C}" ? "default" : "outline"}
                disabled={!automatic || value.includes(variable)}
                onClick={() => {
                  // La clé de contrôle va toujours à la fin ; les autres variables avant elle.
                  setValue((now) =>
                    variable === "{C}"
                      ? `${now}-${variable}`
                      : now.endsWith("-{C}")
                        ? `${now.slice(0, -4)}-${variable}-{C}`
                        : `${now}${now ? "-" : ""}${variable}`,
                  );
                  save.reset();
                }}
              >
                {t(`organisation.matricule.variable.${variable}`)}
              </Button>
            ))}
          </div>
          {saved.range && (
            <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,150px),1fr))] gap-3">
              <Field id="matricule-start" label={t("organisation.matricule.rangeStart")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    value={start}
                    disabled={!automatic}
                    onChange={(event) => setStart(event.target.value)}
                  />
                )}
              </Field>
              <Field
                id="matricule-end"
                label={t("organisation.matricule.rangeEnd")}
                help={t("organisation.matricule.rangeLimit", { limit: saved.range_limit })}
              >
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    value={end}
                    disabled={!automatic}
                    onChange={(event) => setEnd(event.target.value)}
                  />
                )}
              </Field>
              <Field id="matricule-next" label={t("organisation.matricule.rangeNext")}>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    value={next}
                    disabled={!automatic}
                    onChange={(event) => setNext(event.target.value)}
                  />
                )}
              </Field>
            </div>
          )}
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
          <span className="text-xs text-ink-3">{t("organisation.matricule.note")}</span>
          <Button
            type="submit"
            variant="outline"
            disabled={
              !automatic ||
              save.isPending ||
              value.trim() === "" ||
              !rangeValid ||
              (!formatChanged && !rangeChanged)
            }
          >
            {t("common.save")}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
