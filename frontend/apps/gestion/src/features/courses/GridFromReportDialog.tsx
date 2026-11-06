// « Lire un bulletin » (IA.5, maquette `grille-depuis-bulletin`) : le PDF (3 pages au plus) ou la
// photo d'un bulletin → l'IA propose les cours et leurs maxima, la personne coche ce qu'elle garde
// puis les met dans la grille, qu'elle corrige et enregistre comme d'habitude. Le fichier n'est
// jamais lu par notre serveur ; il est gardé le temps de l'appel puis effacé. Droits
// `courses.configure` et `ai.use`, usage `course_grid_from_pdf`.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, DialogContent, DialogRoot, StatusPill, Table } from "@mwangaza/ui";
import { useRef, useState } from "react";

import { errorMessage } from "../../lib/errors";
import { useAiCall } from "../ai/useAiCall";

export type ReadCourse = Schemas["GridCourse"];

const ACCEPT = "application/pdf,image/jpeg,image/png";

type Props = { onClose: () => void; onUse: (courses: ReadCourse[]) => void };

export function GridFromReportDialog({ onClose, onUse }: Props) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [unticked, setUnticked] = useState<Set<number>>(new Set());
  const flow = useAiCall({
    name: "course-grid",
    start: (request_id) => {
      const body = new FormData();
      body.append("request_id", request_id);
      body.append("file", file!);
      return call(
        api.POST("/api/ai/course-grid/", {
          body: body as unknown as Schemas["CourseGridAskRequest"],
        }),
      );
    },
    read: (id) => call(api.GET("/api/ai/course-grid/{id}/", { params: { path: { id } } })),
    settle: (id, kept) =>
      call(api.POST("/api/ai/course-grid/{id}/", { params: { path: { id } }, body: { kept } })),
  });
  const proposal = flow.data?.proposal;
  const done = flow.state === "done" && proposal;
  const courses = proposal?.courses ?? [];
  const chosen = courses.filter((_, index) => !unticked.has(index));

  const close = (kept: boolean) => {
    if (flow.id && flow.state === "done") flow.closing.mutate(kept, { onSettled: onClose });
    else onClose();
  };
  const toggle = (index: number) =>
    setUnticked((current) => {
      const next = new Set(current);
      if (!next.delete(index)) next.add(index);
      return next;
    });
  const error = flow.ask.error ?? flow.reading.error ?? flow.closing.error;

  return (
    <DialogRoot open onOpenChange={(open) => !open && close(false)}>
      <DialogContent
        title={t("courses.report.title")}
        description={t("courses.report.subtitle")}
        className="w-[min(760px,calc(100vw-32px))]"
        footer={
          <>
            <Button variant="outline" className="mr-auto" onClick={() => close(false)}>
              {t(done ? "courses.report.abandon" : "common.cancel")}
            </Button>
            {done && (
              <Button
                disabled={chosen.length === 0 || flow.closing.isPending}
                onClick={() => {
                  onUse(chosen);
                  close(true);
                }}
              >
                {t("courses.report.keep", { count: chosen.length })}
              </Button>
            )}
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
          {flow.failed && <Banner tone="due">{t("courses.report.failed")}</Banner>}
          {!done && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-1">
                <input
                  ref={input}
                  type="file"
                  accept={ACCEPT}
                  className="sr-only"
                  aria-label={t("courses.report.file")}
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <Button
                  variant="outline"
                  className="self-start"
                  disabled={flow.waiting}
                  onClick={() => input.current?.click()}
                >
                  {file ? t("courses.report.change") : t("courses.report.choose")}
                </Button>
                {file && <b className="break-all text-sm">{file.name}</b>}
                <span className="text-sm text-ink-3">{t("courses.report.help")}</span>
              </div>
              <Button
                disabled={!file || flow.waiting}
                onClick={() => {
                  if (flow.failed) flow.reset();
                  flow.ask.mutate();
                }}
              >
                {t("courses.report.read")}
              </Button>
            </div>
          )}
          {flow.waiting && (
            <p role="status" className="text-sm text-ink-2">
              {t("courses.report.reading")}
            </p>
          )}
          {done && (
            <>
              <b className="text-sm">{t("courses.report.found", { count: courses.length })}</b>
              {courses.length > 0 && (
                <Table stacked>
                  <thead>
                    <tr>
                      <th />
                      <th>{t("courses.columns.name")}</th>
                      <th>{t("courses.columns.domain")}</th>
                      <th className="text-right">{t("courses.columns.periodMax")}</th>
                      <th>{t("courses.columns.exam")}</th>
                      <th>{t("courses.columns.category")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses.map((course, index) => (
                      <tr key={index} data-tone={course.doubtful ? "warn" : undefined}>
                        <td>
                          <input
                            type="checkbox"
                            className="size-4"
                            aria-label={course.name}
                            checked={!unticked.has(index)}
                            onChange={() => toggle(index)}
                          />
                        </td>
                        <td data-label={t("courses.columns.name")} data-wrap>
                          <b>{course.name}</b>
                          {course.doubtful && (
                            <span className="block text-sm text-warn-900">
                              {t("courses.report.doubtful")}
                            </span>
                          )}
                        </td>
                        <td data-label={t("courses.columns.domain")} data-wrap>
                          {course.domain}
                        </td>
                        <td
                          className="text-right tabular-nums"
                          data-label={t("courses.columns.periodMax")}
                        >
                          {course.period_max}
                        </td>
                        <td data-label={t("courses.columns.exam")}>
                          {course.has_exam ? (
                            <StatusPill tone="info">{2 * course.period_max}</StatusPill>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td data-label={t("courses.columns.category")}>
                          {t(`courses.category.${course.category as "general"}`)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
              {proposal.skipped.length > 0 && (
                <Banner tone="warn">
                  <b>{t("courses.report.skipped")}</b>{" "}
                  {proposal.skipped
                    .map((item) => [item.name, item.reason].filter(Boolean).join(" : "))
                    .join(" · ")}
                </Banner>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
