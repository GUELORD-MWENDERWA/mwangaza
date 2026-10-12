// Annonces aux familles (H4, maquette `annonces`) ou au personnel (5.7) : à gauche la nouvelle
// annonce (toutes les familles, certaines classes de l'année en cours ou le personnel, PDF
// joint), publiée tout de suite pour le nombre de familles ou de personnes que le serveur
// annonce ; à droite les annonces publiées, chacune avec sa circulaire à imprimer (lettre PDF à
// l'en-tête de l'école, pour les familles sans téléphone). Une annonce n'est jamais modifiée
// (elle a peut-être été lue) : on l'archive, elle quitte le portail ou la Gestion.
// Droit `announcements.publish` (vérifié par le serveur).
import { zodResolver } from "@hookform/resolvers/zod";
import { formatDate, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  List,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Tag,
  Textarea,
} from "@mwangaza/ui";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { useCurrentSchool } from "../../lib/school";
import { useClasses, useYears } from "../organisation/data";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  type Announcement,
  type Audience,
  type NewAnnouncement,
  PAGE_SIZE,
  useAnnouncements,
  useArchive,
  usePublish,
  useRecipients,
} from "./data";

const MAX_PDF_SIZE = 5 * 1024 * 1024;
const EMPTY: NewAnnouncement = {
  title: "",
  body: "",
  audience: "all_families",
  class_groups: [],
  attachment: null,
};

export function AnnouncementsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const list = useAnnouncements(page);

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  const results = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <PageHeader title={t("announcements.title")} subtitle={t("announcements.subtitle")} />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <NewAnnouncementCard />
        <Card>
          <CardHeader>
            <CardTitle>{t("announcements.list")}</CardTitle>
          </CardHeader>
          <CardContent>
            {!list.data ? (
              <Skeleton label={t("common.loading")} />
            ) : results.length === 0 ? (
              <p className="text-ink-3">{t("announcements.empty")}</p>
            ) : (
              <List>
                {results.map((announcement) => (
                  <PublishedItem key={announcement.id} announcement={announcement} />
                ))}
              </List>
            )}
          </CardContent>
          {count > PAGE_SIZE && (
            <Pagination
              page={page}
              hasPrevious={Boolean(list.data?.previous)}
              hasNext={Boolean(list.data?.next)}
              onPage={setPage}
              summary={t("announcements.range", {
                from,
                to: from + results.length - 1,
                count,
              })}
            />
          )}
        </Card>
      </div>
    </>
  );
}

function NewAnnouncementCard() {
  const { t } = useTranslation();
  const required = t("fieldErrors.required");
  const schema = z
    .object({
      title: z.string().trim().min(1, required),
      body: z.string().trim().min(1, required),
      audience: z.enum(["all_families", "class_groups", "staff"]),
      class_groups: z.array(z.string()),
      attachment: z.custom<File | null>(),
    })
    .superRefine((value, ctx) => {
      if (value.audience === "class_groups" && value.class_groups.length === 0) {
        ctx.addIssue({
          code: "custom",
          path: ["class_groups"],
          message: t("announcements.noClass"),
        });
      }
      const file = value.attachment;
      if (file && file.type !== "application/pdf") {
        ctx.addIssue({
          code: "custom",
          path: ["attachment"],
          message: t("fieldErrors.attachment_type"),
        });
      } else if (file && file.size > MAX_PDF_SIZE) {
        const message = t("fieldErrors.attachment_too_large");
        ctx.addIssue({ code: "custom", path: ["attachment"], message });
      }
    });
  const form = useForm<NewAnnouncement>({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const [general, setGeneral] = useState<string | null>(null);
  const [done, setDone] = useState<Audience | null>(null);
  const [preview, setPreview] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const years = useYears();
  const currentYear = years.data?.find((year) => year.is_current);
  const classes = useClasses(currentYear?.id ?? "");
  const audience = form.watch("audience");
  const chosen = form.watch("class_groups");
  const attachment = form.watch("attachment");
  const recipients = useRecipients(audience, chosen);
  const publish = usePublish();
  const errors = form.formState.errors;

  const setAudience = (next: Audience) =>
    form.setValue("audience", next, { shouldValidate: form.formState.isSubmitted });
  const setClasses = (next: string[]) =>
    form.setValue("class_groups", next, { shouldValidate: form.formState.isSubmitted });
  const setFile = (file: File | null) =>
    form.setValue("attachment", file, { shouldValidate: true });
  const onSubmit = form.handleSubmit((value) => {
    setGeneral(null);
    setDone(null);
    publish.mutate(value, {
      onSuccess: () => {
        form.reset(EMPTY);
        setDone(value.audience);
      },
      onError: (error) =>
        setGeneral(
          applyServerErrors(
            error,
            ["title", "body", "audience", "class_groups", "attachment"],
            form.setError,
            t,
          ),
        ),
    });
  });
  const names = new Map((classes.data ?? []).map((group) => [group.id, group.name]));
  const remaining = (classes.data ?? []).filter((group) => !chosen.includes(group.id));
  const toStaff = audience === "staff";
  const reached = toStaff ? recipients.data?.staff : recipients.data?.families;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("announcements.new")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)} noValidate>
          {done && (
            <Banner tone="ok">
              {t(done === "staff" ? "announcements.publishedStaff" : "announcements.published")}
            </Banner>
          )}
          {general && <Banner tone="due">{general}</Banner>}
          <Field
            id="announcement-title"
            label={t("announcements.titleLabel")}
            error={errors.title?.message}
          >
            {(control) => <Input {...control} maxLength={120} {...form.register("title")} />}
          </Field>
          <Field
            id="announcement-body"
            label={t("announcements.body")}
            error={errors.body?.message}
          >
            {(control) => (
              <Textarea
                {...control}
                maxLength={4000}
                className="min-h-32"
                {...form.register("body")}
              />
            )}
          </Field>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-bold">{t("announcements.audience")}</span>
            <Segmented
              label={t("announcements.audience")}
              value={audience}
              onValueChange={setAudience}
              options={[
                { value: "all_families", label: t("announcements.audiences.all_families") },
                { value: "class_groups", label: t("announcements.audiences.class_groups") },
                { value: "staff", label: t("announcements.audiences.staff") },
              ]}
            />
            {audience === "class_groups" && (
              <div
                className="flex flex-wrap items-center gap-1.5"
                aria-label={t("announcements.classesLabel")}
                role="group"
              >
                {chosen.map((id) => (
                  <Tag key={id} className="inline-flex items-center gap-1">
                    {names.get(id) ?? "…"}
                    <button
                      type="button"
                      className="rounded px-0.5 hover:bg-gray-100"
                      aria-label={t("announcements.removeClass", { name: names.get(id) ?? "" })}
                      onClick={() => setClasses(chosen.filter((other) => other !== id))}
                    >
                      ✕
                    </button>
                  </Tag>
                ))}
                {remaining.length > 0 && (
                  <Select
                    aria-label={t("announcements.classesLabel")}
                    className="h-8 w-auto min-w-0 py-0 text-xs font-bold"
                    value=""
                    onChange={(event) =>
                      event.target.value && setClasses([...chosen, event.target.value])
                    }
                  >
                    <option value="">{t("announcements.addClass")}</option>
                    {remaining.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </Select>
                )}
              </div>
            )}
            {errors.class_groups?.message && (
              <span className="text-sm text-due" role="alert">
                {errors.class_groups.message}
              </span>
            )}
          </div>
          <Field
            id="announcement-attachment"
            label={t("announcements.attachment")}
            help={t("announcements.attachmentHelp")}
            error={errors.attachment?.message}
          >
            {(control) => (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  {...control}
                  ref={fileInput}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    event.target.value = "";
                    if (file) setFile(file);
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="max-w-full min-w-0 truncate"
                  onClick={() => fileInput.current?.click()}
                >
                  {attachment ? attachment.name : t("announcements.chooseFile")}
                </Button>
                {attachment && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => setFile(null)}>
                    {t("announcements.removeAttachment")}
                  </Button>
                )}
              </div>
            )}
          </Field>
          <div className="flex gap-2.5">
            <Button type="button" variant="outline" onClick={() => setPreview(true)}>
              {t("announcements.preview")}
            </Button>
            <Button type="submit" className="flex-1" disabled={publish.isPending}>
              {reached === undefined || (audience === "class_groups" && chosen.length === 0)
                ? t("announcements.publish")
                : t(toStaff ? "announcements.publishForStaff" : "announcements.publishFor", {
                    count: reached,
                  })}
            </Button>
          </div>
        </form>
      </CardContent>
      <DialogRoot open={preview} onOpenChange={setPreview}>
        <DialogContent
          title={t("announcements.previewTitle")}
          footer={
            <DialogClose asChild>
              <Button variant="outline">{t("announcements.close")}</Button>
            </DialogClose>
          }
        >
          <AnnouncementPreview
            title={form.watch("title")}
            body={form.watch("body")}
            attachment={attachment?.name ?? null}
          />
        </DialogContent>
      </DialogRoot>
    </Card>
  );
}

function AnnouncementPreview({
  title,
  body,
  attachment,
}: {
  title: string;
  body: string;
  attachment: string | null;
}) {
  const { i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <article className="flex flex-col gap-2 rounded-[10px] border border-line p-4">
      <span className="text-sm text-ink-3">
        {school.name} · {formatDate(new Date().toISOString(), i18n.language, school.timezone)}
      </span>
      <b className="text-base">{title}</b>
      <p className="whitespace-pre-line text-ink-2">{body}</p>
      {attachment && <Tag className="self-start">{attachment}</Tag>}
    </article>
  );
}

function PublishedItem({ announcement }: { announcement: Announcement }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const archive = useArchive();
  const [confirm, setConfirm] = useState(false);
  const archived = announcement.archived_at !== null;
  const toStaff = announcement.audience === "staff";
  const recipients =
    announcement.audience === "class_groups"
      ? announcement.class_groups.map((group) => group.name).join(", ")
      : t(`announcements.audiences.${announcement.audience}`);
  const details = [
    recipients,
    formatDate(announcement.published_at, i18n.language, school.timezone),
    announcement.published_by &&
      t("announcements.by", { name: fullName(announcement.published_by) }),
    !toStaff && t("announcements.readBy", { count: announcement.read_by }),
  ].filter(Boolean);
  return (
    <div>
      <div className="min-w-0">
        <b>{announcement.title}</b>
        <div className="text-sm text-ink-3">{details.join(" · ")}</div>
        <div className="flex flex-wrap gap-x-4">
          {announcement.attachment && (
            <a
              className="text-sm font-bold text-lake underline"
              href={announcement.attachment}
              target="_blank"
              rel="noreferrer"
            >
              {t("announcements.pdf")}
            </a>
          )}
          <a
            className="text-sm font-bold text-lake underline"
            href={`/api/announcements/${announcement.id}/circular/`}
            target="_blank"
            rel="noreferrer"
          >
            {t("announcements.circular")}
          </a>
        </div>
        {archive.error && <div className="text-sm text-due">{errorMessage(archive.error, t)}</div>}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <StatusPill tone={archived ? "gray" : "ok"}>
          {t(archived ? "announcements.status.archived" : "announcements.status.published")}
        </StatusPill>
        {!archived && (
          <Button variant="ghost" size="sm" onClick={() => setConfirm(true)}>
            {t("announcements.archive")}
          </Button>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("announcements.archiveTitle", { title: announcement.title })}
        confirmLabel={t("announcements.archive")}
        cancelLabel={t("announcements.cancel")}
        pending={archive.isPending}
        onConfirm={() => archive.mutate(announcement.id, { onSuccess: () => setConfirm(false) })}
      >
        {t("announcements.archiveText")}
      </ConfirmDialog>
    </div>
  );
}
