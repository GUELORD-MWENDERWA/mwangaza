// Pièces communes aux écrans du site public de la console (témoignages, écoles de référence,
// articles, photothèque) : liste ordonnée, choix d'une photo, envoi d'un fichier.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  DialogClose,
  DialogContent,
  DialogRoot,
  Icon,
  Skeleton,
  StatusPill,
  Tag,
  cn,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { keys } from "../../lib/queries";

export type Photo = Schemas["ConsoleSitePhoto"];

export type Row = {
  id: string;
  title: string;
  sub?: string;
  published: boolean;
  note?: string;
};

/** Liste ordonnée par flèches (témoignages, écoles) : rang, titre, état, monter / descendre. */
export function RankedList({
  rows,
  selected,
  onEdit,
  onMove,
  moving,
  error,
  label,
}: {
  rows: Row[];
  selected?: string;
  onEdit: (id: string) => void;
  onMove: (id: string, direction: "up" | "down") => void;
  moving: boolean;
  error: unknown;
  label: string;
}) {
  const { t } = useTranslation();
  return (
    <ol aria-label={label}>
      {rows.map((row, index) => (
        <li
          key={row.id}
          className={cn(
            "flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-line px-4 py-3 first:border-t-0",
            selected === row.id && "bg-info-50",
          )}
        >
          <span className="w-6 shrink-0 text-right text-ink-3 tabular-nums">{index + 1}</span>
          <button
            type="button"
            className="min-w-48 flex-1 cursor-pointer text-left"
            onClick={() => onEdit(row.id)}
            aria-label={t("console.site.edit", { title: row.title })}
          >
            <b className="block break-words">{row.title}</b>
            {row.sub && <span className="block text-sm break-words text-ink-3">{row.sub}</span>}
            {row.note && <Tag className="mt-1">{row.note}</Tag>}
          </button>
          <span className="ml-auto flex shrink-0 items-center gap-0.5">
            <StatusPill tone={row.published ? "ok" : "gray"} className="mr-2">
              {t(row.published ? "console.site.published" : "console.site.draft")}
            </StatusPill>
            <Button
              variant="ghost"
              size="sm"
              aria-label={t("console.site.up", { title: row.title })}
              disabled={index === 0 || moving}
              onClick={() => onMove(row.id, "up")}
            >
              <Icon name="chevdown" className="rotate-180" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              aria-label={t("console.site.down", { title: row.title })}
              disabled={index === rows.length - 1 || moving}
              onClick={() => onMove(row.id, "down")}
            >
              <Icon name="chevdown" />
            </Button>
          </span>
          {index === rows.length - 1 && error != null && (
            <span className="basis-full text-sm text-due">{errorMessage(error, t)}</span>
          )}
        </li>
      ))}
    </ol>
  );
}

/** Une page de la photothèque (24 photos). */
export function usePhotos(page: number) {
  return useQuery({
    queryKey: [...keys.sitePhotos, page],
    queryFn: () => call(api.GET("/api/console/site/photos/", { params: { query: { page } } })),
    placeholderData: (previous) => previous,
  });
}

/** Vignette d'une photo de la photothèque, sans requête (`site_content.photo_url`). */
export const thumbnail = (id: string) => `/api/platform/photos/${id}-600.webp`;

/** Choix d'une photo de la photothèque : vignette, « Choisir… » ouvre la grille, « Retirer ». */
export function PhotoPicker({
  id,
  value,
  onChange,
  minWidth,
}: {
  id: string;
  value: string | null;
  onChange: (photo: string | null) => void;
  minWidth?: number;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const photos = usePhotos(page);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-card p-2.5">
      {value ? (
        <img
          src={thumbnail(value)}
          alt=""
          className="h-10.5 w-16 shrink-0 rounded-md object-cover"
        />
      ) : null}
      <span className="min-w-32 flex-1 text-sm text-ink-2">
        {t(value ? "console.photos.chosen" : "console.photos.none")}
      </span>
      <Button id={id} type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
        {t(value ? "console.photos.change" : "console.photos.choose")}
      </Button>
      {value && (
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange(null)}>
          {t("console.photos.remove")}
        </Button>
      )}
      <DialogRoot open={open} onOpenChange={setOpen}>
        <DialogContent
          title={t("console.photos.pick")}
          className="w-[min(860px,calc(100vw-32px))]"
          footer={
            <>
              <span className="mr-auto self-center text-sm text-ink-3">
                {photos.data
                  ? t("console.photos.page", {
                      page,
                      pages: Math.max(1, Math.ceil(photos.data.count / 24)),
                    })
                  : null}
              </span>
              <Button
                variant="outline"
                disabled={!photos.data?.previous}
                onClick={() => setPage(page - 1)}
              >
                {t("common.previous")}
              </Button>
              <Button
                variant="outline"
                disabled={!photos.data?.next}
                onClick={() => setPage(page + 1)}
              >
                {t("common.next")}
              </Button>
              <DialogClose asChild>
                <Button variant="outline">{t("common.cancel")}</Button>
              </DialogClose>
            </>
          }
        >
          {photos.isPending ? (
            <Skeleton label={t("common.loading")} />
          ) : photos.data?.results.length === 0 ? (
            <p className="text-ink-3">{t("console.photos.empty")}</p>
          ) : (
            <ul className="grid grid-cols-2 gap-3 min-[560px]:grid-cols-3">
              {photos.data?.results.map((photo) => {
                const small = minWidth !== undefined && photo.width < minWidth;
                return (
                  <li key={photo.id}>
                    <button
                      type="button"
                      disabled={small}
                      className={cn(
                        "flex w-full cursor-pointer flex-col gap-1 rounded-xl border border-line p-1.5 text-left text-sm hover:bg-info-50 disabled:cursor-not-allowed disabled:opacity-50",
                        photo.id === value && "border-lake bg-info-50",
                      )}
                      onClick={() => {
                        onChange(photo.id);
                        setOpen(false);
                      }}
                    >
                      <img
                        src={photo.small_url}
                        alt=""
                        className="aspect-3/2 w-full rounded-lg object-cover"
                      />
                      <b className="line-clamp-2">{photo.alt_fr}</b>
                      {small && (
                        <span className="text-xs text-due">
                          {t("console.photos.tooSmall", { width: minWidth })}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </DialogContent>
      </DialogRoot>
    </div>
  );
}

/** Choix d'un fichier (accord écrit) : nom du fichier choisi ou déposé, « Remplacer ». */
export function FilePicker({
  id,
  file,
  onFile,
  deposited,
  download,
  accept = "application/pdf,image/jpeg,image/png",
}: {
  id: string;
  file: File | null;
  onFile: (file: File | null) => void;
  deposited: boolean;
  download?: string;
  accept?: string;
}) {
  const { t } = useTranslation();
  const name =
    file?.name ?? (deposited ? t("console.site.consent.filed") : t("console.site.consent.none"));
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-card p-2.5">
      <span className="min-w-32 flex-1 text-sm break-all text-ink-2">{name}</span>
      {deposited && !file && download && (
        <a href={download} className="text-sm font-bold text-lake underline">
          {t("console.site.consent.download")}
        </a>
      )}
      <label
        htmlFor={id}
        className="cursor-pointer rounded-md px-2.5 py-1.5 text-sm font-bold text-lake hover:bg-info-50"
      >
        {t(deposited || file ? "console.site.consent.replace" : "console.site.consent.choose")}
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(event) => onFile(event.target.files?.[0] ?? null)}
      />
    </div>
  );
}

/** Message d'erreur général d'un envoi raté. */
export function Failure({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return error ? <Banner tone="due">{errorMessage(error, t)}</Banner> : null;
}
