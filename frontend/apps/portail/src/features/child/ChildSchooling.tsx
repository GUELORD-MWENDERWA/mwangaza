import { api, call } from "@mwangaza/api";
import { errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Select,
  StatusPill,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { reportCardUrl, useChildResults, useChildThread } from "../../lib/families";

const TOPICS = ["waiver", "grade", "other"] as const;

/** Notes validées par période, décision de passage et bulletin PDF (maquette `enfant-bulletin`).
 *  Frais échus sans dérogation : le PDF est retenu, notes et décision restent visibles. */
export function ChildResults({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const results = useChildResults(id);
  const data = results.data;
  if (!data) return null;
  const terms = data.terms.filter((term) => term.courses.length > 0);
  if (terms.length === 0 && !data.decision) return null;
  return (
    <>
      {data.withheld && <Banner tone="info">{t("portal.child.reportWithheld")}</Banner>}
      {terms.map((term) => (
        <Card key={term.id}>
          <CardHeader className="flex items-center justify-between gap-2">
            <CardTitle>{t("portal.child.gradesTitle", { term: term.name })}</CardTitle>
            {term.released && <StatusPill tone="ok">{t("portal.child.released")}</StatusPill>}
          </CardHeader>
          <CardContent className="py-1">
            <ul className="divide-y divide-line">
              {term.courses.map((line) => (
                <li key={line.course} className="flex justify-between gap-3 py-2.5">
                  <span>{line.course}</span>
                  <b className="tabular-nums">
                    {line.score === null ? "—" : `${line.score} / ${line.maximum}`}
                  </b>
                </li>
              ))}
              {term.total !== null && (
                <li className="flex justify-between gap-3 py-2.5">
                  <b>{t("portal.child.total")}</b>
                  <b className="tabular-nums">
                    {term.total} / {term.maximum}
                  </b>
                </li>
              )}
            </ul>
          </CardContent>
        </Card>
      ))}
      {data.decision && (
        <Card>
          <CardHeader className="flex items-center justify-between gap-2">
            <CardTitle>{t("portal.child.decisionTitle")}</CardTitle>
            <StatusPill tone={data.decision.decision === "pass" ? "ok" : "warn"}>
              {t(`deliberation.decision_${data.decision.decision}`, data.decision.decision)}
            </StatusPill>
          </CardHeader>
          <CardContent className="text-sm text-ink-3">
            {t("portal.child.decisionOn", {
              date: formatDay(data.decision.held_on, i18n.language),
            })}
            {data.decision.resit_courses.length > 0 &&
              ` · ${t("portal.child.resitCourses", { courses: data.decision.resit_courses.join(", ") })}`}
          </CardContent>
        </Card>
      )}
      {data.report_available && (
        <Card>
          <CardContent className="flex items-center justify-between gap-3 py-3.5">
            <b>{t("portal.child.reportCard")}</b>
            <a
              href={reportCardUrl(id)}
              target="_blank"
              rel="noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <Icon name="download" size={16} />
              {t("portal.child.pdf")}
            </a>
          </CardContent>
        </Card>
      )}
    </>
  );
}

/** Écrire à l'école (8.8) : le fil de l'enfant, une question ou une demande de dérogation. */
export function ChildThread({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const thread = useChildThread(id);
  const [body, setBody] = useState("");
  const [topic, setTopic] = useState<(typeof TOPICS)[number]>("other");
  const key = ["portal", "child", id, "thread"];
  const send = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/portal/children/{id}/thread/", {
          params: { path: { id } },
          body: { body: body.trim(), topic },
        }),
      ),
    onSuccess: (data) => {
      client.setQueryData(key, data);
      setBody("");
    },
  });
  const read = useMutation({
    mutationFn: () =>
      call(api.POST("/api/portal/children/{id}/thread/read/", { params: { path: { id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
  const unread = thread.data?.unread ?? false;
  // Les réponses affichées sont lues : l'école n'est plus invitée à relancer.
  useEffect(() => {
    if (unread && !read.isPending) read.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unread]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("portal.child.threadTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {thread.data && thread.data.messages.length > 0 && (
          <ul className="flex flex-col gap-2.5">
            {thread.data.messages.map((message) => (
              <li
                key={message.id}
                className={
                  message.from_school
                    ? "rounded-field bg-surface p-3 text-sm"
                    : "rounded-field border border-line p-3 text-sm"
                }
              >
                <span className="block text-xs text-ink-3">
                  <b>
                    {message.from_school ? t("portal.child.fromSchool") : t("portal.child.you")}
                  </b>{" "}
                  · {formatDay(message.created_at.slice(0, 10), i18n.language)}
                  {message.topic &&
                    ` · ${t(`portal.child.topics.${message.topic as (typeof TOPICS)[number]}`)}`}
                </span>
                <span className="whitespace-pre-line">{message.body}</span>
              </li>
            ))}
          </ul>
        )}
        {send.isError && <Banner tone="due">{errorMessage(send.error, t)}</Banner>}
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (body.trim()) send.mutate();
          }}
        >
          <Field id="thread-topic" label={t("portal.child.topic")}>
            {(control) => (
              <Select
                {...control}
                value={topic}
                onChange={(event) => setTopic(event.target.value as (typeof TOPICS)[number])}
              >
                {TOPICS.map((value) => (
                  <option key={value} value={value}>
                    {t(`portal.child.topics.${value}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="thread-body" label={t("portal.child.message")}>
            {(control) => (
              <Textarea
                {...control}
                maxLength={1500}
                className="min-h-24"
                value={body}
                onChange={(event) => setBody(event.target.value)}
              />
            )}
          </Field>
          <Button type="submit" disabled={send.isPending || !body.trim()}>
            {t("portal.child.send")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
