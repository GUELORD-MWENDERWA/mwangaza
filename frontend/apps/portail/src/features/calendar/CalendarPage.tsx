// Calendrier (maquette `portail/calendrier`, 5.7) : d'abord les convocations des parents pour
// leurs enfants (jour, heure, personne à voir, motif), notées « vues » dès qu'elles s'affichent ;
// puis les événements à venir des écoles des enfants, rangés par mois. Un événement réservé au
// personnel n'arrive jamais ici.
import {
  errorMessage,
  formatDateTime,
  formatDay,
  formatMonth,
  useTranslation,
} from "@mwangaza/i18n";
import { Banner, Button, Card, CardContent, Skeleton, StatusPill, Tag } from "@mwangaza/ui";
import { useEffect, useRef } from "react";

import { PortalFrame } from "../home/PortalFrame";
import { type PortalEvent, type PortalSummons, useCalendar, useMarkSeen, useSummons } from "./data";

const TONES = {
  meeting: "info",
  exam: "due",
  holiday: "ok",
  activity: "warn",
  other: "gray",
} as const;

export function CalendarPage() {
  const { t, i18n } = useTranslation();
  const calendar = useCalendar();
  const summons = useSummons();
  const { mutate: markSeen } = useMarkSeen();
  const sent = useRef(new Set<string>());
  const convocations = summons.data?.results;
  const events = calendar.data?.pages.flatMap((page) => page.results) ?? [];
  const months = [...new Set(events.map((event) => event.starts_on.slice(0, 7)))];

  useEffect(() => {
    const ids = (convocations ?? [])
      .filter((item) => !item.seen && !sent.current.has(item.id))
      .map((item) => item.id);
    if (ids.length === 0) return;
    for (const id of ids) sent.current.add(id);
    markSeen(ids);
  }, [convocations, markSeen]);

  return (
    <PortalFrame heading={t("portal.calendar.title")}>
      {convocations?.map((item) => (
        <SummonsCard key={item.id} summons={item} />
      ))}
      {calendar.isPending && <Skeleton label={t("common.loading")} />}
      {calendar.isError && (
        <div className="flex flex-col gap-3">
          <Banner tone="due">{errorMessage(calendar.error, t)}</Banner>
          <Button variant="outline" onClick={() => void calendar.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {calendar.isSuccess && events.length === 0 && (
        <p className="py-6 text-center text-ink-3">{t("portal.calendar.empty")}</p>
      )}
      {months.map((month) => (
        <section key={month} className="flex flex-col gap-2.5">
          <h2 className="text-[1.05rem] first-letter:uppercase">
            {formatMonth(month, i18n.language)}
          </h2>
          {events
            .filter((event) => event.starts_on.startsWith(month))
            .map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
        </section>
      ))}
      {calendar.hasNextPage && (
        <Button
          variant="outline"
          disabled={calendar.isFetchingNextPage}
          onClick={() => void calendar.fetchNextPage()}
        >
          {t("portal.calendar.more")}
        </Button>
      )}
    </PortalFrame>
  );
}

function SummonsCard({ summons }: { summons: PortalSummons }) {
  const { t, i18n } = useTranslation();
  return (
    <Card className="border-[#f3d9a4] bg-warn-50">
      <CardContent className="flex flex-col gap-2 py-4">
        <div className="flex items-center justify-between gap-2">
          <Tag className="min-w-0">{summons.school_name}</Tag>
          <StatusPill tone="warn" className="shrink-0">
            {t("portal.calendar.summons")}
          </StatusPill>
        </div>
        <h2 className="text-[1.05rem]">
          {t("portal.calendar.summonsFor", { name: summons.student_name })}
        </h2>
        <b className="tabular-nums">
          {formatDateTime(summons.meeting_at, i18n.language, summons.school_timezone)}
        </b>
        <span className="text-[.95rem]">
          {t("portal.calendar.meetWith", { name: summons.meet_with })}
        </span>
        <p className="text-[.95rem] whitespace-pre-line">{summons.reason}</p>
      </CardContent>
    </Card>
  );
}

function EventCard({ event }: { event: PortalEvent }) {
  const { t, i18n } = useTranslation();
  const start = formatDay(event.starts_on, i18n.language);
  const days =
    event.ends_on === event.starts_on
      ? start
      : `${start} – ${formatDay(event.ends_on, i18n.language)}`;
  return (
    <Card>
      <CardContent className="flex flex-col gap-1.5 py-3.5">
        <div className="flex items-center justify-between gap-2">
          <Tag className="min-w-0">{event.school_name}</Tag>
          <StatusPill tone={TONES[event.kind]} className="shrink-0">
            {t(`portal.calendar.kinds.${event.kind}`)}
          </StatusPill>
        </div>
        <b>{event.title}</b>
        <span className="text-sm text-ink-2 tabular-nums">
          {[days, event.start_time?.slice(0, 5)].filter(Boolean).join(" · ")}
        </span>
        {event.description && (
          <p className="text-[.92rem] whitespace-pre-line text-ink-3">{event.description}</p>
        )}
      </CardContent>
    </Card>
  );
}
