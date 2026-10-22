// Fenêtre « Publier » de l'éditeur de l'horaire (EDT.4a, maquette
// `gestion/publication-emploi-du-temps`) : bilan du brouillon, date d'effet, version remplacée.
// Le serveur refuse tant qu'il y a du rouge ; le bouton est grisé dans ce cas, le blocage expliqué.
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  StatusPill,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import type { DraftState } from "./editor";

/** Jour du calendrier de l'école (`2026-10-22`), borné à ce que le serveur accepte. */
export function defaultValidFrom(today: string, earliest: string, latest: string): string {
  if (today < earliest) return earliest;
  return today > latest ? latest : today;
}

export function PublishDialog({
  state,
  year,
  current,
  timeZone,
  onClose,
  onPublished,
}: {
  state: DraftState;
  year: { starts_on: string; ends_on: string };
  current?: { name: string; valid_from: string | null };
  timeZone: string;
  onClose: () => void;
  onPublished: (state: DraftState) => void;
}) {
  const { t, i18n } = useTranslation();
  const earliest =
    current?.valid_from && current.valid_from > year.starts_on
      ? current.valid_from
      : year.starts_on;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date());
  const [validFrom, setValidFrom] = useState(defaultValidFrom(today, earliest, year.ends_on));
  const publish = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/drafts/{id}/publish/", {
          params: { path: { id: state.id } },
          body: { valid_from: validFrom },
        }),
      ),
    onSuccess: onPublished,
  });
  const placed = state.classes.reduce((sum, row) => sum + row.placed, 0);
  const due = state.classes.reduce((sum, row) => sum + row.due, 0);
  // Même compte que « placées / dues » : par classe (des groupes en parallèle comptent une fois).
  const left = state.classes.reduce((sum, row) => sum + Math.max(row.due - row.placed, 0), 0);
  const blocked = state.errors > 0;
  const day = (value: string) => formatDay(value, i18n.language);
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("timetable.editor.publishing.title", { name: state.name })}
        description={t("timetable.editor.publishing.subtitle")}
        className="w-[min(520px,calc(100vw-32px))]"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">
                {t(blocked ? "timetable.editor.publishing.close" : "common.cancel")}
              </Button>
            </DialogClose>
            <Button
              disabled={blocked || !validFrom || publish.isPending}
              onClick={() => publish.mutate()}
            >
              {t("timetable.editor.publish")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3.5">
          {publish.isError && <Banner tone="due">{errorMessage(publish.error, t)}</Banner>}
          <dl className="m-0 flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between gap-3 border-b border-line-soft pb-2">
              <dt className="text-ink-3">{t("timetable.editor.publishing.placed")}</dt>
              <dd className="m-0 text-right font-bold">
                {t("timetable.editor.publishing.placedValue", {
                  placed,
                  due,
                  count: state.classes.length,
                })}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3 border-b border-line-soft pb-2">
              <dt className="text-ink-3">{t("timetable.editor.publishing.conflicts")}</dt>
              <dd className="m-0">
                <StatusPill tone={blocked ? "due" : "ok"}>
                  {blocked
                    ? t("timetable.editor.conflicts", { count: state.errors })
                    : t("timetable.editor.noConflict")}
                </StatusPill>
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-ink-3">{t("timetable.editor.publishing.warnings")}</dt>
              <dd className="m-0">
                <StatusPill tone={state.warnings ? "warn" : "gray"}>
                  {state.warnings
                    ? t("timetable.editor.publishing.warningCount", { count: state.warnings })
                    : t("timetable.editor.publishing.none")}
                </StatusPill>
              </dd>
            </div>
          </dl>
          {blocked ? (
            <Banner tone="due">{t("timetable.editor.publishing.blocked")}</Banner>
          ) : (
            left > 0 && (
              <Banner tone="warn">{t("timetable.editor.publishing.left", { count: left })}</Banner>
            )
          )}
          <Field
            id="publish-valid-from"
            label={t("timetable.editor.publishing.validFrom")}
            help={
              blocked
                ? undefined
                : current?.valid_from
                  ? t("timetable.editor.publishing.validFromAfter", {
                      start: day(earliest),
                      end: day(year.ends_on),
                    })
                  : t("timetable.editor.publishing.validFromYear", {
                      start: day(earliest),
                      end: day(year.ends_on),
                    })
            }
          >
            {(control) => (
              <Input
                {...control}
                type="date"
                min={earliest}
                max={year.ends_on}
                disabled={blocked}
                value={validFrom}
                onChange={(event) => setValidFrom(event.target.value)}
              />
            )}
          </Field>
          {current && !blocked && (
            <Banner tone="info">
              {t("timetable.editor.publishing.replaces", { name: current.name })}
            </Banner>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
