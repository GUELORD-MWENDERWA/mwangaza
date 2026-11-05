// Demandes d'aide des écoles (SUP.1, maquettes `console/demandes-aide` et `console/demande-aide`) :
// la file par état (« À traiter » d'abord, la plus ancienne attente en tête), recherche, « les
// miennes », puis la fiche : le fil, la réponse, le responsable et le contexte joint d'office.
// Droit `platform.support.handle` ; le serveur filtre selon le mode (réel / démonstration).
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, formatPhone, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Textarea,
  buttonVariants,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";

type Item = Schemas["ConsoleSupportRequest"];
type State = "todo" | "waiting" | "closed";
const STATES: State[] = ["todo", "waiting", "closed"];
const TONES = { open: "warn", answered: "info", closed: "gray" } as const;
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

function useCounts(enabled = true) {
  return useQuery({
    queryKey: [...keys.support, "counts"],
    enabled,
    queryFn: () => call(api.GET("/api/console/support/counts/")),
    refetchInterval: 60_000,
  });
}

/** Nombre de demandes à traiter, pour le menu. */
export function useTodoCount(enabled: boolean): number {
  return useCounts(enabled).data?.todo ?? 0;
}

function StatusBadge({ status }: { status: Item["status"] }) {
  const { t } = useTranslation();
  return <StatusPill tone={TONES[status]}>{t(`console.support.status.${status}`)}</StatusPill>;
}

export function SupportPage() {
  const { id } = useParams();
  return id ? <SupportDetail id={id} /> : <SupportList />;
}

function SupportList() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<State>("todo");
  const [mine, setMine] = useState(false);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const counts = useCounts();
  const list = useQuery({
    queryKey: [...keys.support, "list", { state, mine, search, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/support/", {
          params: {
            query: { state, mine: mine || undefined, q: search.trim() || undefined, page },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  return (
    <>
      <PageHeader title={t("console.support.title")} subtitle={t("console.support.subtitle")} />
      <div className="max-w-full overflow-x-auto">
        <Segmented
          label={t("console.support.state")}
          className="w-max whitespace-nowrap"
          value={state}
          onValueChange={(value) => {
            setState(value);
            setPage(1);
          }}
          options={STATES.map((value) => ({
            value,
            label: t(`console.support.states.${value}`, { count: counts.data?.[value] ?? 0 }),
          }))}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label={t("console.support.search")}
          placeholder={t("console.support.search")}
          className="max-w-xs"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={mine}
            onChange={(event) => {
              setMine(event.target.checked);
              setPage(1);
            }}
          />
          {t("console.support.mine")}
        </label>
      </div>
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : list.isError ? (
        <>
          <Banner tone="due">{errorMessage(list.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void list.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : list.data.results.length === 0 ? (
        <Card className="px-6 py-6 text-center">
          <p className="font-bold">{t("console.support.none")}</p>
        </Card>
      ) : (
        <Card>
          <ul>
            {list.data.results.map((item) => (
              <li key={item.id} className="border-t border-line first:border-t-0">
                <Link
                  to={`/support/${item.id}`}
                  className="flex flex-col gap-1 px-4 py-3 hover:bg-surface"
                >
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <b className="min-w-0 break-words">
                      {t("console.support.number", { number: item.number })} · {item.subject}
                    </b>
                    <StatusBadge status={item.status} />
                  </span>
                  <span className="text-sm text-ink-3">
                    {item.school_name} · {item.author_name}
                    {item.screen && ` · ${item.screen}`} ·{" "}
                    {formatDateTime(item.last_activity_at, i18n.language, timeZone)}
                    {item.assignee_name && ` · ${item.assignee_name}`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="flex items-center justify-between px-4 py-2.5 text-sm text-ink-3">
            {t("console.support.count", { count: list.data.count })}
          </div>
          <Pager page={page} onPage={setPage} previous={list.data.previous} next={list.data.next} />
        </Card>
      )}
    </>
  );
}

function SupportDetail({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const item = useQuery({
    queryKey: [...keys.support, "one", id],
    queryFn: () => call(api.GET("/api/console/support/{id}/", { params: { path: { id } } })),
  });
  const assignees = useQuery({
    queryKey: [...keys.support, "assignees"],
    queryFn: () => call(api.GET("/api/console/support/assignees/")),
    staleTime: 5 * 60_000,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.support });
  const reply = useMutation({
    mutationFn: (text: string) =>
      call(
        api.POST("/api/console/support/{id}/reply/", {
          params: { path: { id } },
          body: { body: text },
        }),
      ),
    onSuccess: () => {
      setBody("");
      void refresh();
    },
  });
  const close = useMutation({
    mutationFn: () =>
      call(api.POST("/api/console/support/{id}/close/", { params: { path: { id } } })),
    onSuccess: refresh,
  });
  const assign = useMutation({
    mutationFn: (assignee: string | null) =>
      call(
        api.POST("/api/console/support/{id}/assign/", {
          params: { path: { id } },
          body: { assignee },
        }),
      ),
    onSuccess: refresh,
  });
  if (item.isPending) return <Skeleton label={t("common.loading")} />;
  if (item.isError) {
    return (
      <>
        <Banner tone="due">{errorMessage(item.error, t)}</Banner>
        <Link to="/support" className={buttonVariants({ variant: "outline" })}>
          {t("console.support.back")}
        </Link>
      </>
    );
  }
  const data = item.data;
  const failure = reply.error ?? close.error ?? assign.error;
  return (
    <>
      <PageHeader
        title={data.subject}
        subtitle={`${t("console.support.number", { number: data.number })} · ${formatDateTime(data.created_at, i18n.language, timeZone)} · ${data.school_name}`}
        actions={
          <Link to="/support" className={buttonVariants({ variant: "outline" })}>
            {t("console.support.back")}
          </Link>
        }
      />
      {failure && <Banner tone="due">{errorMessage(failure, t)}</Banner>}
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="flex flex-col gap-3 p-4">
          <ol className="flex flex-col gap-2.5">
            {data.replies.map((message) => (
              <li
                key={message.id}
                className={`rounded-xl border px-3.5 py-2.5 ${message.from_platform ? "border-lake bg-lake-50" : "border-line bg-surface"}`}
              >
                <p className="text-sm text-ink-3">
                  <b className="text-ink">{message.author_name}</b>
                  {message.from_platform && ` ${t("console.support.team")}`} ·{" "}
                  {formatDateTime(message.created_at, i18n.language, timeZone)}
                </p>
                <p className="mt-1 whitespace-pre-line break-words">{message.body}</p>
              </li>
            ))}
          </ol>
          <form
            className="flex flex-col gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (body.trim()) reply.mutate(body.trim());
            }}
          >
            <Textarea
              aria-label={t("console.support.replyLabel")}
              rows={4}
              maxLength={5000}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder={t("console.support.replyPlaceholder")}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              {data.status !== "closed" ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={close.isPending}
                  onClick={() => close.mutate()}
                >
                  {t("console.support.close")}
                </Button>
              ) : (
                <span className="text-sm text-ink-3">{t("console.support.reopenHint")}</span>
              )}
              <Button type="submit" disabled={reply.isPending || !body.trim()}>
                {t("console.support.send")}
              </Button>
            </div>
          </form>
        </Card>
        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3 p-4">
            <h2 className="font-bold">{t("console.support.follow")}</h2>
            <p className="flex items-center justify-between text-sm">
              {t("console.support.state")} <StatusBadge status={data.status} />
            </p>
            <Field id="support-assignee" label={t("console.support.assignee")}>
              {(control) => (
                <Select
                  {...control}
                  value={data.assignee ?? ""}
                  disabled={assign.isPending}
                  onChange={(event) => assign.mutate(event.target.value || null)}
                >
                  <option value="">{t("console.support.nobody")}</option>
                  {(assignees.data ?? []).map((member) => (
                    <option key={member.id} value={member.id}>
                      {member.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </Card>
          <Card className="flex flex-col gap-1 p-4 text-sm">
            <h2 className="font-bold">{t("console.support.author")}</h2>
            <p>{data.author_name}</p>
            <p className="text-ink-3">{formatPhone(data.phone)}</p>
            <p className="text-ink-3">
              {data.school_name} ({data.school})
            </p>
          </Card>
          <Card className="flex flex-col gap-1 p-4 text-sm">
            <h2 className="font-bold">{t("console.support.context")}</h2>
            <p>{t("console.support.screen", { screen: data.screen || "—" })}</p>
            <p>{t("console.support.version", { version: data.app_version || "—" })}</p>
            <p>{t("console.support.device", { device: data.device || "—" })}</p>
            <Link
              to={`/schools/${data.school_id}`}
              className={buttonVariants({ variant: "outline", className: "mt-2 w-fit" })}
            >
              {t("console.support.openSchool")}
            </Link>
          </Card>
        </div>
      </div>
    </>
  );
}
