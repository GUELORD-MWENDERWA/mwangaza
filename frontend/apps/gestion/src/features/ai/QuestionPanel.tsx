// « Poser une question » (IA.3, maquette `assistant-questions`) : bouton de la barre du haut, panneau
// à droite. L'IA ne reçoit que la phrase (et 3 questions d'avant) : elle la traduit en une requête
// d'une liste fermée ; l'application calcule avec les droits de la personne et donne chiffres +
// lien vers l'écran. La conversation reste dans cet onglet du navigateur. Droit `ai.use`, usage
// `assistant`.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Banner,
  Button,
  Icon,
  Input,
  PanelContent,
  Sheet,
  SheetClose,
  SheetTrigger,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { uuidv7 } from "../../lib/ids";
import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useAiBlocked } from "./AiButton";

type Answer = NonNullable<Schemas["QuestionCall"]["answer"]>;
type Line =
  | { id: string; kind: "question"; text: string }
  | { id: string; kind: "answer"; answer: Answer; at: Date };

const POLL_MS = 2000;
const WAIT_MAX = 30;
const SUGGESTIONS = ["collected", "headcount", "teacher_load"] as const;

async function ask(question: string, history: string[]): Promise<Answer> {
  const started = await call(
    api.POST("/api/ai/questions/", { body: { request_id: uuidv7(), question, history } }),
  );
  for (let attempt = 0; attempt < WAIT_MAX; attempt += 1) {
    const read = await call(
      api.GET("/api/ai/questions/{id}/", { params: { path: { id: started.id } } }),
    );
    if (read.answer) return read.answer;
    if (!["queued", "running", "done"].includes(read.state)) {
      throw new Error(read.refusal || read.state);
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  throw new Error("timeout");
}

/** Bouton « Question » : caché sans le module IA ou le droit `ai.use`. */
export function QuestionButton() {
  const me = useCurrentMe();
  if (!me.school?.modules.includes("ai") || !can(me, ["ai.use"])) return null;
  return <QuestionSheet />;
}

function QuestionSheet() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const blocked = useAiBlocked("assistant");
  const money = (minor: number, currency: string) => formatAmount(minor, currency as Currency);

  const send = useMutation({
    mutationFn: (question: string) =>
      ask(
        question,
        lines.flatMap((line) => (line.kind === "question" ? [line.text] : [])).slice(-3),
      ),
    onSuccess: (answer) =>
      setLines((current) => [...current, { id: uuidv7(), kind: "answer", answer, at: new Date() }]),
  });
  useEffect(() => end.current?.scrollIntoView?.({ block: "end" }), [lines, send.isPending]);

  const submit = (question: string) => {
    const clean = question.trim();
    if (!clean || send.isPending || blocked) return;
    setLines((current) => [...current, { id: uuidv7(), kind: "question", text: clean }]);
    setText("");
    send.mutate(clean);
  };

  const amounts = (figures: NonNullable<Answer["figures"]>) =>
    (figures.amounts ?? []).map((item) => money(item.amount_minor, item.currency)).join(" + ") ||
    money(0, "USD");

  const body = (answer: Answer) => {
    const figures = answer.figures;
    if (answer.status !== "answered" || !figures) {
      return (
        <Banner tone="warn">
          {t(
            `ai.assistant.status.${answer.status === "answered" ? "not_available" : answer.status}`,
          )}
        </Banner>
      );
    }
    const scope = figures.class_group ? ` · ${figures.class_group}` : "";
    const rows = figures.rows ?? [];
    return (
      <div className="flex flex-col gap-3 text-sm">
        {answer.intent === "unpaid" && (
          <p>
            {t("ai.assistant.unpaid", { count: figures.count, amounts: amounts(figures), scope })}
          </p>
        )}
        {answer.intent === "collected" && (
          <p>
            {t("ai.assistant.collected", {
              amounts: amounts(figures),
              count: figures.count,
              period: t(`ai.assistant.periods.${(figures.period ?? "this_week") as "this_week"}`),
              scope,
            })}
          </p>
        )}
        {answer.intent === "headcount" && (
          <p>
            {t("ai.assistant.headcount", {
              count: figures.count,
              girls: figures.girls,
              boys: figures.boys,
              scope,
            })}
          </p>
        )}
        {answer.intent === "teacher_load" && (
          <ul className="flex flex-col divide-y divide-line-soft">
            {rows.map((row) => (
              <li key={row.name} className="flex flex-wrap justify-between gap-2 py-1.5">
                <b>{row.name}</b>
                <span className="text-ink-3 tabular-nums">
                  {t("ai.assistant.load", { hours: row.hours, courses: row.courses })}
                </span>
              </li>
            ))}
            {rows.length === 0 && <li className="py-1.5">{t("ai.assistant.noLoad")}</li>}
          </ul>
        )}
        <Button asChild variant="outline" size="sm" className="self-start">
          <Link to={figures.link} onClick={() => setOpen(false)}>
            {t("ai.assistant.see")}
          </Link>
        </Button>
      </div>
    );
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="max-[899px]:px-[9px]">
          <Icon name="sparkle" size={16} />
          <span className="max-[599px]:sr-only">{t("ai.assistant.open")}</span>
        </Button>
      </SheetTrigger>
      <PanelContent title={t("ai.assistant.title")}>
        <div className="flex items-center justify-between gap-3 border-b border-line-soft px-5 py-4">
          <b className="flex items-center gap-2 text-base">
            <Icon name="sparkle" size={18} />
            {t("ai.assistant.title")}
          </b>
          <SheetClose asChild>
            <Button variant="ghost" size="sm" aria-label={t("common.close")}>
              ✕
            </Button>
          </SheetClose>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 py-4">
          <p className="text-sm text-ink-2">{t("ai.assistant.intro")}</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((key) => (
              <Button
                key={key}
                variant="outline"
                size="sm"
                disabled={Boolean(blocked) || send.isPending}
                onClick={() => submit(t(`ai.assistant.suggestions.${key}`))}
              >
                {t(`ai.assistant.suggestions.${key}`)}
              </Button>
            ))}
          </div>
          {lines.map((line) =>
            line.kind === "question" ? (
              <p
                key={line.id}
                className="max-w-[85%] self-end rounded-card bg-lake-50 px-4 py-2.5 text-sm break-words"
              >
                {line.text}
              </p>
            ) : (
              <div key={line.id} className="rounded-card border border-line-soft p-4">
                <span className="mb-2 block text-xs text-ink-3">
                  <b className="text-ink">{t("ai.assistant.answer")}</b> ·{" "}
                  {t("ai.assistant.computed", {
                    time: new Intl.DateTimeFormat(i18n.language, {
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(line.at),
                  })}
                </span>
                {body(line.answer)}
              </div>
            ),
          )}
          {send.isPending && (
            <p role="status" className="text-sm text-ink-2">
              {t("ai.assistant.thinking")}
            </p>
          )}
          {send.isError && <Banner tone="due">{errorMessage(send.error, t)}</Banner>}
          <div ref={end} />
        </div>
        <form
          className="flex flex-col gap-2 border-t border-line-soft px-5 py-4"
          onSubmit={(event) => {
            event.preventDefault();
            submit(text);
          }}
        >
          <Input
            aria-label={t("ai.assistant.placeholder")}
            placeholder={t("ai.assistant.placeholder")}
            maxLength={300}
            value={text}
            disabled={Boolean(blocked)}
            onChange={(event) => setText(event.target.value)}
          />
          <span className="text-xs text-ink-3">{blocked || t("ai.assistant.cost")}</span>
          <Button
            type="submit"
            className="self-start"
            disabled={Boolean(blocked) || send.isPending || text.trim().length === 0}
          >
            {t("ai.assistant.ask")}
          </Button>
        </form>
      </PanelContent>
    </Sheet>
  );
}
