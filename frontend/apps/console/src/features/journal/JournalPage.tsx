// Journal de la plateforme (5.4.2, maquette `console/journal`) : actions du support dans la
// console, filtres par type, période et objet ; l'objet mène à sa fiche, où « Derniers
// changements » montre l'avant → après. Onglet voisin : sessions support.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, Input, PageHeader, Select, Skeleton, Table } from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";

type Entry = Schemas["PlatformLog"];
type Domain = "platform" | "school" | "account" | "device";
const DOMAINS: Domain[] = ["platform", "school", "account", "device"];

/** Page de l'objet d'une entrée dans la console ; un appareil n'en a pas. */
function objectPage(entry: Entry): string | null {
  if (entry.entity_type === "schools.school") return `/schools/${entry.entity_id}`;
  if (entry.entity_type === "accounts.user") return `/accounts/${entry.entity_id}`;
  if (entry.entity_type === "core.platformsettings") return "/identity";
  return null;
}

/** En-tête commun aux deux onglets du journal. */
export function JournalLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const tab = ({ isActive }: { isActive: boolean }) =>
    `-mb-px border-b-[3px] px-3.5 py-2.5 font-bold ${
      isActive ? "border-lake text-ink" : "border-transparent text-ink-3 hover:text-ink"
    }`;
  return (
    <>
      <PageHeader title={t("console.journal.title")} subtitle={t("console.journal.subtitle")} />
      <nav className="flex gap-1 overflow-x-auto border-b border-line">
        <NavLink to="/journal" end className={tab}>
          {t("console.journal.tabs.log")}
        </NavLink>
        <NavLink to="/journal/support" className={tab}>
          {t("console.journal.tabs.support")}
        </NavLink>
      </nav>
      {children}
    </>
  );
}

export function JournalPage() {
  const { t, i18n } = useTranslation();
  const [domain, setDomain] = useState<Domain | "">("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const filters = { domain, since, until, search: useDeferredValue(search.trim()) };
  const log = useQuery({
    queryKey: [...keys.journal, { ...filters, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/audit/", {
          params: {
            query: {
              domain: filters.domain || undefined,
              since: filters.since || undefined,
              until: filters.until || undefined,
              search: filters.search || undefined,
              page,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const filter =
    <T,>(set: (value: T) => void) =>
    (value: T) => {
      set(value);
      setPage(1);
    };

  return (
    <JournalLayout>
      <div className="grid gap-3 min-[700px]:grid-cols-[auto_auto_auto_minmax(0,320px)]">
        <Select
          aria-label={t("console.journal.domain")}
          value={domain}
          onChange={(event) => filter(setDomain)(event.target.value as Domain | "")}
        >
          <option value="">{t("console.journal.allDomains")}</option>
          {DOMAINS.map((value) => (
            <option key={value} value={value}>
              {t(`console.journal.domains.${value}`)}
            </option>
          ))}
        </Select>
        <Input
          type="date"
          aria-label={t("console.journal.since")}
          value={since}
          onChange={(event) => filter(setSince)(event.target.value)}
        />
        <Input
          type="date"
          aria-label={t("console.journal.until")}
          value={until}
          onChange={(event) => filter(setUntil)(event.target.value)}
        />
        <Input
          type="search"
          aria-label={t("console.journal.search")}
          placeholder={t("console.journal.search")}
          value={search}
          onChange={(event) => filter(setSearch)(event.target.value)}
        />
      </div>
      {log.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : log.isError ? (
        <>
          <Banner tone="due">{errorMessage(log.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void log.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          {log.data.results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.journal.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.journal.when")}</th>
                  <th>{t("console.journal.action")}</th>
                  <th>{t("console.journal.object")}</th>
                  <th>{t("console.journal.by")}</th>
                </tr>
              </thead>
              <tbody>
                {log.data.results.map((entry) => {
                  const to = objectPage(entry);
                  return (
                    <tr key={entry.id}>
                      <td className="text-sm whitespace-nowrap text-ink-3">
                        {formatDateTime(entry.created_at, i18n.language, timeZone)}
                      </td>
                      <td>
                        <b>{t(`console.actions.${entry.action}`)}</b>
                      </td>
                      <td>
                        {to ? (
                          <Link to={to} className="hover:underline">
                            {entry.entity_label}
                          </Link>
                        ) : (
                          entry.entity_label
                        )}
                      </td>
                      <td>
                        {entry.actor
                          ? [entry.actor.first_name, entry.actor.last_name].join(" ")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          )}
          <Pager page={page} onPage={setPage} previous={log.data.previous} next={log.data.next} />
        </Card>
      )}
    </JournalLayout>
  );
}
