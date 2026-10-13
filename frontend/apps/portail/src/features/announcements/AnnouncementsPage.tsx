// Annonces (maquette `portail/annonces`, H4) : celles des écoles reliées qui visent la famille,
// les plus récentes d'abord ; une puce par école dès qu'il y en a deux. Une annonce affichée est
// marquée lue (« lue par N familles » dans la Gestion) ; « Nouvelle » reste jusqu'à la visite
// suivante.
import { errorMessage, formatVisit, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, CardContent, Icon, Skeleton, StatusPill, Tag } from "@mwangaza/ui";
import { useEffect, useRef, useState } from "react";

import { useFamilies } from "../../lib/families";
import { PortalFrame } from "../home/PortalFrame";
import { type PortalAnnouncement, useAnnouncements, useMarkRead } from "./data";

export function AnnouncementsPage() {
  const { t } = useTranslation();
  const [family, setFamily] = useState<string>();
  const announcements = useAnnouncements(family);
  const { mutate: markRead } = useMarkRead();
  const sent = useRef(new Set<string>());
  const pages = announcements.data?.pages;
  const items = pages?.flatMap((page) => page.results) ?? [];

  useEffect(() => {
    const ids = (pages ?? [])
      .flatMap((page) => page.results)
      .filter((item) => !item.read && !sent.current.has(item.id))
      .map((item) => item.id);
    if (ids.length === 0) return;
    for (const id of ids) sent.current.add(id);
    markRead(ids);
  }, [pages, markRead]);

  return (
    <PortalFrame heading={t("portal.announcements.title")}>
      <SchoolFilter value={family} onChange={setFamily} />
      {announcements.isPending && <Skeleton label={t("common.loading")} />}
      {announcements.isError && (
        <div className="flex flex-col gap-3">
          <Banner tone="due">{errorMessage(announcements.error, t)}</Banner>
          <Button variant="outline" onClick={() => void announcements.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {announcements.isSuccess && items.length === 0 && (
        <p className="py-6 text-center text-ink-3">{t("portal.announcements.empty")}</p>
      )}
      {items.map((item) => (
        <AnnouncementCard key={item.id} announcement={item} />
      ))}
      {announcements.hasNextPage && (
        <Button
          variant="outline"
          disabled={announcements.isFetchingNextPage}
          onClick={() => void announcements.fetchNextPage()}
        >
          {t("portal.announcements.older")}
        </Button>
      )}
    </PortalFrame>
  );
}

/** « Toutes · ITIG · Les Volcans » : seulement avec deux écoles ou plus. */
function SchoolFilter({
  value,
  onChange,
}: {
  value?: string;
  onChange: (family?: string) => void;
}) {
  const { t } = useTranslation();
  const families = useFamilies().data?.filter((family) => family.status === "active") ?? [];
  if (families.length < 2) return null;
  const choices = [
    { id: undefined, label: t("portal.announcements.all") },
    ...families.map((family) => ({ id: family.id, label: family.school_name })),
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {choices.map((choice) => (
        <button
          key={choice.id ?? "all"}
          type="button"
          aria-pressed={value === choice.id}
          onClick={() => onChange(choice.id)}
        >
          <StatusPill
            tone={value === choice.id ? "info" : "gray"}
            className="px-3.5 py-1.5 text-[.88rem]"
          >
            {choice.label}
          </StatusPill>
        </button>
      ))}
    </div>
  );
}

function AnnouncementCard({ announcement }: { announcement: PortalAnnouncement }) {
  const { t, i18n } = useTranslation();
  const day = formatVisit(
    announcement.published_at,
    i18n.language,
    announcement.school_timezone,
    () => t("portal.announcements.today"),
  );
  return (
    <Card>
      <CardContent className="flex flex-col gap-2.5 py-4">
        <div className="flex items-center justify-between gap-2">
          <Tag className="min-w-0">
            {[announcement.school_name, ...announcement.classes].join(" · ")}
          </Tag>
          <span className="shrink-0 text-xs text-ink-3">{day}</span>
        </div>
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-[1.05rem]">{announcement.title}</h2>
          {!announcement.read && (
            <StatusPill tone="info" className="shrink-0">
              {t("portal.announcements.new")}
            </StatusPill>
          )}
        </div>
        <p className="text-[.95rem] whitespace-pre-line">{announcement.body}</p>
        {announcement.attachment && (
          <a
            className="flex items-center gap-1.5 text-sm font-bold text-lake underline"
            href={announcement.attachment}
            download
          >
            <Icon name="file" size={16} />
            {t("portal.announcements.attachment")}
          </a>
        )}
      </CardContent>
    </Card>
  );
}
