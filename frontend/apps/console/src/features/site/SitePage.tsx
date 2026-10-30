// Contenus du site public (SITE.1a, maquette `console/site`) : questions fréquentes (accueil,
// parents), « Prochainement » et bandeau d'annonce, tenus par la communication. À gauche la liste
// (rang, état, monter / descendre), à droite l'éditeur en français et en anglais avec l'aperçu
// du site. Le serveur note chaque changement au journal et vide le cache du site.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Tag,
  Textarea,
  buttonVariants,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { BannerPanel } from "./BannerPanel";
import { PartnersPanel } from "./PartnersPanel";
import { PlansPanel } from "./PlansPanel";
import { ReferencesPanel } from "./ReferencesPanel";
import { SeoPanel } from "./SeoPanel";
import { SocialPanel } from "./SocialPanel";
import { TestimonialsPanel } from "./TestimonialsPanel";

type Entry = Schemas["ConsoleSiteEntry"];
type Kind = Schemas["ConsoleSiteEntryKindEnum"];
type Values = Pick<Entry, "title_fr" | "title_en" | "text_fr" | "text_en" | "published">;

const MAX_PER_KIND = 20; // comme le serveur (`SiteEntry.MAX_PER_KIND`)
const EMPTY: Values = { title_fr: "", title_en: "", text_fr: "", text_en: "", published: false };
const TABS = [
  "questions",
  "upcoming",
  "banner",
  "testimonials",
  "references",
  "plans",
  "partners",
  "seo",
  "social",
] as const;

/** Le site public : la même adresse sans `admin.` ; en développement, Django le sert (:8000). */
export function siteAddress(): string {
  const { protocol, hostname, port } = window.location;
  const shown = import.meta.env.DEV ? "8000" : port;
  return `${protocol}//${hostname.replace(/^admin\./, "")}${shown ? `:${shown}` : ""}/`;
}

export function SitePage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<(typeof TABS)[number]>("questions");
  const entries = useQuery({
    queryKey: keys.siteEntries,
    queryFn: () => call(api.GET("/api/console/site/entries/")),
  });
  const body = (kinds: [Kind, ...Kind[]]) =>
    entries.isPending ? (
      <Skeleton label={t("common.loading")} />
    ) : entries.isError ? (
      <Banner tone="due">{errorMessage(entries.error, t)}</Banner>
    ) : (
      <EntriesPanel kinds={kinds} entries={entries.data} />
    );

  return (
    <>
      <PageHeader
        title={t("console.site.title")}
        subtitle={t("console.site.subtitle")}
        actions={
          <a
            href={siteAddress()}
            target="_blank"
            rel="noopener"
            className={buttonVariants({ variant: "outline" })}
          >
            {t("console.site.open")} ↗
          </a>
        }
      />
      <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
        <TabsList aria-label={t("console.site.title")}>
          {TABS.map((value) => (
            <TabsTrigger key={value} value={value}>
              {t(`console.site.tabs.${value}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="questions">{body(["home_question", "parent_question"])}</TabsContent>
        <TabsContent value="upcoming">{body(["upcoming"])}</TabsContent>
        <TabsContent value="banner">
          <BannerPanel />
        </TabsContent>
        <TabsContent value="testimonials">
          <TestimonialsPanel />
        </TabsContent>
        <TabsContent value="references">
          <ReferencesPanel />
        </TabsContent>
        <TabsContent value="plans">
          <PlansPanel />
        </TabsContent>
        <TabsContent value="partners">
          <PartnersPanel />
        </TabsContent>
        <TabsContent value="seo">
          <SeoPanel />
        </TabsContent>
        <TabsContent value="social">
          <SocialPanel />
        </TabsContent>
      </Tabs>
    </>
  );
}

function EntriesPanel({ kinds, entries }: { kinds: [Kind, ...Kind[]]; entries: Entry[] }) {
  const { t } = useTranslation();
  const [kind, setKind] = useState<Kind>(kinds[0]);
  const [editing, setEditing] = useState<Entry | null>(null);
  const editor = useRef<HTMLDivElement>(null);
  const list = entries.filter((entry) => entry.kind === kind);
  const group = kind === "upcoming" ? "upcoming" : "questions";
  const edit = (entry: Entry | null) => {
    setEditing(entry);
    editor.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <CardTitle>{t(`console.site.lists.${group}`)}</CardTitle>
          {kinds.length > 1 && (
            <Segmented
              label={t("console.site.page")}
              value={kind}
              onValueChange={(value) => {
                setKind(value);
                setEditing(null);
              }}
              options={kinds.map((value) => ({
                value,
                label: t(`console.site.kinds.${value}`, {
                  n: entries.filter((entry) => entry.kind === value).length,
                }),
              }))}
            />
          )}
        </CardHeader>
        {list.length === 0 ? (
          <CardContent>
            <p className="text-ink-3">{t(`console.site.empty.${group}`)}</p>
          </CardContent>
        ) : (
          <ol aria-label={t(`console.site.kinds.${kind}`, { n: list.length })}>
            {list.map((entry, index) => (
              <EntryRow
                key={entry.id}
                entry={entry}
                rank={index + 1}
                last={index === list.length - 1}
                selected={editing?.id === entry.id}
                onEdit={() => edit(entry)}
              />
            ))}
          </ol>
        )}
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">
            {t(`console.site.count.${group}`, { count: list.length, max: MAX_PER_KIND })}
          </span>
          <Button size="sm" disabled={list.length >= MAX_PER_KIND} onClick={() => edit(null)}>
            <Icon name="plus" /> {t(`console.site.add.${group}`)}
          </Button>
        </CardFooter>
      </Card>
      <div ref={editor} className="scroll-mt-4">
        <EntryEditor
          key={editing?.id ?? `new-${kind}`}
          kind={kind}
          entry={editing}
          onDone={() => setEditing(null)}
        />
      </div>
    </div>
  );
}

function EntryRow({
  entry,
  rank,
  last,
  selected,
  onEdit,
}: {
  entry: Entry;
  rank: number;
  last: boolean;
  selected: boolean;
  onEdit: () => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const move = useMutation({
    mutationFn: (direction: "up" | "down") =>
      call(
        api.POST("/api/console/site/entries/{id}/move/", {
          params: { path: { id: entry.id } },
          body: { direction },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.siteEntries }),
  });
  return (
    <li
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line px-4 py-3 first:border-t-0",
        selected && "bg-info-50",
      )}
    >
      <span className="w-6 shrink-0 text-right text-ink-3 tabular-nums">{rank}</span>
      <button
        type="button"
        className="min-w-48 flex-1 cursor-pointer text-left"
        onClick={onEdit}
        aria-label={t("console.site.edit", { title: entry.title_fr })}
      >
        <b className="block break-words">{entry.title_fr}</b>
        {entry.title_en ? (
          <span className="block text-sm text-ink-3">{entry.title_en}</span>
        ) : (
          <Tag className="mt-1">{t("console.site.noEnglish")}</Tag>
        )}
        {move.isError && (
          <span className="block text-sm text-due">{errorMessage(move.error, t)}</span>
        )}
      </button>
      <span className="ml-auto flex shrink-0 items-center gap-0.5">
        <StatusPill tone={entry.published ? "ok" : "gray"} className="mr-2">
          {t(entry.published ? "console.site.published" : "console.site.draft")}
        </StatusPill>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("console.site.up", { title: entry.title_fr })}
          disabled={rank === 1 || move.isPending}
          onClick={() => move.mutate("up")}
        >
          <Icon name="chevdown" className="rotate-180" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("console.site.down", { title: entry.title_fr })}
          disabled={last || move.isPending}
          onClick={() => move.mutate("down")}
        >
          <Icon name="chevdown" />
        </Button>
      </span>
    </li>
  );
}

function EntryEditor({
  kind,
  entry,
  onDone,
}: {
  kind: Kind;
  entry: Entry | null;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const group = kind === "upcoming" ? "upcoming" : "questions";
  const required = t("fieldErrors.required");
  const schema = z.object({
    title_fr: z.string().trim().min(1, required).max(160),
    title_en: z.string().trim().max(160),
    text_fr: z.string().trim().min(1, required).max(1500),
    text_en: z.string().trim().max(1500),
    published: z.boolean(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: entry ?? EMPTY,
  });
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const fields: (keyof Values)[] = ["title_fr", "title_en", "text_fr", "text_en", "published"];
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.siteEntries });
  const save = useMutation({
    mutationFn: (values: Values) =>
      entry
        ? call(
            api.PATCH("/api/console/site/entries/{id}/", {
              params: { path: { id: entry.id } },
              body: values,
            }),
          )
        : call(api.POST("/api/console/site/entries/", { body: { ...values, kind } })),
    onSuccess: () => {
      setSaved(true);
      if (!entry) form.reset(EMPTY);
      refresh();
    },
    onError: (error) => setGeneral(applyServerErrors(error, fields, form.setError, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/entries/{id}/", {
          params: { path: { id: entry?.id ?? "" } },
        }),
      ),
    onSuccess: () => {
      setConfirm(false);
      refresh();
      onDone();
    },
  });
  const onSubmit = form.handleSubmit((values) => {
    setGeneral(null);
    setSaved(false);
    save.mutate(values);
  });
  const preview = useWatch({ control: form.control });
  const label = (field: "title" | "text") => t(`console.site.fields.${group}.${field}`);

  return (
    <Card>
      <CardHeader className="flex-wrap gap-2">
        <CardTitle>{t(`console.site.${entry ? "editTitle" : "newTitle"}.${group}`)}</CardTitle>
        {entry && (
          <span className="text-sm text-ink-3">
            {t("console.site.changed", {
              date: formatDay(entry.updated_at.slice(0, 10), i18n.language),
            })}
          </span>
        )}
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={(event) => void onSubmit(event)} noValidate>
          {saved && <Banner tone="ok">{t("console.site.saved")}</Banner>}
          {general && <Banner tone="due">{general}</Banner>}
          {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 min-[1300px]:grid-cols-2">
            {(["fr", "en"] as const).map((lang) => (
              <fieldset key={lang} className="flex min-w-0 flex-col gap-3">
                <legend className="mb-3 text-sm font-bold tracking-wide text-ink-3 uppercase">
                  {t(`console.site.languages.${lang}`)}
                </legend>
                <Field
                  id={`entry-title-${lang}`}
                  label={label("title")}
                  error={errors[`title_${lang}`]?.message}
                >
                  {(control) => (
                    <Input {...control} maxLength={160} {...form.register(`title_${lang}`)} />
                  )}
                </Field>
                <Field
                  id={`entry-text-${lang}`}
                  label={label("text")}
                  error={errors[`text_${lang}`]?.message}
                >
                  {(control) => (
                    <Textarea
                      {...control}
                      maxLength={1500}
                      className="min-h-32"
                      {...form.register(`text_${lang}`)}
                    />
                  )}
                </Field>
                {lang === "en" && (
                  <span className="text-sm text-ink-3">{t("console.site.englishHint")}</span>
                )}
              </fieldset>
            ))}
          </div>
          <CheckboxField
            id="entry-published"
            checked={preview.published}
            onCheckedChange={(checked) => form.setValue("published", checked === true)}
            label={
              <>
                <b>{t("console.site.publish")}</b>
                <span className="block text-sm text-ink-3">{t("console.site.draftHint")}</span>
              </>
            }
          />
          <div className="flex flex-col gap-1.5">
            <b className="text-sm">{t("console.site.preview")}</b>
            <div className="rounded-xl border border-dashed border-line bg-surface p-3.5">
              {group === "questions" ? (
                <details open className="rounded-xl border border-line bg-card">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 font-bold">
                    {preview.title_fr || t("console.site.fields.questions.title")}
                    <Icon name="chevdown" className="text-lake" />
                  </summary>
                  <p className="px-4 pb-3.5 whitespace-pre-line text-ink-2">{preview.text_fr}</p>
                </details>
              ) : (
                <div className="flex max-w-90 flex-col gap-1.5 rounded-xl border border-line bg-card p-4">
                  <span className="self-start rounded-md bg-lamp-soft px-2 py-0.5 text-sm font-semibold text-lamp-900">
                    {t("console.site.comingSoon")}
                  </span>
                  <b>{preview.title_fr || t("console.site.fields.upcoming.title")}</b>
                  <span className="whitespace-pre-line text-ink-2">{preview.text_fr}</span>
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-wrap justify-between gap-2">
            {entry ? (
              <Button type="button" variant="destructive-outline" onClick={() => setConfirm(true)}>
                {t("console.site.delete")}
              </Button>
            ) : (
              <span />
            )}
            <span className="flex gap-2">
              {entry && (
                <Button type="button" variant="outline" onClick={onDone}>
                  {t("common.cancel")}
                </Button>
              )}
              <Button type="submit" disabled={save.isPending}>
                {t("console.site.save")}
              </Button>
            </span>
          </div>
        </form>
      </CardContent>
      {entry && (
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={t("console.site.deleteTitle", { title: entry.title_fr })}
          confirmLabel={t("console.site.delete")}
          cancelLabel={t("common.cancel")}
          pending={remove.isPending}
          onConfirm={() => remove.mutate()}
        >
          {t("console.site.deleteText")}
        </ConfirmDialog>
      )}
    </Card>
  );
}
