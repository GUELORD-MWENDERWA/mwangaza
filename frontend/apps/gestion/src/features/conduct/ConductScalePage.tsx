// Barème de conduite (8.5.1a, maquette `conduite-bareme`) : la liste des infractions avec leurs
// points et les seuils des cotes TB, B, AB, ME, MA. Retirer une infraction la désactive : les
// incidents passés la gardent.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { useRules, useScale, type Rule } from "./data";

type Draft = { id: string | null; label: string; points: string };

export function ConductScalePage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const rules = useRules(true);
  const scale = useScale();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [minimums, setMinimums] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.conduct });

  const saveRule = useMutation({
    mutationFn: (input: Draft) => {
      const body = { label: input.label, points: Number(input.points) };
      return input.id
        ? call(
            api.PATCH("/api/discipline/rules/{id}/", { params: { path: { id: input.id } }, body }),
          )
        : call(api.POST("/api/discipline/rules/", { body }));
    },
    onSuccess: () => {
      setDraft(null);
      refresh();
    },
  });
  const toggle = useMutation({
    mutationFn: (rule: Rule) =>
      call(
        api.PATCH("/api/discipline/rules/{id}/", {
          params: { path: { id: rule.id } },
          body: { is_active: !rule.is_active },
        }),
      ),
    onSuccess: refresh,
  });
  const defaults = useMutation({
    mutationFn: () => call(api.POST("/api/discipline/rules/defaults/")),
    onSuccess: refresh,
  });
  const saveScale = useMutation({
    mutationFn: (rows: { grade: "TB" | "B" | "AB" | "ME" | "MA"; min_points: number }[]) =>
      call(api.PUT("/api/discipline/scale/", { body: { scale: rows } })),
    onSuccess: () => {
      setSaved(true);
      setMinimums({});
      refresh();
    },
  });

  if (rules.isPending || scale.isPending) return <Skeleton label={t("common.loading")} />;
  if (rules.isError) return <LoadError error={rules.error} onRetry={() => void rules.refetch()} />;
  if (scale.isError) return <LoadError error={scale.error} onRetry={() => void scale.refetch()} />;

  const rows = scale.data.scale.map((row) => ({
    ...row,
    value: minimums[row.grade] ?? String(row.min_points),
  }));

  return (
    <>
      <PageHeader title={t("conductScale.title")} subtitle={t("conductScale.subtitle")} />
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_340px]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>{t("conductScale.offences")}</CardTitle>
            <Button size="sm" onClick={() => setDraft({ id: null, label: "", points: "1" })}>
              {t("conductScale.add")}
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rules.data.length === 0 ? (
              <>
                <p className="text-ink-3">{t("conductScale.empty")}</p>
                <p className="text-sm text-ink-3">{t("conductScale.defaultsHelp")}</p>
                {defaults.isError && (
                  <Banner tone="due">{firstErrorMessage(defaults.error, t)}</Banner>
                )}
                <Button
                  variant="outline"
                  disabled={defaults.isPending}
                  onClick={() => defaults.mutate()}
                >
                  {t("conductScale.loadDefaults")}
                </Button>
              </>
            ) : (
              <Table stacked>
                <thead>
                  <tr>
                    <th>{t("conductScale.label")}</th>
                    <th className="text-right">{t("conductScale.points")}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rules.data.map((rule) => (
                    <tr key={rule.id} className={rule.is_active ? "" : "opacity-60"}>
                      <td data-label={t("conductScale.label")} data-wrap>
                        {rule.label}
                        {!rule.is_active && (
                          <StatusPill tone="warn" className="ml-2">
                            {t("conductScale.retired")}
                          </StatusPill>
                        )}
                      </td>
                      <td data-label={t("conductScale.points")} className="text-right">
                        {rule.points}
                      </td>
                      <td>
                        <div className="flex justify-end gap-2">
                          {rule.is_active && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                setDraft({
                                  id: rule.id,
                                  label: rule.label,
                                  points: String(rule.points),
                                })
                              }
                            >
                              {t("conductScale.edit")}
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={toggle.isPending}
                            onClick={() => toggle.mutate(rule)}
                          >
                            {rule.is_active ? t("conductScale.retire") : t("conductScale.restore")}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            {toggle.isError && <Banner tone="due">{firstErrorMessage(toggle.error, t)}</Banner>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("conductScale.scale")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rows.map((row) => (
              <div key={row.grade} className="flex items-center justify-between gap-3">
                <b className="w-10">{row.grade}</b>
                <label htmlFor={`scale-${row.grade}`} className="flex-1 text-sm text-ink-3">
                  {t("conductScale.from")}
                </label>
                <Input
                  id={`scale-${row.grade}`}
                  className="w-24"
                  type="number"
                  min={0}
                  inputMode="numeric"
                  value={row.value}
                  readOnly={row.grade === "TB"}
                  onChange={(event) => {
                    setSaved(false);
                    setMinimums({ ...minimums, [row.grade]: event.target.value });
                  }}
                />
              </div>
            ))}
            <p className="text-sm text-ink-3">{t("conductScale.scaleHelp")}</p>
            {saved && <Banner tone="ok">{t("conductScale.saved")}</Banner>}
            {saveScale.isError && (
              <Banner tone="due">{firstErrorMessage(saveScale.error, t)}</Banner>
            )}
            <Button
              disabled={saveScale.isPending}
              onClick={() =>
                saveScale.mutate(
                  rows.map((row) => ({ grade: row.grade, min_points: Number(row.value) })),
                )
              }
            >
              {t("conductScale.saveScale")}
            </Button>
          </CardContent>
        </Card>
      </div>
      <DialogRoot open={draft !== null} onOpenChange={(open) => !open && setDraft(null)}>
        {draft && (
          <DialogContent
            title={draft.id ? t("conductScale.editTitle") : t("conductScale.addTitle")}
            footer={
              <>
                <DialogClose asChild>
                  <Button variant="outline">{t("conductScale.cancel")}</Button>
                </DialogClose>
                <Button
                  disabled={saveRule.isPending || draft.label.trim() === "" || !draft.points}
                  onClick={() => saveRule.mutate(draft)}
                >
                  {t("conductScale.save")}
                </Button>
              </>
            }
          >
            <div className="flex flex-col gap-4">
              <Field id="rule-label" label={t("conductScale.label")} required>
                {(control) => (
                  <Input
                    {...control}
                    maxLength={120}
                    value={draft.label}
                    onChange={(event) => setDraft({ ...draft, label: event.target.value })}
                  />
                )}
              </Field>
              <Field id="rule-points" label={t("conductScale.points")} required>
                {(control) => (
                  <Input
                    {...control}
                    type="number"
                    min={1}
                    max={100}
                    inputMode="numeric"
                    value={draft.points}
                    onChange={(event) => setDraft({ ...draft, points: event.target.value })}
                  />
                )}
              </Field>
              {saveRule.isError && (
                <Banner tone="due">{firstErrorMessage(saveRule.error, t)}</Banner>
              )}
            </div>
          </DialogContent>
        )}
      </DialogRoot>
    </>
  );
}
