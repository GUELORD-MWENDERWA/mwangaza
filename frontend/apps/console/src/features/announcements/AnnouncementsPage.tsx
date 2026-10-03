// Annonces de la plateforme aux écoles (5.4.3, maquette `console/annonces`) : à gauche la nouvelle
// annonce (toutes les écoles ou celles choisies), publiée tout de suite ; à droite les annonces
// publiées avec « lue par N personnes ». Jamais modifiée : on l'archive, elle quitte la Gestion.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  List,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Tag,
  Textarea,
} from "@mwangaza/ui";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { Pager } from "../shell/Pager";

type Announcement = Schemas["ConsolePlatformAnnouncement"];
type SchoolRef = Schemas["ConsoleSchoolRef"];
type Values = {
  title: string;
  body: string;
  audience: Schemas["PlatformAudienceEnum"];
  schools: SchoolRef[];
};
const EMPTY: Values = { title: "", body: "", audience: "all_schools", schools: [] };

export function AnnouncementsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: [...keys.announcements, { page }],
    queryFn: () => call(api.GET("/api/console/announcements/", { params: { query: { page } } })),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title={t("console.announcements.title")}
        subtitle={t("console.announcements.subtitle")}
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <NewAnnouncementCard />
        <Card>
          <CardHeader>
            <CardTitle>{t("console.announcements.list")}</CardTitle>
          </CardHeader>
          <CardContent>
            {list.isPending ? (
              <Skeleton label={t("common.loading")} />
            ) : list.isError ? (
              <Banner tone="due">{errorMessage(list.error, t)}</Banner>
            ) : list.data.results.length === 0 ? (
              <p className="text-ink-3">{t("console.announcements.empty")}</p>
            ) : (
              <List>
                {list.data.results.map((announcement) => (
                  <PublishedItem key={announcement.id} announcement={announcement} />
                ))}
              </List>
            )}
          </CardContent>
          <Pager
            page={page}
            onPage={setPage}
            previous={list.data?.previous}
            next={list.data?.next}
          />
        </Card>
      </div>
    </>
  );
}

function NewAnnouncementCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const required = t("fieldErrors.required");
  const schema = z
    .object({
      title: z.string().trim().min(1, required),
      body: z.string().trim().min(1, required),
      audience: z.enum(["all_schools", "schools"]),
      schools: z.array(z.object({ id: z.string(), code: z.string(), name: z.string() })),
    })
    .refine((value) => value.audience === "all_schools" || value.schools.length > 0, {
      path: ["schools"],
      message: t("console.announcements.noSchool"),
    });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const [general, setGeneral] = useState<string | null>(null);
  const audience = form.watch("audience");
  const chosen = form.watch("schools");
  const errors = form.formState.errors;
  const publish = useMutation({
    mutationFn: (values: Values) =>
      call(
        api.POST("/api/console/announcements/", {
          body: { ...values, schools: values.schools.map((school) => school.id) },
        }),
      ),
    onSuccess: () => {
      form.reset(EMPTY);
      void queryClient.invalidateQueries({ queryKey: keys.announcements });
    },
    onError: (error) =>
      setGeneral(
        applyServerErrors(error, ["title", "body", "audience", "schools"], form.setError, t),
      ),
  });
  const setSchools = (next: SchoolRef[]) =>
    form.setValue("schools", next, { shouldValidate: form.formState.isSubmitted });
  const onSubmit = form.handleSubmit((values) => {
    setGeneral(null);
    publish.reset();
    publish.mutate(values);
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.announcements.new")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)} noValidate>
          {publish.isSuccess && <Banner tone="ok">{t("console.announcements.published")}</Banner>}
          {general && <Banner tone="due">{general}</Banner>}
          <Field
            id="announcement-title"
            label={t("console.announcements.titleLabel")}
            error={errors.title?.message}
          >
            {(control) => <Input {...control} maxLength={120} {...form.register("title")} />}
          </Field>
          <Field
            id="announcement-body"
            label={t("console.announcements.body")}
            error={errors.body?.message}
          >
            {(control) => (
              <Textarea
                {...control}
                maxLength={2000}
                className="min-h-32"
                {...form.register("body")}
              />
            )}
          </Field>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-bold">{t("console.announcements.audience")}</span>
            <Segmented
              label={t("console.announcements.audience")}
              value={audience}
              onValueChange={(value) =>
                form.setValue("audience", value, { shouldValidate: form.formState.isSubmitted })
              }
              options={[
                { value: "all_schools", label: t("console.announcements.audiences.all_schools") },
                { value: "schools", label: t("console.announcements.audiences.schools") },
              ]}
            />
            {audience === "schools" && <SchoolPicker chosen={chosen} onChange={setSchools} />}
            {errors.schools?.message && (
              <span className="text-sm text-due" role="alert">
                {errors.schools.message}
              </span>
            )}
          </div>
          <Button type="submit" disabled={publish.isPending}>
            {audience === "all_schools"
              ? t("console.announcements.publishAll")
              : t("console.announcements.publishFor", { count: chosen.length })}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/** Écoles choisies en étiquettes ; une recherche propose les autres (toutes les écoles de la
 *  plateforme, pas seulement la première page). */
function SchoolPicker({
  chosen,
  onChange,
}: {
  chosen: SchoolRef[];
  onChange: (schools: SchoolRef[]) => void;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const query = useDeferredValue(search.trim());
  const found = useQuery({
    queryKey: [...keys.schools, { search: query }],
    queryFn: () =>
      call(api.GET("/api/console/schools/", { params: { query: { search: query || undefined } } })),
    enabled: query.length > 0,
  });
  const ids = new Set(chosen.map((school) => school.id));
  const suggestions = (found.data?.results ?? []).filter((school) => !ids.has(school.id));

  return (
    <div
      className="flex flex-col gap-2"
      role="group"
      aria-label={t("console.announcements.schools")}
    >
      {chosen.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chosen.map((school) => (
            <Tag key={school.id} className="inline-flex items-center gap-1">
              {school.name}
              <button
                type="button"
                className="rounded px-0.5 hover:bg-gray-100"
                aria-label={t("console.announcements.removeSchool", { name: school.name })}
                onClick={() => onChange(chosen.filter((other) => other.id !== school.id))}
              >
                ✕
              </button>
            </Tag>
          ))}
        </div>
      )}
      <Input
        type="search"
        aria-label={t("console.announcements.addSchool")}
        placeholder={t("console.announcements.addSchool")}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.slice(0, 8).map((school) => (
            <Button
              key={school.id}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                onChange([...chosen, { id: school.id, code: school.code, name: school.name }]);
                setSearch("");
              }}
            >
              + {school.name}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

function PublishedItem({ announcement }: { announcement: Announcement }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const archive = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/console/announcements/{id}/archive/", {
          params: { path: { id: announcement.id } },
        }),
      ),
    onSuccess: () => {
      setConfirm(false);
      void queryClient.invalidateQueries({ queryKey: keys.announcements });
    },
  });
  const archived = announcement.archived_at !== null;
  const details = [
    announcement.audience === "all_schools"
      ? t("console.announcements.audiences.all_schools")
      : announcement.schools.map((school) => school.name).join(", "),
    formatDay(announcement.published_at.slice(0, 10), i18n.language),
    t("console.announcements.readBy", { count: announcement.read_by }),
  ];
  return (
    <div>
      <div className="min-w-0">
        <b>{announcement.title}</b>
        <div className="text-sm text-ink-3">{details.join(" · ")}</div>
        {archive.isError && (
          <div className="text-sm text-due">{errorMessage(archive.error, t)}</div>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <StatusPill tone={archived ? "gray" : "ok"}>
          {t(archived ? "console.announcements.archived" : "console.announcements.live")}
        </StatusPill>
        {!archived && (
          <Button variant="ghost" size="sm" onClick={() => setConfirm(true)}>
            {t("console.announcements.archive")}
          </Button>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("console.announcements.archiveTitle", { title: announcement.title })}
        confirmLabel={t("console.announcements.archive")}
        cancelLabel={t("common.cancel")}
        pending={archive.isPending}
        onConfirm={() => archive.mutate()}
      >
        {t("console.announcements.archiveText")}
      </ConfirmDialog>
    </div>
  );
}
