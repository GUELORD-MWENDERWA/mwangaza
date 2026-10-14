// Sessions support « en tant qu'école » (5.4.2), ouvertes et passées : école, motif, début, fin
// (ouverte jusqu'à…, fermée, expirée) et nombre d'actions faites dans l'école pendant la session.
import { api, call } from "@mwangaza/api";
import { errorMessage, formatDateTime, formatTime, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, Input, Skeleton, StatusPill, Table } from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";
import { JournalLayout } from "./JournalPage";

export function SupportSessionsPage() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const query = useDeferredValue(search.trim());
  const sessions = useQuery({
    queryKey: [...keys.supportSessions, { query, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/support-sessions/", {
          params: { query: { search: query || undefined, page } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const when = (value: string) => formatDateTime(value, i18n.language, timeZone);
  const time = (value: string) => formatTime(value, i18n.language, timeZone);

  return (
    <JournalLayout>
      <Input
        type="search"
        aria-label={t("console.journal.sessions.search")}
        placeholder={t("console.journal.sessions.search")}
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        className="max-w-sm"
      />
      {sessions.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : sessions.isError ? (
        <>
          <Banner tone="due">{errorMessage(sessions.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void sessions.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          {sessions.data.results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.journal.sessions.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.journal.sessions.school")}</th>
                  <th>{t("console.journal.sessions.reason")}</th>
                  <th>{t("console.journal.sessions.start")}</th>
                  <th>{t("console.journal.sessions.end")}</th>
                  <th>{t("console.journal.sessions.actions")}</th>
                  <th>{t("console.journal.by")}</th>
                </tr>
              </thead>
              <tbody>
                {sessions.data.results.map((session) => (
                  <tr key={session.id}>
                    <td>
                      <Link
                        to={`/schools/${session.school.id}`}
                        className="font-bold hover:underline"
                      >
                        {session.school.name}
                      </Link>
                    </td>
                    <td data-wrap className="min-w-48">
                      {session.reason}
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {when(session.started_at)}
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {session.state === "ended" && session.ended_at ? (
                        when(session.ended_at)
                      ) : (
                        <>
                          <StatusPill tone={session.state === "open" ? "info" : "warn"}>
                            {t(`console.journal.sessions.${session.state}`)}
                          </StatusPill>{" "}
                          {session.state === "open"
                            ? t("console.journal.sessions.until", {
                                time: time(session.expires_at),
                              })
                            : time(session.expires_at)}
                        </>
                      )}
                    </td>
                    <td className="tabular-nums">{session.actions}</td>
                    <td>{[session.admin.first_name, session.admin.last_name].join(" ")}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          <Pager
            page={page}
            onPage={setPage}
            previous={sessions.data.previous}
            next={sessions.data.next}
          />
        </Card>
      )}
    </JournalLayout>
  );
}
