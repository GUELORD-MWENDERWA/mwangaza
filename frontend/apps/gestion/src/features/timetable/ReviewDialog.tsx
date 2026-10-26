// « Demander conseil » (IA.2b, maquette `conseil-emploi-du-temps`) : l'assistant lit les chiffres
// calculés par le serveur (contrôles de l'année, ou conflits d'un horaire calculé) et explique ;
// chaque action proposée s'applique d'un clic par les mêmes services que l'écran normal, le
// serveur revérifie. Un clic = un appel. Droits `timetable.manage` et `ai.use`.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, DialogContent, DialogRoot } from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { keys } from "../../lib/queries";

const POLL_MS = 2000;

type Props = { timetable?: string; onClose: () => void };

export function ReviewDialog({ timetable, onClose }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const requestId = useRef(uuidv7());
  const [callId, setCallId] = useState<string | null>(null);
  const [applied, setApplied] = useState<string[]>([]);

  const ask = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/review/", {
          body: { request_id: requestId.current, timetable },
        }),
      ),
    onSuccess: (started) => setCallId(started.id),
  });
  const reading = useQuery({
    enabled: callId !== null,
    queryKey: [...keys.timetable, "review", callId],
    queryFn: () =>
      call(api.GET("/api/timetable/review/{id}/", { params: { path: { id: callId! } } })),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.state ?? "queued") ? POLL_MS : false,
  });
  // Ouvrir la fenêtre = le clic « Demander conseil » : un seul départ, même en double rendu.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    ask.mutate();
  }, [ask]);
  const state = reading.data?.state;
  const proposal = reading.data?.proposal;

  const apply = useMutation({
    mutationFn: (key: string) =>
      call(
        api.POST("/api/timetable/review/{id}/apply/", {
          params: { path: { id: callId! } },
          body: { key },
        }),
      ),
    onSuccess: (next, key) => {
      setApplied((current) => [...current, key]);
      queryClient.setQueryData([...keys.timetable, "review", callId], next);
    },
  });
  const finish = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/review/{id}/finish/", {
          params: { path: { id: callId! } },
          body: { applied: applied.length > 0 },
        }),
      ),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.timetable });
      onClose();
    },
  });
  const close = () => (state === "done" ? finish.mutate() : onClose());

  const waiting = ask.isPending || state === "queued" || state === "running";
  const failed = state === "error" || state === "refused";
  const error = ask.error ?? apply.error ?? reading.error;

  return (
    <DialogRoot open onOpenChange={(open) => !open && close()}>
      <DialogContent
        title={t("timetable.review.title")}
        description={t("timetable.review.subtitle")}
        className="w-[min(640px,calc(100vw-32px))]"
        footer={<Button onClick={close}>{t("timetable.review.done")}</Button>}
      >
        <div className="flex flex-col gap-4">
          {error && <Banner tone="due">{firstErrorMessage(error, t)}</Banner>}
          {waiting && (
            <p role="status" className="text-sm text-ink-2">
              {t("timetable.review.reading")}
            </p>
          )}
          {failed && <Banner tone="due">{t("timetable.review.failed")}</Banner>}
          {proposal && (
            <>
              <p className="m-0 whitespace-pre-line break-words">{proposal.explanation}</p>
              <div className="flex flex-col border-t border-line-soft pt-3">
                <b className="mb-1 text-sm">
                  {proposal.actions.length === 0
                    ? t("timetable.review.nothing")
                    : t("timetable.review.proposed", { count: proposal.actions.length })}
                </b>
                {proposal.actions.map((action) => (
                  <div
                    key={action.key}
                    className="flex flex-wrap items-start gap-x-3 gap-y-2 border-b border-line-soft py-3"
                  >
                    <span className="flex min-w-0 flex-1 basis-[240px] flex-col gap-1">
                      <span className="break-words">
                        <b>{t(`timetable.review.kind.${action.kind}`)}</b>
                        {action.label &&
                          ` · ${action.kind === "set_pattern" ? `${action.label} : ${action.pattern}` : t(`timetable.constraints.kinds.${action.label}`, { defaultValue: action.label })}`}
                      </span>
                      <span className="break-words text-sm text-ink-3">{action.note}</span>
                    </span>
                    {action.kind !== "need_teacher" && (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={apply.isPending}
                        onClick={() => apply.mutate(action.key)}
                      >
                        {t("timetable.review.apply")}
                      </Button>
                    )}
                  </div>
                ))}
                {applied.length > 0 && (
                  <Banner tone="ok" className="mt-3">
                    {t("timetable.review.applied", { count: applied.length })}
                  </Banner>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
