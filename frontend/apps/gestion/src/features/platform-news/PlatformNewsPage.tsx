// Annonces de la plateforme à l'école (5.4.3, maquette `console/annonces`), les plus récentes
// d'abord, pour tout le personnel. Celles qui s'affichent sont notées comme lues par ce compte ;
// la pastille « Nouvelle » reste jusqu'à la prochaine ouverture.
import { formatDate, useTranslation } from "@mwangaza/i18n";
import { Card, PageHeader, Skeleton, StatusPill, usePlatform } from "@mwangaza/ui";
import { useEffect, useState } from "react";

import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { PAGE_SIZE, useMarkRead, useNews } from "./data";

export function PlatformNewsPage() {
  const { t, i18n } = useTranslation();
  const platform = usePlatform().name;
  const school = useCurrentSchool();
  const [page, setPage] = useState(1);
  const list = useNews(page);
  const { mutate: markRead } = useMarkRead();
  const results = list.data?.results ?? [];
  const unread = results
    .filter((news) => !news.is_read)
    .map((news) => news.id)
    .join(",");
  useEffect(() => {
    if (unread) markRead(unread.split(","));
  }, [unread, markRead]);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader
        title={t("platformNews.title", { platform })}
        subtitle={t("platformNews.subtitle")}
      />
      <Card>
        {!list.data ? (
          <Skeleton label={t("common.loading")} />
        ) : results.length === 0 ? (
          <p className="px-4 py-5 text-ink-3">{t("platformNews.empty")}</p>
        ) : (
          results.map((news) => (
            <article
              key={news.id}
              className="flex flex-col gap-1.5 border-t border-line px-4 py-3.5 first:border-t-0"
            >
              <div className="flex flex-wrap items-center gap-2">
                <b>{news.title}</b>
                {!news.is_read && <StatusPill tone="info">{t("platformNews.new")}</StatusPill>}
              </div>
              <span className="text-sm text-ink-3">
                {formatDate(news.published_at, i18n.language, school.timezone)}
              </span>
              <p className="whitespace-pre-line text-ink-2">{news.body}</p>
            </article>
          ))
        )}
        {count > PAGE_SIZE && (
          <Pagination
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
            summary={t("platformNews.range", { from, to: from + results.length - 1, count })}
          />
        )}
      </Card>
    </>
  );
}
