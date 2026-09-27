// Journal d'audit (M6, I1) : qui a fait quoi et quand, dans cette école seulement ; ni modifiable
// ni effaçable. Droit `audit.view` (directeur, promoteur). Le support Mwangaza n'est pas nommé.
// Export Excel : 2.4 ; appareil et heure hors ligne : 3.3.
import { api, call, type Schemas } from "@mwangaza/api";
import {
  type TFunction,
  formatDate,
  formatDateTime,
  formatTime,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Avatar,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  List,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  initials,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useSettled } from "../../lib/settled";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { ACTIONS, DOMAINS, actionTone, fieldLabel, renderValue } from "./values";

type Log = Schemas["AuditLog"];
type Filters = {
  actor: string;
  action: string;
  domain: string;
  since: string;
  until: string;
  search: string;
};
const PAGE_SIZE = 50;

export function AuditPage() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<Filters>({
    actor: "",
    action: "",
    domain: "",
    since: "",
    until: "",
    search: "",
  });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const search = useSettled(filters.search.trim());
  const query = Object.fromEntries(
    Object.entries({ ...filters, search }).filter(([, value]) => value !== ""),
  );
  const logs = useQuery({
    queryKey: [...keys.audit, query, page],
    queryFn: () =>
      call(
        api.GET("/api/audit/", { params: { query: { ...query, ...(page > 1 ? { page } : {}) } } }),
      ),
    placeholderData: keepPreviousData,
  });
  const actors = useQuery({
    queryKey: keys.auditActors,
    queryFn: () => call(api.GET("/api/audit/actors/")),
  });
  const change = (field: keyof Filters) => (value: string) => {
    setFilters((current) => ({ ...current, [field]: value }));
    setPage(1);
  };

  if (logs.isError && !logs.data) {
    return <LoadError error={logs.error} onRetry={() => void logs.refetch()} />;
  }
  const results = logs.data?.results ?? [];
  const current = results.find((log) => log.id === selected) ?? null;
  const count = logs.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;

  return (
    <>
      <PageHeader title={t("audit.title")} subtitle={t("audit.subtitle")} />
      <Card>
        <CardContent className="grid gap-3 min-[700px]:grid-cols-3 min-[1300px]:grid-cols-[1fr_1fr_1fr_auto_auto_1.4fr]">
          <Select
            aria-label={t("audit.filters.person")}
            value={filters.actor}
            onChange={(e) => change("actor")(e.target.value)}
          >
            <option value="">{t("audit.filters.allPeople")}</option>
            {(actors.data ?? []).map((person) => (
              <option key={person.id} value={person.id}>
                {fullName(person)}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("audit.filters.action")}
            value={filters.action}
            onChange={(e) => change("action")(e.target.value)}
          >
            <option value="">{t("audit.filters.allActions")}</option>
            {DOMAINS.map((domain) => (
              <optgroup key={domain} label={t(`audit.domains.${domain}`)}>
                {ACTIONS.filter((action) => action.startsWith(`${domain}.`)).map((action) => (
                  <option key={action} value={action}>
                    {t(`audit.actions.${action}`)}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
          <Select
            aria-label={t("audit.filters.domain")}
            value={filters.domain}
            onChange={(e) => change("domain")(e.target.value)}
          >
            <option value="">{t("audit.filters.allDomains")}</option>
            {DOMAINS.map((domain) => (
              <option key={domain} value={domain}>
                {t(`audit.domains.${domain}`)}
              </option>
            ))}
          </Select>
          <Input
            type="date"
            aria-label={t("audit.filters.since")}
            value={filters.since}
            onChange={(e) => change("since")(e.target.value)}
          />
          <Input
            type="date"
            aria-label={t("audit.filters.until")}
            value={filters.until}
            onChange={(e) => change("until")(e.target.value)}
          />
          <div className="relative">
            <Icon
              name="search"
              size={16}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3"
            />
            <Input
              type="search"
              aria-label={t("audit.filters.search")}
              placeholder={t("audit.filters.search")}
              value={filters.search}
              onChange={(e) => change("search")(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card>
          {!logs.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : results.length === 0 ? (
            <CardContent className="text-ink-3">{t("audit.empty")}</CardContent>
          ) : (
            <LogTable logs={results} selected={selected} onSelect={setSelected} />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(logs.data?.previous)}
            hasNext={Boolean(logs.data?.next)}
            onPage={setPage}
            summary={t("audit.range", { from, to: from ? from + results.length - 1 : 0, count })}
          />
        </Card>
        {current ? (
          <LogDetail key={current.id} log={current} />
        ) : (
          <Card>
            <CardContent className="text-ink-3">{t("audit.pick")}</CardContent>
          </Card>
        )}
      </div>
    </>
  );
}

function Who({ log }: { log: Log }) {
  const { t } = useTranslation();
  if (log.by_support) return <>{t("audit.support")}</>;
  if (!log.actor) return <>{t("audit.system")}</>;
  return <>{fullName(log.actor)}</>;
}

function subject(log: Log, t: TFunction) {
  if (log.entity_label) return log.entity_label;
  if (log.role_code) return t(`roles.${log.role_code}`);
  return t("common.none");
}

function LogTable({
  logs,
  selected,
  onSelect,
}: {
  logs: Log[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("audit.columns.when")}</th>
          <th>{t("audit.columns.who")}</th>
          <th>{t("audit.columns.action")}</th>
          <th>{t("audit.columns.on")}</th>
        </tr>
      </thead>
      <tbody>
        {logs.map((log) => {
          const initialsText = log.by_support
            ? "SA"
            : log.actor
              ? initials(log.actor.last_name, log.actor.first_name, log.actor.middle_name)
              : "—";
          return (
            <tr key={log.id} aria-selected={log.id === selected}>
              <td className="text-sm whitespace-nowrap tabular-nums">
                <button
                  type="button"
                  onClick={() => onSelect(log.id)}
                  className="cursor-pointer text-left focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
                >
                  {formatDate(log.created_at, i18n.language, school.timezone).slice(0, 5)} ·{" "}
                  {formatTime(log.created_at, i18n.language, school.timezone)}
                </button>
              </td>
              <td>
                <span className="flex items-center gap-2">
                  <Avatar text={initialsText} className="size-7 text-[.7rem]" />
                  <b className="text-sm">
                    <Who log={log} />
                  </b>
                </span>
              </td>
              <td>
                <StatusPill tone={actionTone(log.action)}>
                  {t(`audit.actions.${log.action}`)}
                </StatusPill>
              </td>
              <td className="text-sm">{subject(log, t)}</td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function LogDetail({ log }: { log: Log }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const before = (log.before ?? {}) as Record<string, unknown>;
  const after = (log.after ?? {}) as Record<string, unknown>;
  const fields = [...new Set([...Object.keys(before), ...Object.keys(after)])];
  const value = (field: string, data: Record<string, unknown>) =>
    field in data
      ? renderValue(field, data[field], t, i18n.language, school.timezone)
      : t("audit.values.none");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t(`audit.actions.${log.action}`)}</CardTitle>
        <span className="text-sm text-ink-3 tabular-nums">
          {formatDateTime(log.created_at, i18n.language, school.timezone)}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <List>
          <div>
            <span className="text-ink-2">{t("audit.detail.by")}</span>
            <b>
              <Who log={log} />
            </b>
          </div>
          <div>
            <span className="text-ink-2">{t("audit.detail.on")}</span>
            <span>{subject(log, t)}</span>
          </div>
          {log.ip && (
            <div>
              <span className="text-ink-2">{t("audit.detail.ip")}</span>
              <span className="tabular-nums">{log.ip}</span>
            </div>
          )}
          {log.user_agent && (
            <div>
              <span className="text-ink-2">{t("audit.detail.browser")}</span>
              <span className="min-w-0 truncate text-right text-sm" title={log.user_agent}>
                {log.user_agent}
              </span>
            </div>
          )}
        </List>
        {fields.length === 0 ? (
          <p className="text-sm text-ink-3">{t("audit.detail.noChange")}</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>{t("audit.detail.field")}</th>
                <th>{t("audit.detail.before")}</th>
                <th>{t("audit.detail.after")}</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((field) => (
                <tr key={field}>
                  <td className="align-top">{fieldLabel(field, t)}</td>
                  <td className="align-top text-ink-3">{value(field, before)}</td>
                  <td className="align-top font-bold">{value(field, after)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
