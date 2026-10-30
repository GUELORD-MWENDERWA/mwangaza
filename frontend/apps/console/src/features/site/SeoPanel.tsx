// Titres de recherche (WEB.1c, SITE.1b) : une ligne par page publique et par langue, vide = le
// texte du logiciel. Compteur en direct (titre 60, description 160).
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
  Input,
  Segmented,
  Skeleton,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { keys } from "../../lib/queries";

type Page = Schemas["ConsoleSitePage"];
type Lang = "fr" | "en";
type Draft = Record<string, string>; // `<page>.<title|description>_<lang>` → texte

const TITLE_MAX = 60;
const DESCRIPTION_MAX = 160;

export function SeoPanel() {
  const { t } = useTranslation();
  const pages = useQuery({
    queryKey: keys.sitePages,
    queryFn: () => call(api.GET("/api/console/site/pages/")),
  });
  if (pages.isPending) return <Skeleton label={t("common.loading")} />;
  if (pages.isError) return <Banner tone="due">{errorMessage(pages.error, t)}</Banner>;
  return <SeoTable pages={pages.data} />;
}

function SeoTable({ pages }: { pages: Page[] }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [lang, setLang] = useState<Lang>("fr");
  const [draft, setDraft] = useState<Draft>({});
  const [saved, setSaved] = useState(false);
  const value = (page: Page, field: "title" | "description") => {
    const key = `${page.key}.${field}_${lang}`;
    return draft[key] ?? page[`${field}_${lang}`];
  };
  const save = useMutation({
    mutationFn: async () => {
      const changed = pages
        .map((page) => {
          const body: Record<string, string> = {};
          for (const [key, text] of Object.entries(draft)) {
            const [pageKey, field] = key.split(".");
            if (pageKey === page.key && field) body[field] = text;
          }
          return { page, body };
        })
        .filter(({ body }) => Object.keys(body).length > 0);
      for (const { page, body } of changed) {
        await call(
          api.PATCH("/api/console/site/pages/{key}/", {
            params: { path: { key: page.key } },
            body,
          }),
        );
      }
    },
    onSuccess: () => {
      setSaved(true);
      setDraft({});
      void queryClient.invalidateQueries({ queryKey: keys.sitePages });
    },
  });
  const error = save.error ? applyServerErrors(save.error, [], () => undefined, t) : null;

  return (
    <Card className="mt-4">
      <CardHeader className="flex-wrap gap-3">
        <CardTitle>{t("console.site.seo.title")}</CardTitle>
        <Segmented
          label={t("console.site.seo.language")}
          value={lang}
          onValueChange={setLang}
          options={[
            { value: "fr", label: t("console.site.languages.fr") },
            { value: "en", label: t("console.site.languages.en") },
          ]}
        />
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {saved && <Banner tone="ok">{t("console.site.saved")}</Banner>}
        {error && <Banner tone="due">{error}</Banner>}
        {pages.map((page) => {
          const title = value(page, "title");
          const description = value(page, "description");
          return (
            <section
              key={page.key}
              className="grid gap-3 border-t border-line pt-4 first:border-t-0 first:pt-0 min-[900px]:grid-cols-[10rem_minmax(0,1fr)_minmax(0,1.3fr)]"
            >
              <h3 className="font-bold">{t(`console.site.seo.pages.${page.key}`)}</h3>
              <div className="flex flex-col gap-1">
                <Input
                  aria-label={`${t("console.site.seo.titleLabel")} | ${t(`console.site.seo.pages.${page.key}`)}`}
                  maxLength={TITLE_MAX}
                  value={title}
                  placeholder={t("console.site.seo.default")}
                  onChange={(event) => {
                    setSaved(false);
                    setDraft({ ...draft, [`${page.key}.title_${lang}`]: event.target.value });
                  }}
                />
                <span className="text-xs text-ink-3">
                  {t("console.site.seo.count", { n: title.length, max: TITLE_MAX })}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <Textarea
                  aria-label={`${t("console.site.seo.descriptionLabel")} | ${t(`console.site.seo.pages.${page.key}`)}`}
                  maxLength={DESCRIPTION_MAX}
                  value={description}
                  className="min-h-16"
                  placeholder={t("console.site.seo.default")}
                  onChange={(event) => {
                    setSaved(false);
                    setDraft({
                      ...draft,
                      [`${page.key}.description_${lang}`]: event.target.value,
                    });
                  }}
                />
                <span className="text-xs text-ink-3">
                  {t("console.site.seo.count", { n: description.length, max: DESCRIPTION_MAX })}
                </span>
              </div>
            </section>
          );
        })}
      </CardContent>
      <CardFooter className="flex-wrap justify-between gap-3">
        <span className="text-sm text-ink-3">{t("console.site.seo.hint")}</span>
        <Button
          size="sm"
          disabled={save.isPending || Object.keys(draft).length === 0}
          onClick={() => save.mutate()}
        >
          {t("console.site.save")}
        </Button>
      </CardFooter>
    </Card>
  );
}
