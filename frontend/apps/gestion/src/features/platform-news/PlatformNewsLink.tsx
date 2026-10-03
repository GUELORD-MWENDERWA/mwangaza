import { useTranslation } from "@mwangaza/i18n";
import { cn, Icon, usePlatform } from "@mwangaza/ui";
import { Link } from "react-router";

import { useUnreadNews } from "./data";

/** Lien du bas du menu vers les annonces de la plateforme (5.4.3), avec le nombre de non lues. */
export function PlatformNewsLink({
  className,
  onClick,
}: {
  className?: string;
  onClick?: () => void;
}) {
  const { t } = useTranslation();
  const platform = usePlatform().name;
  const unread = useUnreadNews().data?.count ?? 0;
  return (
    <Link
      to="/platform-news"
      onClick={onClick}
      className={cn(
        "flex min-h-11 items-center gap-2.5 text-sm text-basalt-soft no-underline hover:text-basalt-ink",
        className,
      )}
    >
      <Icon name="megaphone" size={18} />
      <span className="min-w-0 flex-1 truncate">{t("platformNews.menu", { platform })}</span>
      {unread > 0 && (
        <span className="rounded-full bg-lamp px-1.5 text-xs font-bold text-basalt">
          <span aria-hidden>{unread}</span>
          <span className="sr-only">{t("platformNews.unread", { count: unread })}</span>
        </span>
      )}
    </Link>
  );
}
