// Annonces de l'école à son personnel (5.7, maquette `annonces-personnel`), les plus récentes
// d'abord : tout compte de l'école les lit, quel que soit son rôle. Elles sont publiées depuis
// l'écran « Annonces » (destinataire « Personnel ») ; une annonce archivée n'est plus ici.
import { formatDate, useTranslation } from "@mwangaza/i18n";
import { Card, PageHeader, Skeleton } from "@mwangaza/ui";
import { useState } from "react";

import { fullName } from "../../lib/people";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { PAGE_SIZE, useStaffNews } from "./data";

export function StaffNewsPage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [page, setPage] = useState(1);
  const list = useStaffNews(page);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader
        title={t("staffNews.title")}
        subtitle={t("staffNews.subtitle", { school: school.name })}
      />
      <Card>
        {!list.data ? (
          <Skeleton label={t("common.loading")} />
        ) : results.length === 0 ? (
          <p className="px-4 py-5 text-ink-3">{t("staffNews.empty")}</p>
        ) : (
          results.map((news) => (
            <article
              key={news.id}
              className="flex flex-col gap-1.5 border-t border-line px-4 py-3.5 first:border-t-0"
            >
              <b>{news.title}</b>
              <span className="text-sm text-ink-3">
                {[
                  formatDate(news.published_at, i18n.language, school.timezone),
                  news.published_by && t("staffNews.by", { name: fullName(news.published_by) }),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              <p className="whitespace-pre-line text-ink-2">{news.body}</p>
              {news.attachment && (
                <a
                  className="self-start text-sm font-bold text-lake underline"
                  href={news.attachment}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("staffNews.pdf")}
                </a>
              )}
            </article>
          ))
        )}
        {count > PAGE_SIZE && (
          <Pagination
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
            summary={t("staffNews.range", { from, to: from + results.length - 1, count })}
          />
        )}
      </Card>
    </>
  );
}
