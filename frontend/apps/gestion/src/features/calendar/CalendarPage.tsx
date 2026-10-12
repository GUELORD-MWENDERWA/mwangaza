// Calendrier de l'école (5.7, maquette `calendrier`) : événements à venir, les plus proches
// d'abord, rangés par mois ; tout le personnel le lit. Avec `announcements.publish` (vérifié par
// le serveur) : ajouter, corriger, supprimer. Un événement « pour tous » s'affiche aussi dans le
// portail des parents ; « personnel seulement » reste dans la Gestion.
import { zodResolver } from "@hookform/resolvers/zod";
import { formatDay, formatMonth, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Tag,
  Textarea,
} from "@mwangaza/ui";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  type EventValues,
  KINDS,
  PAGE_SIZE,
  type SchoolEvent,
  useDeleteEvent,
  useEvents,
  useSaveEvent,
} from "./data";

const EMPTY: EventValues = {
  title: "",
  description: "",
  kind: "meeting",
  audience: "everyone",
  starts_on: "",
  ends_on: "",
  start_time: "",
};
const TONES = {
  meeting: "info",
  exam: "due",
  holiday: "ok",
  activity: "warn",
  other: "gray",
} as const;

/** « 07/09/2026 », ou « 07/09/2026 – 11/09/2026 » sur plusieurs jours. */
export function eventDays(event: Pick<SchoolEvent, "starts_on" | "ends_on">, language: string) {
  const start = formatDay(event.starts_on, language);
  const end = event.ends_on ?? event.starts_on;
  return end === event.starts_on ? start : `${start} – ${formatDay(end, language)}`;
}

export function CalendarPage() {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const editor = can(me, ["announcements.publish"]);
  const [past, setPast] = useState(false);
  const [page, setPage] = useState(1);
  const [edited, setEdited] = useState<SchoolEvent | "new" | null>(null);
  const list = useEvents(past, page);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const months = [...new Set(results.map((event) => event.starts_on.slice(0, 7)))];
  return (
    <>
      <PageHeader
        title={t("calendar.title")}
        subtitle={t(editor ? "calendar.subtitleEditor" : "calendar.subtitle")}
        actions={editor && <Button onClick={() => setEdited("new")}>{t("calendar.add")}</Button>}
      />
      <Segmented
        label={t("calendar.period")}
        className="mb-4"
        value={past ? "past" : "upcoming"}
        onValueChange={(value) => {
          setPast(value === "past");
          setPage(1);
        }}
        options={[
          { value: "upcoming", label: t("calendar.upcoming") },
          { value: "past", label: t("calendar.past") },
        ]}
      />
      {!list.data ? (
        <Skeleton label={t("common.loading")} />
      ) : results.length === 0 ? (
        <Card>
          <p className="px-4 py-5 text-ink-3">
            {t(past ? "calendar.emptyPast" : "calendar.empty")}
          </p>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {months.map((month) => (
            <Card key={month}>
              <h2 className="border-b border-line px-4 py-2.5 text-sm font-bold text-ink-2 first-letter:uppercase">
                {formatMonth(month, i18n.language)}
              </h2>
              {results
                .filter((event) => event.starts_on.startsWith(month))
                .map((event) => (
                  <EventRow
                    key={event.id}
                    event={event}
                    onEdit={editor ? () => setEdited(event) : undefined}
                  />
                ))}
            </Card>
          ))}
        </div>
      )}
      {count > PAGE_SIZE && (
        <Pagination
          page={page}
          hasPrevious={Boolean(list.data?.previous)}
          hasNext={Boolean(list.data?.next)}
          onPage={setPage}
          summary={t("calendar.range", { from, to: from + results.length - 1, count })}
        />
      )}
      <DialogRoot open={edited !== null} onOpenChange={(open) => !open && setEdited(null)}>
        {edited !== null && (
          <EventDialog event={edited === "new" ? null : edited} onDone={() => setEdited(null)} />
        )}
      </DialogRoot>
    </>
  );
}

function EventRow({ event, onEdit }: { event: SchoolEvent; onEdit?: () => void }) {
  const { t, i18n } = useTranslation();
  return (
    <article className="flex flex-wrap items-start justify-between gap-3 border-t border-line px-4 py-3.5 first:border-t-0">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <b>{event.title}</b>
          <StatusPill tone={TONES[event.kind]}>{t(`calendar.kinds.${event.kind}`)}</StatusPill>
          {event.audience === "staff" && <Tag>{t("calendar.audiences.staff")}</Tag>}
        </div>
        <span className="text-sm text-ink-2 tabular-nums">
          {[eventDays(event, i18n.language), event.start_time?.slice(0, 5)]
            .filter(Boolean)
            .join(" · ")}
        </span>
        {event.description && (
          <p className="whitespace-pre-line text-sm text-ink-3">{event.description}</p>
        )}
      </div>
      {onEdit && (
        <Button variant="ghost" size="sm" onClick={onEdit}>
          {t("calendar.edit")}
        </Button>
      )}
    </article>
  );
}

function EventDialog({ event, onDone }: { event: SchoolEvent | null; onDone: () => void }) {
  const { t } = useTranslation();
  const required = t("fieldErrors.required");
  const schema = z
    .object({
      title: z.string().trim().min(1, required),
      description: z.string().trim(),
      kind: z.enum(["meeting", "exam", "holiday", "activity", "other"]),
      audience: z.enum(["everyone", "staff"]),
      starts_on: z.string().min(1, required),
      ends_on: z.string(),
      start_time: z.string(),
    })
    .refine((value) => !value.ends_on || value.ends_on >= value.starts_on, {
      path: ["ends_on"],
      message: t("fieldErrors.ends_before_start"),
    });
  const form = useForm<EventValues>({
    resolver: zodResolver(schema),
    defaultValues: event
      ? {
          title: event.title,
          description: event.description ?? "",
          kind: event.kind ?? "other",
          audience: event.audience ?? "everyone",
          starts_on: event.starts_on,
          ends_on: event.ends_on && event.ends_on !== event.starts_on ? event.ends_on : "",
          start_time: event.start_time?.slice(0, 5) ?? "",
        }
      : EMPTY,
  });
  const [general, setGeneral] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const save = useSaveEvent(event?.id ?? null);
  const remove = useDeleteEvent();
  const errors = form.formState.errors;
  const onSubmit = form.handleSubmit((values) => {
    setGeneral(null);
    save.mutate(values, {
      onSuccess: onDone,
      onError: (error) =>
        setGeneral(
          applyServerErrors(
            error,
            ["title", "description", "kind", "audience", "starts_on", "ends_on", "start_time"],
            form.setError,
            t,
          ),
        ),
    });
  });
  return (
    <DialogContent title={t(event ? "calendar.editTitle" : "calendar.add")}>
      <form className="flex flex-col gap-4" onSubmit={(e) => void onSubmit(e)} noValidate>
        {general && <Banner tone="due">{general}</Banner>}
        {remove.error && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
        <Field id="event-title" label={t("calendar.fields.title")} error={errors.title?.message}>
          {(control) => <Input {...control} maxLength={120} {...form.register("title")} />}
        </Field>
        <Field id="event-kind" label={t("calendar.fields.kind")}>
          {(control) => (
            <Select {...control} {...form.register("kind")}>
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {t(`calendar.kinds.${kind}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <div className="grid grid-cols-1 gap-4 min-[520px]:grid-cols-3">
          <Field
            id="event-start"
            label={t("calendar.fields.startsOn")}
            error={errors.starts_on?.message}
          >
            {(control) => <Input {...control} type="date" {...form.register("starts_on")} />}
          </Field>
          <Field
            id="event-end"
            label={t("calendar.fields.endsOn")}
            help={t("calendar.fields.endsOnHelp")}
            error={errors.ends_on?.message}
          >
            {(control) => <Input {...control} type="date" {...form.register("ends_on")} />}
          </Field>
          <Field
            id="event-time"
            label={t("calendar.fields.startTime")}
            help={t("calendar.fields.startTimeHelp")}
            error={errors.start_time?.message}
          >
            {(control) => <Input {...control} type="time" {...form.register("start_time")} />}
          </Field>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-sm font-bold">{t("calendar.fields.audience")}</span>
          <Segmented
            label={t("calendar.fields.audience")}
            value={form.watch("audience")}
            onValueChange={(value) => form.setValue("audience", value, { shouldDirty: true })}
            options={[
              { value: "everyone", label: t("calendar.audiences.everyone") },
              { value: "staff", label: t("calendar.audiences.staff") },
            ]}
          />
          <span className="text-sm text-ink-3">{t("calendar.fields.audienceHelp")}</span>
        </div>
        <Field
          id="event-description"
          label={t("calendar.fields.description")}
          error={errors.description?.message}
        >
          {(control) => (
            <Textarea {...control} maxLength={1000} {...form.register("description")} />
          )}
        </Field>
        <div className="flex flex-wrap justify-end gap-2.5">
          {event && (
            <Button
              type="button"
              variant="ghost"
              className="mr-auto text-due"
              onClick={() => setConfirm(true)}
            >
              {t("calendar.delete")}
            </Button>
          )}
          <DialogClose asChild>
            <Button type="button" variant="outline">
              {t("calendar.cancel")}
            </Button>
          </DialogClose>
          <Button type="submit" disabled={save.isPending}>
            {t("calendar.save")}
          </Button>
        </div>
      </form>
      {event && (
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={t("calendar.deleteTitle", { title: event.title })}
          confirmLabel={t("calendar.delete")}
          cancelLabel={t("calendar.cancel")}
          pending={remove.isPending}
          onConfirm={() => remove.mutate(event.id, { onSuccess: onDone })}
        >
          {t("calendar.deleteText")}
        </ConfirmDialog>
      )}
    </DialogContent>
  );
}
