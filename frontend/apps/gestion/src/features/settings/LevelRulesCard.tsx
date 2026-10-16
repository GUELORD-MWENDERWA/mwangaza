// Carte « Règles par niveau » des paramètres de l'école (8.4.1) : chaque niveau (7e, 3e…) peut
// avoir ses propres critères de réussite et de repêchage ; ce qu'il ne change pas vient des règles
// de l'école. Enregistrée niveau par niveau (sans le formulaire des paramètres).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  Skeleton,
} from "@mwangaza/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useLevels, useRefresh, type Level } from "../organisation/data";

const FIELDS = [
  "pass_percent",
  "course_pass_percent",
  "resit_floor_percent",
  "max_resit_courses",
  "orientation_percent",
  "conduct_ma_to_exclude",
  "conduct_me_to_exclude",
  "resit_failures_to_fail",
] as const;
type Field_ = (typeof FIELDS)[number];
type Draft = Record<Field_, string>;

export function LevelRulesCard() {
  const { t } = useTranslation();
  const levels = useLevels();
  const settings = useQuery({
    queryKey: keys.settings,
    queryFn: () => call(api.GET("/api/school/settings/")),
  });
  const refresh = useRefresh();
  const [target, setTarget] = useState<Level | null>(null);
  const [draft, setDraft] = useState<Draft>(blank());

  const save = useMutation({
    mutationFn: ({ level, rules }: { level: Level; rules: Record<string, number> }) =>
      call(
        api.PATCH("/api/levels/{id}/", {
          params: { path: { id: level.id } },
          body: { pass_rules: rules },
        }),
      ),
    onSuccess: async () => {
      setTarget(null);
      await refresh(keys.levels);
    },
  });

  if (levels.isPending || settings.isPending) return <Skeleton label={t("common.loading")} />;
  if (levels.isError || settings.isError) return null;
  const school = settings.data.pass_rules;

  const open = (level: Level) => {
    save.reset();
    setDraft({
      ...blank(),
      ...Object.fromEntries(
        FIELDS.filter((f) => f in rulesOf(level)).map((f) => [f, String(rulesOf(level)[f])]),
      ),
    });
    setTarget(level);
  };
  const rules = () =>
    Object.fromEntries(
      FIELDS.filter((f) => /^\d{1,3}$/.test(draft[f].trim())).map((f) => [f, Number(draft[f])]),
    );
  const summary = (level: Level) => {
    const own = rulesOf(level);
    return Object.keys(own).length === 0
      ? t("settings.levelRules.sameAsSchool")
      : t("settings.levelRules.summary", {
          pass: own.pass_percent ?? school.pass_percent,
          course: own.course_pass_percent ?? school.course_pass_percent,
          max: own.max_resit_courses ?? school.max_resit_courses,
        });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.levelRules.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.levelRules.intro")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {levels.data.length === 0 && (
          <span className="text-sm text-ink-3">{t("settings.levelRules.none")}</span>
        )}
        {levels.data.map((level) => (
          <div
            key={level.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line p-3"
          >
            <span>
              <b>{level.name}</b>
              <span className="block text-sm text-ink-3">{summary(level)}</span>
            </span>
            <Button size="sm" variant="outline" type="button" onClick={() => open(level)}>
              {t("settings.levelRules.edit")}
            </Button>
          </div>
        ))}
      </CardContent>
      <ConfirmDialog
        open={target !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setTarget(null);
        }}
        title={t("settings.levelRules.dialogTitle", { name: target?.name ?? "" })}
        confirmLabel={t("settings.levelRules.save")}
        cancelLabel={t("settings.levelRules.cancel")}
        pending={save.isPending}
        onConfirm={() => target && save.mutate({ level: target, rules: rules() })}
      >
        <div className="flex flex-col gap-3">
          <p className="text-ink-3">{t("settings.levelRules.dialogHelp")}</p>
          {FIELDS.map((name) => (
            <Field
              key={name}
              id={`level-rules-${name}`}
              label={t(`settings.levelRules.${name}`)}
              help={t("settings.levelRules.schoolValue", { value: school[name] })}
            >
              {(control) => (
                <Input
                  {...control}
                  inputMode="numeric"
                  className="max-w-32 text-right tabular-nums"
                  placeholder={String(school[name])}
                  value={draft[name]}
                  onChange={(event) => setDraft({ ...draft, [name]: event.target.value })}
                />
              )}
            </Field>
          ))}
          <Button
            type="button"
            variant="outline"
            disabled={save.isPending}
            onClick={() => target && save.mutate({ level: target, rules: {} })}
          >
            {t("settings.levelRules.reset")}
          </Button>
          {save.isError && <Banner tone="due">{firstErrorMessage(save.error, t)}</Banner>}
        </div>
      </ConfirmDialog>
    </Card>
  );
}

function blank(): Draft {
  return Object.fromEntries(FIELDS.map((f) => [f, ""])) as Draft;
}

/** Règles propres au niveau (vide : celles de l'école). */
function rulesOf(level: Level): Record<string, number> {
  return (level.pass_rules ?? {}) as Record<string, number>;
}
