// Messages des parents (8.8, maquette `messages-parents`) : un fil par élève, ouvert à droite ;
// répondre prévient le parent sur son téléphone. Droit `announcements.publish`.
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  PageHeader,
  Skeleton,
  StatusPill,
  Textarea,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { useReply, useThread, useThreads } from "./data";

export function ParentMessagesPage() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useThreads(page);
  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const items = list.data?.results ?? [];
  const current = selected ?? items[0]?.id ?? null;
  return (
    <>
      <PageHeader title={t("parentMessages.title")} subtitle={t("parentMessages.subtitle")} />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          {!list.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : items.length === 0 ? (
            <CardContent className="text-ink-3">{t("parentMessages.empty")}</CardContent>
          ) : (
            <ul className="divide-y divide-line">
              {items.map((thread) => (
                <li key={thread.id}>
                  <button
                    type="button"
                    aria-current={thread.id === current}
                    onClick={() => setSelected(thread.id)}
                    className="flex min-h-11 w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-surface aria-[current=true]:bg-surface"
                  >
                    <span className="min-w-0">
                      <b className="block truncate">{thread.student_name}</b>
                      <span className="text-sm text-ink-3 tabular-nums">
                        {formatDay(thread.last_message_at.slice(0, 10), i18n.language)}
                      </span>
                    </span>
                    {thread.unread && (
                      <StatusPill tone="warn">{t("parentMessages.new")}</StatusPill>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
            summary={t("parentMessages.count", { count: list.data?.count ?? 0 })}
          />
        </Card>
        {current ? (
          <ThreadView key={current} id={current} />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("parentMessages.pick")}</CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function ThreadView({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const thread = useThread(id);
  const reply = useReply(id);
  const [body, setBody] = useState("");
  const data = thread.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{data?.student_name ?? ""}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!data && <Skeleton label={t("common.loading")} />}
        <ul className="flex flex-col gap-2.5">
          {data?.messages.map((message) => (
            <li
              key={message.id}
              className={
                message.from_school
                  ? "rounded-field bg-surface p-3 text-sm"
                  : "rounded-field border border-line p-3 text-sm"
              }
            >
              <span className="block text-xs text-ink-3">
                <b>{message.author_name}</b> ·{" "}
                {formatDay(message.created_at.slice(0, 10), i18n.language)}
                {message.topic && ` · ${t(`parentMessages.topics.${message.topic}`)}`}
              </span>
              <span className="whitespace-pre-line">{message.body}</span>
            </li>
          ))}
        </ul>
        {reply.isError && <Banner tone="due">{errorMessage(reply.error, t)}</Banner>}
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            reply.mutate(body.trim(), { onSuccess: () => setBody("") });
          }}
        >
          <Field id="reply-body" label={t("parentMessages.reply")}>
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
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={reply.isPending || !body.trim()}>
              {t("parentMessages.send")}
            </Button>
            <Link to="../waivers" className="inline-flex">
              <Button type="button" variant="outline">
                {t("parentMessages.grantWaiver")}
              </Button>
            </Link>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
