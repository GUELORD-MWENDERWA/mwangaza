// Demandes de démonstration et messages du chat envoyés par le site public (WEB.1d, maquette
// `console/demandes` et `site/chat`) :
// filtrées par suivi (« Nouvelles » d'abord, avec leur nombre), suivi et note interne, « Effacer »
// après confirmation quand la personne le demande. Le serveur efface seul après un an.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, formatPhone, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  Field,
  Icon,
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
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";

type DemoRequest = Schemas["ConsoleDemoRequest"];
type Status = Schemas["DemoRequestStatusEnum"];
const STATUSES: Status[] = ["new", "called", "trial", "dropped"];
const FILTERS = [...STATUSES, "all"] as const;
type Filter = (typeof FILTERS)[number];
const TONES = { new: "info", called: "warn", trial: "ok", dropped: "gray" } as const;

function useRequests(filter: Filter, page: number) {
  return useQuery({
    queryKey: [...keys.demoRequests, { filter, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/demo-requests/", {
          params: { query: { status: filter === "all" ? undefined : filter, page } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function DemoRequestsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("new");
  const [page, setPage] = useState(1);
  const [erase, setErase] = useState<DemoRequest | null>(null);
  const requests = useRequests(filter, page);
  // Nombre de nouvelles, montré sur le premier filtre (même requête que ce filtre, gardée en cache).
  const fresh = useRequests("new", 1);
  const remove = useMutation({
    mutationFn: (request: DemoRequest) =>
      call(
        api.DELETE("/api/console/demo-requests/{id}/", {
          params: { path: { id: request.id } },
        }),
      ),
    onSuccess: () => {
      setErase(null);
      void queryClient.invalidateQueries({ queryKey: keys.demoRequests });
    },
  });
  const newCount = fresh.data?.count ?? 0;

  return (
    <>
      <PageHeader
        title={t("console.demoRequests.title")}
        subtitle={t("console.demoRequests.subtitle")}
      />
      <div className="max-w-full overflow-x-auto">
        <Segmented
          label={t("console.demoRequests.filter")}
          className="w-max whitespace-nowrap"
          value={filter}
          onValueChange={(value) => {
            setFilter(value);
            setPage(1);
          }}
          options={FILTERS.map((value) => ({
            value,
            label:
              value === "new" && newCount
                ? t("console.demoRequests.newCount", { count: newCount })
                : t(`console.demoRequests.filters.${value}`),
          }))}
        />
      </div>
      {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      {requests.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : requests.isError ? (
        <>
          <Banner tone="due">{errorMessage(requests.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void requests.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : requests.data.results.length === 0 ? (
        <Card className="px-6 py-6 text-center">
          <p className="font-bold">{t("console.demoRequests.none")}</p>
          <p className="mt-1 text-sm text-ink-3">{t("console.demoRequests.noneHelp")}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {requests.data.results.map((request) => (
            <RequestCard key={request.id} request={request} onErase={() => setErase(request)} />
          ))}
          <Card>
            <div className="flex items-center justify-between px-4 py-2.5 text-sm text-ink-3">
              {t("console.demoRequests.count", { count: requests.data.count })}
            </div>
            <Pager
              page={page}
              onPage={setPage}
              previous={requests.data.previous}
              next={requests.data.next}
            />
          </Card>
        </div>
      )}
      <ConfirmDialog
        open={erase !== null}
        onOpenChange={(open) => !open && setErase(null)}
        title={
          erase
            ? t("console.demoRequests.erase.title", { school: erase.school_name || erase.name })
            : ""
        }
        confirmLabel={t("console.demoRequests.erase.confirm")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => erase && remove.mutate(erase)}
        pending={remove.isPending}
        destructive
      >
        {t("console.demoRequests.erase.text")}
      </ConfirmDialog>
    </>
  );
}

function RequestCard({ request, onErase }: { request: DemoRequest; onErase: () => void }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const current = request.status ?? "new";
  const [status, setStatus] = useState<Status>(current);
  const [notes, setNotes] = useState(request.notes);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/console/demo-requests/{id}/", {
          params: { path: { id: request.id } },
          body: { status, notes },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.demoRequests }),
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const digits = request.phone.replace("+", "");
  const changed = status !== current || notes !== request.notes;
  const chat = request.source === "chat";
  const facts = [
    request.town,
    request.size && t(`console.demoRequests.sizes.${request.size}`),
    t("console.demoRequests.received", {
      date: formatDateTime(request.created_at, i18n.language, timeZone),
    }),
    t(`console.demoRequests.languages.${request.language === "en" ? "en" : "fr"}`),
  ].filter(Boolean);

  return (
    <Card className="grid gap-4 p-4 min-[820px]:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold break-words">{request.school_name || request.name}</h2>
            <p className="text-sm text-ink-3">{facts.join(" · ")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {chat && <StatusPill tone="gray">{t("console.demoRequests.chat")}</StatusPill>}
            <StatusPill tone={TONES[current]}>
              {t(`console.demoRequests.statuses.${current}`)}
            </StatusPill>
          </div>
        </div>
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
          <dt className="text-ink-3">{t("console.demoRequests.contact")}</dt>
          <dd className="font-bold break-words">
            {request.role
              ? `${request.name}, ${t(`console.demoRequests.roles.${request.role}`)}`
              : request.name}
          </dd>
          <dt className="text-ink-3">{t("console.demoRequests.phone")}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <span className="tabular-nums">{formatPhone(request.phone)}</span>
            <a
              className={buttonVariants({ variant: "outline", size: "sm" })}
              href={`tel:${request.phone}`}
            >
              <Icon name="phone" size={16} />
              {t("console.demoRequests.call")}
            </a>
            <a
              className={buttonVariants({ variant: "outline", size: "sm" })}
              href={`https://wa.me/${digits}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icon name="chat" size={16} />
              {t("console.demoRequests.whatsapp")}
            </a>
          </dd>
          {!chat && (
            <>
              <dt className="text-ink-3">{t("console.demoRequests.email")}</dt>
              <dd className="break-words">
                {request.email ? <a href={`mailto:${request.email}`}>{request.email}</a> : "—"}
              </dd>
            </>
          )}
        </dl>
        {request.message ? (
          <p className="rounded-md bg-surface px-3 py-2.5 text-sm break-words whitespace-pre-line">
            {request.message}
          </p>
        ) : (
          <p className="text-sm text-ink-3">{t("console.demoRequests.noMessage")}</p>
        )}
      </div>
      <div className="flex flex-col gap-3">
        <Field id={`status-${request.id}`} label={t("console.demoRequests.status")}>
          {(control) => (
            <Select
              {...control}
              value={status}
              onChange={(event) => setStatus(event.target.value as Status)}
            >
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {t(`console.demoRequests.statuses.${value}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id={`notes-${request.id}`}
          label={t("console.demoRequests.notes")}
          help={t("console.demoRequests.notesHelp")}
        >
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              maxLength={2000}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          )}
        </Field>
        {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={!changed || save.isPending} onClick={() => save.mutate()}>
            {t("console.demoRequests.save")}
          </Button>
          {!chat && (
            <Link className={buttonVariants({ variant: "ghost", size: "sm" })} to="/schools/new">
              {t("console.demoRequests.openTrial")}
            </Link>
          )}
          <Button variant="ghost" size="sm" className="ml-auto text-due" onClick={onErase}>
            {t("console.demoRequests.erase.confirm")}
          </Button>
        </div>
      </div>
    </Card>
  );
}
