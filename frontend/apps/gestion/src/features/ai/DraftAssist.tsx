// Brouillon IA (IA.4, maquette `brouillon-ia`) : une phrase, un ton → un titre et un texte dans le
// panneau ; la personne les met dans l'éditeur (« Remplacer » ou « Ajouter à la fin »), les
// relit et publie par le bouton habituel. L'IA ne reçoit ni nom d'élève ni donnée de famille.
// Droits `announcements.publish` (écran hôte) et `ai.use`, usage `drafting`.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Field, Segmented, Textarea } from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { AiButton } from "./AiButton";
import { useAiCall } from "./useAiCall";

type Kind = Schemas["DraftKindEnum"];
type Tone = "formal" | "simple";
export type Draft = { title: string; body: string };

/** Le module IA est donné à l'école et la personne a le droit `ai.use` (sinon le bouton est caché). */
export function useCanDraft(): boolean {
  const me = useCurrentMe();
  return Boolean(me.school?.modules.includes("ai")) && can(me, ["ai.use"]);
}

export function DraftButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <AiButton use="drafting" onClick={onClick}>
      {t("ai.draft.open")}
    </AiButton>
  );
}

type Props = {
  kinds: Kind[];
  /** « replace » : le brouillon prend la place du texte ; « append » : il s'ajoute à la fin. */
  onUse: (draft: Draft, mode: "replace" | "append") => void;
  onClose: () => void;
};

export function DraftPanel({ kinds, onUse, onClose }: Props) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<Kind>(kinds[0]!);
  const [tone, setTone] = useState<Tone>("formal");
  const [brief, setBrief] = useState("");
  const flow = useAiCall({
    name: "draft",
    start: (request_id) =>
      call(api.POST("/api/ai/drafts/", { body: { request_id, kind, tone, brief } })),
    read: (id) => call(api.GET("/api/ai/drafts/{id}/", { params: { path: { id } } })),
    settle: (id, kept) =>
      call(api.POST("/api/ai/drafts/{id}/", { params: { path: { id } }, body: { kept } })),
  });
  const draft = flow.data?.draft;
  const done = flow.state === "done" && draft;

  const finish = (kept: boolean, mode?: "replace" | "append") => {
    if (kept && draft && mode) onUse(draft, mode);
    flow.closing.mutate(kept, { onSettled: onClose });
  };
  const error = flow.ask.error ?? flow.reading.error ?? flow.closing.error;

  return (
    <div
      className="flex flex-col gap-3 rounded-field border border-line-soft bg-surface p-4"
      data-testid="draft-panel"
    >
      <b>{t("ai.draft.title")}</b>
      {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
      {flow.failed && <Banner tone="due">{t("ai.draft.failed")}</Banner>}
      {!done && (
        <>
          {kinds.length > 1 && (
            <Segmented
              value={kind}
              onValueChange={setKind}
              label={t("ai.draft.kind")}
              options={kinds.map((value) => ({ value, label: t(`ai.draft.kinds.${value}`) }))}
            />
          )}
          <Segmented
            value={tone}
            onValueChange={setTone}
            label={t("ai.draft.tone")}
            options={(["formal", "simple"] as const).map((value) => ({
              value,
              label: t(`ai.draft.tones.${value}`),
            }))}
          />
          <Field id="draft-brief" label={t("ai.draft.brief")} help={t("ai.draft.briefHelp")}>
            {(control) => (
              <Textarea
                {...control}
                rows={3}
                maxLength={600}
                value={brief}
                disabled={flow.id !== null && !flow.failed}
                placeholder={t("ai.draft.placeholder")}
                onChange={(event) => setBrief(event.target.value)}
              />
            )}
          </Field>
          {flow.waiting && (
            <p role="status" className="text-sm text-ink-2">
              {t("ai.draft.writing")}
            </p>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-ink-3">{t("ai.draft.cost")}</span>
            <span className="flex gap-2">
              <Button variant="outline" onClick={onClose}>
                {t("common.cancel")}
              </Button>
              <Button
                disabled={flow.waiting || brief.trim().length === 0}
                onClick={() => {
                  if (flow.failed) flow.reset();
                  flow.ask.mutate();
                }}
              >
                {t("ai.draft.write")}
              </Button>
            </span>
          </div>
        </>
      )}
      {done && (
        <>
          <span className="text-sm text-ink-3">{t("ai.draft.proposed")}</span>
          <b className="break-words text-base">{draft.title}</b>
          <p className="whitespace-pre-line break-words text-ink-2">{draft.body}</p>
          <div className="flex flex-wrap gap-2">
            <Button disabled={flow.closing.isPending} onClick={() => finish(true, "replace")}>
              {t("ai.draft.replace")}
            </Button>
            <Button
              variant="outline"
              disabled={flow.closing.isPending}
              onClick={() => finish(true, "append")}
            >
              {t("ai.draft.append")}
            </Button>
            <Button variant="ghost" disabled={flow.closing.isPending} onClick={() => finish(false)}>
              {t("ai.draft.abandon")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
