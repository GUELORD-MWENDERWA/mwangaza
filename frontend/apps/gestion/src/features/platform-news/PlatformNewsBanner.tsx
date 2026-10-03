// Bandeau des annonces de la plateforme (5.4.3, maquette `console/annonces`) en haut de chaque
// écran de la Gestion : la plus récente non lue par ce compte. « Fermer » la note comme lue (elle
// disparaît tout de suite, même sans réseau), « Lire » ouvre la liste.
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button } from "@mwangaza/ui";
import { useState } from "react";
import { Link, useMatch } from "react-router";

import { useMarkRead, useUnreadNews } from "./data";

export function PlatformNewsBanner() {
  const { t } = useTranslation();
  const onList = useMatch("/platform-news");
  const unread = useUnreadNews();
  const markRead = useMarkRead();
  const [closed, setClosed] = useState<string[]>([]);
  const news = unread.data?.results.find((item) => !closed.includes(item.id));
  if (!news || onList) return null;
  return (
    <Banner tone="info" icon="megaphone" role="region" aria-label={t("platformNews.bannerLabel")}>
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="min-w-0 flex-[1_1_220px]">
          <b className="block">{news.title}</b>
          <span className="block truncate text-ink-2">{news.body}</span>
        </div>
        <div className="ml-auto flex gap-1.5">
          <Button asChild size="sm" variant="outline">
            <Link to="/platform-news">{t("platformNews.read")}</Link>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setClosed([...closed, news.id]);
              markRead.mutate([news.id]);
            }}
          >
            {t("platformNews.close")}
          </Button>
        </div>
      </div>
    </Banner>
  );
}
