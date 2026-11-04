import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Button,
  cn,
  Icon,
  Input,
  PanelContent,
  Sheet,
  SheetClose,
  SheetTrigger,
  Skeleton,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState, type MouseEvent, type ReactNode } from "react";

export type HelpApp = "gestion" | "portail" | "console";
type Article = Schemas["HelpArticle"];
type Item = Schemas["HelpItem"];

const WEEK = 60_000;

function useHelpList(app: HelpApp, lang: "fr" | "en", search: string, enabled: boolean) {
  return useQuery({
    queryKey: ["help", app, lang, "list", search],
    enabled,
    staleTime: WEEK,
    queryFn: () =>
      app === "console"
        ? call(api.GET("/api/console/help/", { params: { query: { lang, search } } }))
        : call(api.GET("/api/help/{app}/", { params: { path: { app }, query: { lang, search } } })),
  });
}

function useHelpArticle(app: HelpApp, lang: "fr" | "en", key: string | null, open: boolean) {
  return useQuery({
    queryKey: ["help", app, lang, "article", key],
    enabled: open && key !== null,
    staleTime: WEEK,
    queryFn: () =>
      app === "console"
        ? call(
            api.GET("/api/console/help/{key}/", {
              params: { path: { key: key! }, query: { lang } },
            }),
          )
        : call(
            api.GET("/api/help/{app}/{key}/", {
              params: { path: { app, key: key! }, query: { lang } },
            }),
          ),
  });
}

/** Style du texte rendu par le serveur (`markdown.py` : p, ul, ol, strong, `.tip`, `.hshot`). */
export const ARTICLE_TEXT =
  "text-sm text-ink-2 [&_a]:font-semibold [&_a]:text-lake [&_figcaption]:border-t [&_figcaption]:border-line-soft [&_figcaption]:bg-card [&_figcaption]:px-2.5 [&_figcaption]:py-1.5 [&_figcaption]:text-xs [&_figcaption]:text-ink-3 [&_figure]:mt-3 [&_figure]:overflow-hidden [&_figure]:rounded-[10px] [&_figure]:border [&_figure]:border-line [&_figure]:bg-surface [&_h2]:mt-4 [&_h2]:mb-1 [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-ink [&_h3]:mt-3 [&_h3]:font-bold [&_h3]:text-ink [&_img]:block [&_img]:h-auto [&_img]:max-h-40 [&_img]:w-full [&_img]:object-cover [&_img]:object-top-left [&_li]:py-0.5 [&_ol]:mt-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mt-2 [&_strong]:text-ink [&_ul]:mt-2 [&_ul]:list-disc [&_ul]:pl-5 [&_.tip]:mt-3 [&_.tip]:rounded-r-lg [&_.tip]:border-l-[3px] [&_.tip]:border-lake [&_.tip]:bg-lake-50 [&_.tip]:px-3 [&_.tip]:py-2.5 [&_.tip]:text-ink";

/** Les liens `#` de la console ne mènent nulle part : on les laisse sans effet. */
function ignoreAnchors(event: MouseEvent<HTMLElement>) {
  const link = (event.target as HTMLElement).closest("a");
  if (link?.getAttribute("href") === "#") event.preventDefault();
}

function ItemLink({ item, onOpen }: { item: Item; onOpen: (key: string) => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(item.key)}
        className="flex min-h-11 w-full cursor-pointer items-center justify-between gap-2.5 border-t border-line-soft py-2.5 text-left text-sm font-semibold text-ink [&_mark]:rounded-[3px] [&_mark]:bg-lamp-soft [&_mark]:px-0.5 [&_mark]:text-inherit"
      >
        <span className="min-w-0">
          <span dangerouslySetInnerHTML={{ __html: item.title_html }} />
          <small
            className="block text-xs font-normal text-ink-3"
            dangerouslySetInnerHTML={{ __html: item.excerpt_html }}
          />
        </span>
        <Icon name="chevron" size={16} className="shrink-0 text-ink-3" />
      </button>
    </li>
  );
}

function ArticleView({
  article,
  onScreen,
  app,
  onOpen,
}: {
  article: Article;
  onScreen: boolean;
  app: HelpApp;
  onOpen: (key: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <span className="text-xs font-bold tracking-wider text-ink-3 uppercase">
        {onScreen ? t("help.onScreen", { group: article.group_label }) : article.group_label}
      </span>
      <article>
        <h2 className="text-lg font-bold tracking-tight">{article.title}</h2>
        <p className="mt-1.5 text-sm text-ink-2">{article.summary}</p>
        <div
          className={ARTICLE_TEXT}
          onClick={ignoreAnchors}
          dangerouslySetInnerHTML={{ __html: article.html }}
        />
      </article>
      {article.url && app !== "console" && (
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-10 items-center gap-1.5 self-start rounded-field border border-field bg-card px-3 text-sm font-semibold text-ink no-underline shadow-button"
        >
          {t("help.readFull")}
          <Icon name="chevron" size={14} />
        </a>
      )}
      {article.related.length > 0 && (
        <>
          <span className="text-xs font-bold tracking-wider text-ink-3 uppercase">
            {t("help.related")}
          </span>
          <ul className="m-0 list-none p-0">
            {article.related.map((item) => (
              <ItemLink key={item.key} item={item} onOpen={onOpen} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

/** Bouton « Aide » de la barre du haut et son panneau (maquette `aide-panneau`) : l'article de
 *  l'écran ouvert (`screen`), la recherche, les articles liés ; `footer` : ce que l'application
 *  ajoute en bas (écrire au support, revoir le guide), reçoit la fermeture du panneau. */
export function HelpButton({
  app,
  screen,
  footer,
  className,
}: {
  app: HelpApp;
  screen: string | null;
  footer?: (close: () => void) => ReactNode;
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.startsWith("en") ? "en" : "fr";
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search.trim());
  const searching = deferred.length >= 2;
  const key = picked ?? screen;
  const article = useHelpArticle(app, lang, searching ? null : key, open);
  const list = useHelpList(
    app,
    lang,
    searching ? deferred : "",
    open && (searching || key === null),
  );
  const close = () => setOpen(false);

  const change = (next: boolean) => {
    setOpen(next);
    if (next) {
      setPicked(null);
      setSearch("");
    }
  };
  const openArticle = (next: string) => {
    setSearch("");
    setPicked(next);
  };

  return (
    <Sheet open={open} onOpenChange={change}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label={t("help.button")}
          className={cn(
            "inline-flex h-10 min-w-11 cursor-pointer items-center justify-center gap-1.5 rounded-[10px] border border-line bg-card px-2.5 text-sm font-semibold whitespace-nowrap text-ink-2 hover:border-ink-3 min-[900px]:px-3",
            className,
          )}
        >
          <Icon name="help" size={18} />
          <span className="max-[899px]:hidden">{t("help.button")}</span>
        </button>
      </SheetTrigger>
      <PanelContent title={t("help.title")}>
        <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
          <Icon name="help" size={20} className="text-lake" />
          <b className="text-lg">{t("help.title")}</b>
          <SheetClose className="ml-auto grid size-11 cursor-pointer place-items-center rounded-lg text-ink-2">
            <Icon name="x" />
            <span className="sr-only">{t("help.close")}</span>
          </SheetClose>
        </div>
        <div className="border-b border-line-soft px-4 py-3">
          <Input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("help.searchPlaceholder")}
            aria-label={t("help.search")}
          />
        </div>
        <div className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-4">
          {picked !== null && !searching && (
            <Button
              variant="ghost"
              size="sm"
              className="self-start"
              onClick={() => setPicked(null)}
            >
              {screen ? t("help.backToScreen") : t("help.backToList")}
            </Button>
          )}
          {searching || (key === null && !article.data) ? (
            list.isPending ? (
              <Skeleton label={t("common.loading")} />
            ) : list.isError ? (
              <p role="alert" className="text-sm text-due">
                {errorMessage(list.error, t)}
              </p>
            ) : list.data.articles.length === 0 ? (
              <p className="text-sm text-ink-2">{t("help.noResults")}</p>
            ) : (
              <ul className="m-0 list-none p-0">
                {list.data.articles.map((item) => (
                  <ItemLink key={item.key} item={item} onOpen={openArticle} />
                ))}
              </ul>
            )
          ) : article.isPending ? (
            <Skeleton label={t("common.loading")} />
          ) : article.isError ? (
            <p role="alert" className="text-sm text-due">
              {t("help.unavailable")}
            </p>
          ) : (
            <ArticleView
              article={article.data}
              onScreen={key === screen}
              app={app}
              onOpen={openArticle}
            />
          )}
        </div>
        {footer && (
          <div className="flex flex-col gap-2 border-t border-line bg-surface px-4 py-3">
            {footer(close)}
          </div>
        )}
      </PanelContent>
    </Sheet>
  );
}
