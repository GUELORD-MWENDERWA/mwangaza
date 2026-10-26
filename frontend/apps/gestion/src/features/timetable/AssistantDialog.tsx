// « Dire mes consignes » (IA.2a, maquette `consignes-emploi-du-temps`) : le directeur des études
// écrit ses consignes en phrases, l'assistant les traduit en règles de la liste fermée, il coche
// celles à garder. Un clic = un appel ; rien n'est enregistré sans lui. Le serveur revérifie
// chaque règle comme une règle saisie à la main. Droits `timetable.manage` et `ai.use`.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogContent,
  DialogRoot,
  Field,
  StatusPill,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { uuidv7 } from "../../lib/ids";
import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { type Lookup, describe } from "./rules";

const TEXT_MAX = 2000;
const POLL_MS = 2000;

type Props = { lookup: Lookup; onClose: () => void };

export function AssistantDialog({ lookup, onClose }: Props) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const requestId = useRef(uuidv7());
  const [text, setText] = useState("");
  const [callId, setCallId] = useState<string | null>(null);
  const [unticked, setUnticked] = useState<Set<number>>(new Set());

  const ask = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/constraints/assist/", {
          body: { request_id: requestId.current, text },
        }),
      ),
    onSuccess: (started) => setCallId(started.id),
  });
  const reading = useQuery({
    enabled: callId !== null,
    queryKey: [...keys.timetable, "assist", callId],
    queryFn: () =>
      call(
        api.GET("/api/timetable/constraints/assist/{id}/", { params: { path: { id: callId! } } }),
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.state ?? "queued") ? POLL_MS : false,
  });
  const state = reading.data?.state;
  const proposals = reading.data?.proposals ?? [];
  const understood = proposals.flatMap((row, index) => (row.rule ? [{ row, index }] : []));
  const chosen = understood.filter(({ index }) => !unticked.has(index));

  const finish = async () => {
    await queryClient.invalidateQueries({ queryKey: keys.timetable });
    onClose();
  };
  const keep = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/constraints/assist/{id}/keep/", {
          params: { path: { id: callId! } },
          body: {
            items: chosen.map(({ row }) => ({ sentence: row.sentence, rule: row.rule! })),
          },
        }),
      ),
    onSuccess: finish,
  });
  const abandon = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/constraints/assist/{id}/abandon/", {
          params: { path: { id: callId! } },
        }),
      ),
    onSettled: finish,
  });
  // Fermer avec une réponse prête, sans l'enregistrer : elle est abandonnée (compte du mois).
  const close = () => (state === "done" ? abandon.mutate() : onClose());
  const toggle = (index: number) =>
    setUnticked((current) => {
      const next = new Set(current);
      if (!next.delete(index)) next.add(index);
      return next;
    });

  const waiting = ask.isPending || state === "queued" || state === "running";
  const failed = state === "error" || state === "refused";
  const error = ask.error ?? keep.error ?? abandon.error ?? reading.error;

  return (
    <DialogRoot open onOpenChange={(open) => !open && close()}>
      <DialogContent
        title={t("timetable.assistant.title")}
        description={t("timetable.assistant.subtitle")}
        className="w-[min(640px,calc(100vw-32px))]"
        footer={
          <>
            <Button variant="outline" className="mr-auto" onClick={close}>
              {t(state === "done" ? "timetable.assistant.abandon" : "common.cancel")}
            </Button>
            {state === "done" && (
              <Button
                disabled={keep.isPending || chosen.length === 0}
                onClick={() => keep.mutate()}
              >
                {t("timetable.assistant.keep", { count: chosen.length })}
              </Button>
            )}
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {error && <Banner tone="due">{firstErrorMessage(error, t)}</Banner>}
          <Field
            id="assistant-text"
            label={t("timetable.assistant.text")}
            help={t("timetable.assistant.textHelp")}
          >
            {(control) => (
              <Textarea
                {...control}
                rows={4}
                maxLength={TEXT_MAX}
                value={text}
                disabled={callId !== null}
                placeholder={t("timetable.assistant.placeholder")}
                onChange={(event) => setText(event.target.value)}
              />
            )}
          </Field>
          {callId === null && (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm text-ink-3">{t("timetable.assistant.cost")}</span>
              <Button disabled={waiting || text.trim().length === 0} onClick={() => ask.mutate()}>
                {t("timetable.assistant.translate")}
              </Button>
            </div>
          )}
          {callId !== null && waiting && (
            <p role="status" className="text-sm text-ink-2">
              {t("timetable.assistant.reading")}
            </p>
          )}
          {failed && <Banner tone="due">{t("timetable.assistant.failed")}</Banner>}
          {state === "done" && (
            <div className="flex flex-col border-t border-line-soft pt-3">
              <b className="mb-1 text-sm">
                {t("timetable.assistant.proposed", { count: understood.length })}
              </b>
              {proposals.map((row, index) => {
                if (!row.rule) return null;
                const { subject, text: line } = describe(row.rule, lookup, t, i18n.language);
                return (
                  <label
                    key={index}
                    className="flex cursor-pointer items-start gap-3 border-b border-line-soft py-3"
                  >
                    <input
                      type="checkbox"
                      className="mt-1 size-4"
                      checked={!unticked.has(index)}
                      onChange={() => toggle(index)}
                    />
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <b className="min-w-0 break-words">{subject}</b>
                        <StatusPill tone={row.rule.strength === "hard" ? "gray" : "info"}>
                          {row.rule.strength === "hard"
                            ? t("timetable.constraints.strength.hard")
                            : t("timetable.constraints.wish", { weight: row.rule.weight })}
                        </StatusPill>
                      </span>
                      <span className="text-sm text-ink-2">{line}</span>
                      <span className="break-words text-sm text-ink-3">« {row.sentence} »</span>
                    </span>
                  </label>
                );
              })}
              {proposals
                .filter((row) => !row.rule)
                .map((row, index) => (
                  <Banner key={index} tone="warn" className="mt-3">
                    <b>{t("timetable.assistant.notUnderstood")}</b> · « {row.sentence} » —{" "}
                    {row.reason}
                  </Banner>
                ))}
              {proposals.length === 0 && (
                <p className="text-sm text-ink-2">{t("timetable.assistant.nothing")}</p>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
