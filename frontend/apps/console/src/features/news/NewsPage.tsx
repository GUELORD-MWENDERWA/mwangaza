// Actualités du site public (SITE.2, maquette `console/actualites`) : liste filtrée et paginée,
// éditeur (petit Markdown) et aperçu rendu par le serveur avec le même code que le site. Un article
// publié à une date future est « programmé » : il paraît seul à sa date.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Textarea,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { PhotoPicker, thumbnail } from "../site/shared";

type Article = Schemas["ConsoleArticle"];
type State = "all" | "published" | "scheduled" | "draft";
type Values = {
  language: "fr" | "en";
  author_name: string;
  title: string;
  summary: string;
  body: string;
  status: "draft" | "published";
  published_at: string; // heure locale `AAAA-MM-JJTHH:MM`, vide = maintenant à la publication
};

const TONES = { published: "ok", scheduled: "info", draft: "gray" } as const;
const FIELDS: (keyof Values)[] = [
  "language",
  "author_name",
  "title",
  "summary",
  "body",
  "status",
  "published_at",
];

const toLocal = (iso: string | null) => {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const blank = (language: "fr" | "en"): Values => ({
  language,
  author_name: "",
  title: "",
  summary: "",
  body: "",
  status: "draft",
  published_at: "",
});

export function NewsPage() {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<State>("all");
  const [language, setLanguage] = useState<"all" | "fr" | "en">("all");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Article | null>(null);
  const counts = useQuery({
    queryKey: [...keys.siteArticles, "counts"],
    queryFn: () => call(api.GET("/api/console/site/articles/counts/")),
  });
  const list = useQuery({
    queryKey: [...keys.siteArticles, state, language, page],
    queryFn: () =>
      call(
        api.GET("/api/console/site/articles/", {
          params: {
            query: {
              page,
              ...(state === "all" ? {} : { state }),
              ...(language === "all" ? {} : { language }),
            },
          },
        }),
      ),
    placeholderData: (previous) => previous,
  });
  const when = new Intl.DateTimeFormat(i18n.language, { dateStyle: "short", timeStyle: "short" });
  const n = (key: State) => counts.data?.[key === "all" ? "all" : key] ?? 0;

  return (
    <>
      <PageHeader
        title={t("console.news.title")}
        subtitle={t("console.news.subtitle")}
        actions={<Button onClick={() => setEditing(null)}>{t("console.news.add")}</Button>}
      />
      <div className="flex flex-wrap gap-3">
        <Segmented
          label={t("console.news.state")}
          value={state}
          onValueChange={(value) => {
            setState(value);
            setPage(1);
          }}
          options={(["all", "published", "scheduled", "draft"] as const).map((value) => ({
            value,
            label: t(`console.news.states.${value}`, { n: n(value) }),
          }))}
        />
        <Segmented
          label={t("console.news.language")}
          value={language}
          onValueChange={(value) => {
            setLanguage(value);
            setPage(1);
          }}
          options={[
            { value: "all", label: t("console.news.allLanguages") },
            { value: "fr", label: t("console.site.languages.fr") },
            { value: "en", label: t("console.site.languages.en") },
          ]}
        />
      </div>
      <Card className="mt-4">
        {list.isPending ? (
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        ) : list.isError ? (
          <CardContent>
            <Banner tone="due">{errorMessage(list.error, t)}</Banner>
          </CardContent>
        ) : list.data.results.length === 0 ? (
          <CardContent>
            <p className="text-ink-3">{t("console.news.empty")}</p>
          </CardContent>
        ) : (
          <ul>
            {list.data.results.map((article) => (
              <li
                key={article.id}
                className={cn(
                  "border-t border-line first:border-t-0",
                  editing?.id === article.id && "bg-info-50",
                )}
              >
                <button
                  type="button"
                  className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-4 py-3 text-left min-[820px]:grid-cols-[minmax(0,1fr)_3rem_8rem_10rem_9rem]"
                  onClick={() => setEditing(article)}
                  aria-label={t("console.site.edit", { title: article.title })}
                >
                  <span className="min-w-0">
                    <b className="block break-words">{article.title}</b>
                    <span className="block text-sm break-all text-ink-3">
                      {article.url ?? t("console.news.noAddress")}
                    </span>
                  </span>
                  <span className="text-sm font-bold uppercase text-ink-2">{article.language}</span>
                  <StatusPill tone={TONES[article.state]} className="justify-self-start">
                    {t(`console.news.pill.${article.state}`)}
                  </StatusPill>
                  <span className="text-sm text-ink-2">
                    {article.published_at ? when.format(new Date(article.published_at)) : "—"}
                  </span>
                  <span className="text-sm text-ink-3">
                    {article.updated_by
                      ? `${article.updated_by.first_name} ${article.updated_by.last_name}`
                      : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">
            {t("console.news.page", {
              page,
              pages: Math.max(1, Math.ceil((list.data?.count ?? 0) / 20)),
            })}
          </span>
          <span className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!list.data?.previous}
              onClick={() => setPage(page - 1)}
            >
              {t("common.previous")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!list.data?.next}
              onClick={() => setPage(page + 1)}
            >
              {t("common.next")}
            </Button>
          </span>
        </CardFooter>
      </Card>
      <ArticleEditor
        key={editing?.id ?? "new"}
        article={editing}
        defaultLanguage={i18n.language === "en" ? "en" : "fr"}
        onSaved={setEditing}
        onDone={() => setEditing(null)}
      />
    </>
  );
}

function ArticleEditor({
  article,
  defaultLanguage,
  onSaved,
  onDone,
}: {
  article: Article | null;
  defaultLanguage: "fr" | "en";
  onSaved: (article: Article) => void;
  onDone: () => void;
}) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const required = t("fieldErrors.required");
  const schema = z.object({
    language: z.enum(["fr", "en"]),
    author_name: z.string().trim().max(80),
    title: z.string().trim().min(1, required).max(120),
    summary: z.string().trim().min(1, required).max(200),
    body: z.string().trim().min(1, required).max(20000),
    status: z.enum(["draft", "published"]),
    published_at: z.string(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: article
      ? {
          language: article.language,
          author_name: article.author_name,
          title: article.title,
          summary: article.summary,
          body: article.body,
          status: article.status,
          published_at: toLocal(article.published_at),
        }
      : blank(defaultLanguage),
  });
  const [photo, setPhoto] = useState<string | null>(article?.photo ?? null);
  const [general, setGeneral] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const values = useWatch({ control: form.control }) as Values;
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.siteArticles });

  const save = useMutation({
    mutationFn: (v: Values) => {
      const body = {
        ...v,
        photo,
        published_at: v.published_at ? new Date(v.published_at).toISOString() : null,
      };
      return article
        ? call(
            api.PATCH("/api/console/site/articles/{id}/", {
              params: { path: { id: article.id } },
              body,
            }),
          )
        : call(api.POST("/api/console/site/articles/", { body }));
    },
    onSuccess: (saved_) => {
      setSaved(true);
      refresh();
      onSaved(saved_);
    },
    onError: (error) => setGeneral(applyServerErrors(error, FIELDS, form.setError, t)),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/articles/{id}/", {
          params: { path: { id: article?.id ?? "" } },
        }),
      ),
    onSuccess: () => {
      setConfirm(false);
      refresh();
      onDone();
    },
  });

  // L'aperçu vient du serveur (même code que le site), 400 ms après la dernière frappe.
  const [body, setBody] = useState(values.body);
  useEffect(() => {
    const timer = setTimeout(() => setBody(values.body), 400);
    return () => clearTimeout(timer);
  }, [values.body]);
  const preview = useQuery({
    queryKey: [...keys.siteArticles, "preview", body],
    queryFn: () => call(api.POST("/api/console/site/articles/preview/", { body: { body } })),
    enabled: body.trim().length > 0,
    placeholderData: (previous) => previous,
  });
  const scheduled =
    values.status === "published" && values.published_at
      ? new Date(values.published_at) > new Date()
      : false;
  const day = values.published_at
    ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "long" }).format(
        new Date(values.published_at),
      )
    : null;

  return (
    <div className="mt-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-2">
      <Card>
        <CardHeader className="flex-wrap gap-2">
          <CardTitle>{t(article ? "console.news.editTitle" : "console.news.newTitle")}</CardTitle>
          {article && (
            <StatusPill tone={TONES[article.state]}>
              {t(`console.news.pill.${article.state}`)}
            </StatusPill>
          )}
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              setGeneral(null);
              setSaved(false);
              void form.handleSubmit((v) => save.mutate(v))(event);
            }}
            noValidate
          >
            {saved && <Banner tone="ok">{t("console.site.saved")}</Banner>}
            {general && <Banner tone="due">{general}</Banner>}
            {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
            <div className="grid gap-4 min-[560px]:grid-cols-2">
              <Field
                id="article-language"
                label={t("console.news.fields.language")}
                help={article?.slug ? t("console.news.languageFixed") : undefined}
                error={errors.language?.message}
              >
                {(control) => (
                  <Select
                    {...control}
                    disabled={Boolean(article?.slug)}
                    {...form.register("language")}
                  >
                    <option value="fr">{t("console.site.languages.fr")}</option>
                    <option value="en">{t("console.site.languages.en")}</option>
                  </Select>
                )}
              </Field>
              <Field
                id="article-author_name"
                label={t("console.news.fields.author_name")}
                error={errors.author_name?.message}
              >
                {(control) => (
                  <Input {...control} maxLength={80} {...form.register("author_name")} />
                )}
              </Field>
            </div>
            <Field
              id="article-title"
              label={t("console.news.fields.title")}
              required
              help={t("console.news.titleHelp", {
                n: values.title.length,
                url: article?.url ?? t("console.news.noAddress"),
              })}
              error={errors.title?.message}
            >
              {(control) => <Input {...control} maxLength={120} {...form.register("title")} />}
            </Field>
            <Field
              id="article-summary"
              label={t("console.news.fields.summary")}
              required
              help={t("console.news.summaryHelp", { n: values.summary.length })}
              error={errors.summary?.message}
            >
              {(control) => (
                <Textarea
                  {...control}
                  maxLength={200}
                  className="min-h-16"
                  {...form.register("summary")}
                />
              )}
            </Field>
            <Field
              id="article-body"
              label={t("console.news.fields.body")}
              required
              error={errors.body?.message}
            >
              {(control) => (
                <Textarea
                  {...control}
                  maxLength={20000}
                  className="min-h-56 font-mono text-sm"
                  {...form.register("body")}
                />
              )}
            </Field>
            <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3">
              <code>## {t("console.news.md.heading")}</code>
              <code>- {t("console.news.md.list")}</code>
              <code>**{t("console.news.md.bold")}**</code>
              <code>[{t("console.news.md.text")}](https://…)</code>
              <span>{t("console.news.md.paragraph")}</span>
            </p>
            <Field id="article-photo" label={t("console.news.fields.photo")}>
              {(control) => <PhotoPicker id={control.id} value={photo} onChange={setPhoto} />}
            </Field>
            <div className="grid gap-4 min-[560px]:grid-cols-2">
              <Field
                id="article-status"
                label={t("console.news.fields.status")}
                error={errors.status?.message}
              >
                {(control) => (
                  <Select {...control} {...form.register("status")}>
                    <option value="draft">{t("console.news.pill.draft")}</option>
                    <option value="published">{t("console.news.pill.published")}</option>
                  </Select>
                )}
              </Field>
              <Field
                id="article-published_at"
                label={t("console.news.fields.published_at")}
                help={t("console.news.dateHelp")}
                error={errors.published_at?.message}
              >
                {(control) => (
                  <Input {...control} type="datetime-local" {...form.register("published_at")} />
                )}
              </Field>
            </div>
            {scheduled && <Banner tone="info">{t("console.news.willAppear")}</Banner>}
            <div className="flex flex-wrap justify-between gap-2">
              {article ? (
                <Button
                  type="button"
                  variant="destructive-outline"
                  onClick={() => setConfirm(true)}
                >
                  {t("console.site.delete")}
                </Button>
              ) : (
                <span />
              )}
              <span className="flex gap-2">
                {article && (
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
        {article && (
          <ConfirmDialog
            open={confirm}
            onOpenChange={setConfirm}
            title={t("console.site.deleteTitle", { title: article.title })}
            confirmLabel={t("console.site.delete")}
            cancelLabel={t("common.cancel")}
            pending={remove.isPending}
            onConfirm={() => remove.mutate()}
          >
            {t("console.news.deleteText")}
          </ConfirmDialog>
        )}
      </Card>
      <Card>
        <CardHeader className="flex-wrap gap-2">
          <CardTitle>{t("console.news.preview")}</CardTitle>
          <span className="text-sm text-ink-3">{t("console.news.previewHint")}</span>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <span className="text-sm text-ink-3">
            {[
              day,
              values.author_name || t("console.news.defaultAuthor"),
              preview.data ? t("console.news.minutes", { count: preview.data.minutes }) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
          <h2 className="text-2xl font-bold tracking-tight break-words">
            {values.title || t("console.news.fields.title")}
          </h2>
          <p className="text-ink-2">{values.summary}</p>
          {photo && (
            <img
              src={thumbnail(photo)}
              alt=""
              className="aspect-2/1 w-full rounded-xl object-cover"
            />
          )}
          {preview.data && (
            <div
              className="flex flex-col gap-3 break-words [&_a]:text-lake [&_a]:underline [&_h2]:mt-2 [&_h2]:text-xl [&_h2]:font-bold [&_h3]:font-bold [&_li]:ml-5 [&_li]:list-disc [&_strong]:font-bold"
              // Rendu par le serveur : tout texte saisi y est échappé (`core/markdown.py`).
              dangerouslySetInnerHTML={{ __html: preview.data.html }}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
