// Demandes des parents (M18, H5) : coordonnées envoyées par les familles depuis le portail. Rien
// n'est changé dans la fiche tant que le secrétariat ne les applique pas (`students.edit`, le
// serveur vérifie) ; « Ne pas appliquer » garde la fiche (ex. le parent n'a pas fait ce
// changement). Les deux vont au journal. Rien n'est dit des autres écoles de la famille.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDate, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  List,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { formatPhone } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";

type Item = Schemas["ContactChange"];
type Changes = Schemas["Changes"];
type Filter = "pending" | "handled" | "all";
const PAGE_SIZE = 50;
const TONES = { pending: "warn", applied: "ok", dismissed: "gray" } as const;
const FIELDS = ["address", "email", "emergency_contact"] as const;
type FieldName = (typeof FIELDS)[number];

function useContactChanges(status: Filter, page: number) {
  return useQuery({
    queryKey: [...keys.contactChanges, status, page],
    queryFn: () =>
      call(
        api.GET("/api/contact-changes/", {
          params: { query: { status, ...(page > 1 ? { page } : {}) } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

/** « 19/10 · 09:58 » dans le fuseau de l'école. */
function useWhen() {
  const { i18n } = useTranslation();
  const school = useCurrentSchool();
  return (iso: string) =>
    `${formatDate(iso, i18n.language, school.timezone).slice(0, 5)} · ${formatTime(iso, i18n.language, school.timezone)}`;
}

/** Avant / après d'un champ, en une ligne lisible ; vide : « — ». */
function useValue() {
  const { t } = useTranslation();
  return (changes: Changes, name: FieldName, side: "before" | "after") => {
    let text = "";
    if (name === "address" && changes.address) {
      const { commune, quartier, avenue, number } = changes.address[side];
      text = [commune, quartier, avenue, number].filter(Boolean).join(", ");
    } else if (name === "email" && changes.email) {
      text = changes.email[side];
    } else if (name === "emergency_contact" && changes.emergency_contact) {
      const { full_name, phone } = changes.emergency_contact[side];
      text = [full_name, phone && formatPhone(phone)].filter(Boolean).join(" · ");
    }
    return text || t("common.none");
  };
}

const changed = (changes: Changes) => FIELDS.filter((name) => changes[name]);

export function ParentRequestsPage() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Filter>("pending");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useContactChanges(status, page);
  const pending = useContactChanges("pending", 1);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const current = results.find((item) => item.id === selected) ?? results[0] ?? null;
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;

  return (
    <>
      <PageHeader
        title={t("parentRequests.title")}
        subtitle={t("parentRequests.subtitle")}
        actions={
          <Segmented
            label={t("parentRequests.filter")}
            value={status}
            onValueChange={(next) => {
              setStatus(next);
              setPage(1);
              setSelected(null);
            }}
            options={[
              {
                value: "pending",
                label: t("parentRequests.filters.pending", { count: pending.data?.count ?? 0 }),
              },
              { value: "handled", label: t("parentRequests.filters.handled") },
              { value: "all", label: t("parentRequests.filters.all") },
            ]}
          />
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          {!list.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : results.length === 0 ? (
            <CardContent className="text-ink-3">{t(`parentRequests.empty.${status}`)}</CardContent>
          ) : (
            <RequestTable items={results} selected={current?.id ?? null} onSelect={setSelected} />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
            summary={t("parentRequests.range", {
              from,
              to: from ? from + results.length - 1 : 0,
              count,
            })}
          />
        </Card>
        {current ? (
          <RequestDetail key={current.id} item={current} />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("parentRequests.pick")}</CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function RequestTable({
  items,
  selected,
  onSelect,
}: {
  items: Item[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  const when = useWhen();
  const value = useValue();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("parentRequests.columns.parent")}</th>
          <th>{t("parentRequests.columns.change")}</th>
          <th>{t("parentRequests.columns.before")}</th>
          <th>{t("parentRequests.columns.after")}</th>
          <th>{t("parentRequests.columns.when")}</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => {
          const names = changed(item.changes);
          return (
            <tr key={item.id} aria-selected={item.id === selected}>
              <td>
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  className="cursor-pointer text-left font-bold focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
                >
                  {item.family.parent || item.family.code}
                </button>
                <span className="block text-sm text-ink-3">
                  {t("parentRequests.familyLine", {
                    code: item.family.code,
                    count: item.family.children.length,
                  })}
                </span>
              </td>
              <td className="text-sm">
                {names.map((name) => (
                  <span key={name} className="block">
                    {t(`parentRequests.fields.${name}`)}
                  </span>
                ))}
              </td>
              <td className="text-sm text-ink-3">
                {names.map((name) => (
                  <s key={name} className="block">
                    {value(item.changes, name, "before")}
                  </s>
                ))}
              </td>
              <td className="text-sm font-bold">
                {names.map((name) => (
                  <span key={name} className="block">
                    {value(item.changes, name, "after")}
                  </span>
                ))}
              </td>
              <td className="text-sm whitespace-nowrap tabular-nums">{when(item.created_at)}</td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function Line({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex-wrap text-sm">
      <span>{label}</span>
      <span className="text-right">{children}</span>
    </div>
  );
}

function RequestDetail({ item }: { item: Item }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const when = useWhen();
  const value = useValue();
  const refresh = () =>
    Promise.all(
      [keys.contactChanges, keys.families, keys.students].map((queryKey) =>
        client.invalidateQueries({ queryKey }),
      ),
    );
  const decide = useMutation({
    mutationFn: (decision: "apply" | "dismiss") => {
      const params = { path: { id: item.id } };
      return call(
        decision === "apply"
          ? api.POST("/api/contact-changes/{id}/apply/", { params })
          : api.POST("/api/contact-changes/{id}/dismiss/", { params }),
      );
    },
    onSuccess: refresh,
  });
  const { family } = item;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{family.parent || family.code}</CardTitle>
        <StatusPill tone={TONES[item.status]}>
          {t(`parentRequests.states.${item.status}`)}
        </StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <List>
          <Line label={t("parentRequests.family")}>
            <Link to={`/families/${family.id}`}>{family.code}</Link>
          </Line>
          <Line label={t("parentRequests.children", { count: family.children.length })}>
            {family.children.join(", ") || t("common.none")}
          </Line>
          {changed(item.changes).map((name) => (
            <Line key={name} label={t(`parentRequests.fields.${name}`)}>
              <s className="block text-ink-3">{value(item.changes, name, "before")}</s>
              <b>{value(item.changes, name, "after")}</b>
            </Line>
          ))}
          <Line label={t("parentRequests.sent")}>{when(item.created_at)}</Line>
          {item.handled_at && (
            <Line label={t(`parentRequests.handled.${item.status as "applied" | "dismissed"}`)}>
              {item.handled_by} · {when(item.handled_at)}
            </Line>
          )}
        </List>
        {item.status === "pending" && (
          <>
            <Banner tone="info">{t("parentRequests.otherSchools")}</Banner>
            {decide.error && <Banner tone="due">{errorMessage(decide.error, t)}</Banner>}
            <div className="flex flex-wrap gap-2">
              {family.phone && (
                <a href={`tel:${family.phone}`} className={buttonVariants({ variant: "outline" })}>
                  <Icon name="phone" size={16} />
                  {t("parentRequests.call", { phone: formatPhone(family.phone) })}
                </a>
              )}
              <Button
                variant="outline"
                disabled={decide.isPending}
                onClick={() => decide.mutate("dismiss")}
              >
                {t("parentRequests.dismiss")}
              </Button>
              <Button
                className="flex-1"
                disabled={decide.isPending}
                onClick={() => decide.mutate("apply")}
              >
                <Icon name="check" size={16} />
                {t("parentRequests.apply")}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
