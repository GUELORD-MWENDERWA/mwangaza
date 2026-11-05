// « Mes demandes d'aide » (SUP.1, maquette `gestion/aide-mes-demandes`) : la liste de mes demandes
// à la plateforme (activité la plus récente d'abord) et le fil de la demande ouverte. Sous 900 px :
// la liste, puis le fil sur sa propre page. Texte simple, retours à la ligne gardés.
import { errorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  PageHeader,
  Skeleton,
  StatusPill,
  Textarea,
  usePlatform,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { useOnline } from "../../lib/online";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  PAGE_SIZE,
  useCloseRequest,
  useReplyRequest,
  useRequest,
  useRequests,
  type SupportStatus,
} from "./data";
import { SupportDialog } from "./SupportDialog";

const TONES = { open: "info", answered: "warn", closed: "gray" } as const;

function State({ status }: { status: SupportStatus }) {
  const { t } = useTranslation();
  return <StatusPill tone={TONES[status]}>{t(`helpRequests.status.${status}`)}</StatusPill>;
}

export function SupportRequestsPage() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const school = useCurrentSchool();
  const platform = usePlatform().name;
  const [page, setPage] = useState(1);
  const [writing, setWriting] = useState(false);
  const list = useRequests(page);
  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader
        title={t("helpRequests.title")}
        subtitle={t("helpRequests.subtitle", { platform })}
        actions={<Button onClick={() => setWriting(true)}>{t("helpRequests.write")}</Button>}
      />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <Card className={id ? "hidden lg:block" : undefined}>
          {!list.data ? (
            <Skeleton label={t("common.loading")} />
          ) : results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("helpRequests.empty")}</p>
          ) : (
            <ul>
              {results.map((request) => (
                <li key={request.id} className="border-t border-line first:border-t-0">
                  <Link
                    to={`/help/requests/${request.id}`}
                    className={`flex flex-col gap-1 px-4 py-3 hover:bg-surface ${request.id === id ? "bg-lake-50" : ""}`}
                  >
                    <span className="flex flex-wrap items-center justify-between gap-2">
                      <b className="min-w-0 break-words">{request.subject}</b>
                      <State status={request.status} />
                    </span>
                    <span className="text-sm text-ink-3">
                      {t("helpRequests.number", { number: request.number })} ·{" "}
                      {formatDateTime(request.last_activity_at, i18n.language, school.timezone)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {count > PAGE_SIZE && (
            <Pagination
              page={page}
              hasPrevious={Boolean(list.data?.previous)}
              hasNext={Boolean(list.data?.next)}
              onPage={setPage}
              summary={t("helpRequests.range", { from, to: from + results.length - 1, count })}
            />
          )}
        </Card>
        {id ? (
          <Thread id={id} />
        ) : (
          <p className="hidden rounded-xl border border-dashed border-line px-4 py-8 text-center text-ink-3 lg:block">
            {t("helpRequests.pick")}
          </p>
        )}
      </div>
      <SupportDialog open={writing} onClose={() => setWriting(false)} />
    </>
  );
}

function Thread({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const online = useOnline();
  const request = useRequest(id);
  const reply = useReplyRequest(id);
  const close = useCloseRequest(id);
  const [body, setBody] = useState("");
  const [now] = useState(() => Date.now());
  if (request.isError) {
    return <LoadError error={request.error} onRetry={() => void request.refetch()} />;
  }
  const data = request.data;
  if (!data) return <Skeleton label={t("common.loading")} />;
  const closedForGood =
    data.status === "closed" &&
    data.closed_at !== null &&
    now - new Date(data.closed_at).getTime() > 30 * 24 * 3600 * 1000;
  return (
    <Card className="flex flex-col gap-3 p-4">
      <Link to="/help/requests" className="text-sm font-semibold text-lake lg:hidden">
        ← {t("helpRequests.back")}
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="break-words text-lg font-bold">{data.subject}</h2>
          <p className="text-sm text-ink-3">
            {t("helpRequests.number", { number: data.number })}
            {data.screen && ` · ${data.screen}`} ·{" "}
            {formatDateTime(data.created_at, i18n.language, school.timezone)}
          </p>
        </div>
        <State status={data.status} />
      </div>
      <ol className="flex flex-col gap-2.5">
        {data.replies.map((message) => (
          <li
            key={message.id}
            className={`rounded-xl border px-3.5 py-2.5 ${message.from_platform ? "border-lake bg-lake-50" : "border-line bg-surface"}`}
          >
            <p className="text-sm text-ink-3">
              <b className="text-ink">
                {message.from_platform
                  ? t("helpRequests.fromPlatform", { name: message.author_name })
                  : t("helpRequests.you")}
              </b>{" "}
              · {formatDateTime(message.created_at, i18n.language, school.timezone)}
            </p>
            <p className="mt-1 whitespace-pre-line break-words">{message.body}</p>
          </li>
        ))}
      </ol>
      {closedForGood ? (
        <Banner tone="info">{t("helpRequests.closedForGood")}</Banner>
      ) : (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!body.trim()) return;
            reply.mutate(body.trim(), { onSuccess: () => setBody("") });
          }}
        >
          {(reply.isError || close.isError) && (
            <Banner tone="due">{errorMessage(reply.error ?? close.error, t)}</Banner>
          )}
          <Textarea
            aria-label={t("helpRequests.replyLabel")}
            rows={3}
            maxLength={5000}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder={t("helpRequests.replyPlaceholder")}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            {data.status !== "closed" ? (
              <button
                type="button"
                disabled={!online || close.isPending}
                onClick={() => close.mutate()}
                className="cursor-pointer text-sm font-semibold text-lake disabled:opacity-50"
              >
                {t("helpRequests.solved")}
              </button>
            ) : (
              <span className="text-sm text-ink-3">{t("helpRequests.reopenHint")}</span>
            )}
            <Button type="submit" disabled={!online || reply.isPending || !body.trim()}>
              {t("helpRequests.send")}
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
