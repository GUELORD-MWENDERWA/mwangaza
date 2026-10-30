// Photothèque du site public (SITE.3, maquette `console/photos`) : photos du haut des pages, photos
// envoyées (réduites et nettoyées par le serveur), envoi avec licence, crédit et accord écrit.
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
  CheckboxField,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Tag,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { FilePicker, PhotoPicker, thumbnail, usePhotos, type Photo } from "../site/shared";

type Page = Schemas["ConsoleSitePage"];
type Values = {
  alt_fr: string;
  alt_en: string;
  credit: string;
  license: Photo["license"];
  recognizable: boolean;
};

const LICENSES: Photo["license"][] = ["cc0", "public_domain", "cc_by", "cc_by_sa", "consent"];
const MIN_WIDTH = 1200; // largeur d'une photo du haut d'une page (`SitePage.PHOTO_MIN_WIDTH`)

export function PhotosPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Photo | "new" | null>(null);
  const photos = usePhotos(page);

  return (
    <>
      <PageHeader
        title={t("console.photos.title")}
        subtitle={t("console.photos.subtitle")}
        actions={<Button onClick={() => setEditing("new")}>{t("console.photos.upload")}</Button>}
      />
      <Slots />
      <Card className="mt-4">
        <CardHeader className="flex-wrap gap-2">
          <CardTitle>{t("console.photos.sent")}</CardTitle>
          <span className="text-sm text-ink-3">
            {t("console.photos.count", { count: photos.data?.count ?? 0 })}
          </span>
        </CardHeader>
        <CardContent>
          {photos.isPending ? (
            <Skeleton label={t("common.loading")} />
          ) : photos.isError ? (
            <Banner tone="due">{errorMessage(photos.error, t)}</Banner>
          ) : photos.data.results.length === 0 ? (
            <p className="text-ink-3">{t("console.photos.empty")}</p>
          ) : (
            <ul className="grid grid-cols-1 gap-4 min-[560px]:grid-cols-2 min-[1100px]:grid-cols-4">
              {photos.data.results.map((photo) => (
                <li key={photo.id}>
                  <button
                    type="button"
                    className="flex h-full w-full cursor-pointer flex-col gap-1.5 rounded-xl border border-line p-2 text-left hover:bg-info-50"
                    onClick={() => setEditing(photo)}
                    aria-label={t("console.site.edit", { title: photo.alt_fr })}
                  >
                    <img
                      src={photo.small_url}
                      alt=""
                      className="aspect-3/2 w-full rounded-lg object-cover"
                    />
                    <b className="break-words">{photo.alt_fr}</b>
                    <span className="text-sm text-ink-3">
                      {photo.credit} · {t(`console.photos.licenses.${photo.license}`)}
                    </span>
                    <span className="flex flex-wrap gap-1.5">
                      <Tag>
                        {photo.uses
                          ? t("console.photos.used", { count: photo.uses })
                          : t("console.photos.unused")}
                      </Tag>
                      {photo.recognizable && (
                        <StatusPill tone="warn">{t("console.photos.recognizable")}</StatusPill>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
        <CardFooter className="flex-wrap justify-between gap-3">
          <span className="text-sm text-ink-3">
            {t("console.photos.page", {
              page,
              pages: Math.max(1, Math.ceil((photos.data?.count ?? 0) / 24)),
            })}
          </span>
          <span className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!photos.data?.previous}
              onClick={() => setPage(page - 1)}
            >
              {t("common.previous")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!photos.data?.next}
              onClick={() => setPage(page + 1)}
            >
              {t("common.next")}
            </Button>
          </span>
        </CardFooter>
      </Card>
      {editing && (
        <PhotoDialog
          key={editing === "new" ? "new" : editing.id}
          photo={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}

/** Photo du haut de l'accueil, des écoles et des parents ; vide = celle du site. */
function Slots() {
  const { t } = useTranslation();
  const pages = useQuery({
    queryKey: keys.sitePages,
    queryFn: () => call(api.GET("/api/console/site/pages/")),
  });
  return (
    <Card className="mt-4">
      <CardHeader className="flex-wrap gap-2">
        <CardTitle>{t("console.photos.slots")}</CardTitle>
        <span className="text-sm text-ink-3">{t("console.photos.slotsHint")}</span>
      </CardHeader>
      <CardContent className="grid gap-4 min-[820px]:grid-cols-3">
        {pages.isPending ? (
          <Skeleton label={t("common.loading")} />
        ) : pages.isError ? (
          <Banner tone="due">{errorMessage(pages.error, t)}</Banner>
        ) : (
          pages.data
            .filter((page) => page.has_photo_slot)
            .map((page) => <Slot key={page.key} page={page} />)
        )}
      </CardContent>
    </Card>
  );
}

function Slot({ page }: { page: Page }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (photo: string | null) =>
      call(
        api.PATCH("/api/console/site/pages/{key}/", {
          params: { path: { key: page.key } },
          body: { photo },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.sitePages }),
  });
  return (
    <div className="flex flex-col gap-2">
      <b>{t(`console.site.seo.pages.${page.key}`)}</b>
      {page.photo ? (
        <img
          src={thumbnail(page.photo)}
          alt=""
          className="aspect-3/2 w-full rounded-xl object-cover"
        />
      ) : (
        <span className="text-sm text-ink-3">{t("console.photos.defaultPhoto")}</span>
      )}
      <PhotoPicker
        id={`slot-${page.key}`}
        value={page.photo}
        minWidth={MIN_WIDTH}
        onChange={(photo) => save.mutate(photo)}
      />
      {save.isError && <span className="text-sm text-due">{errorMessage(save.error, t)}</span>}
    </div>
  );
}

function PhotoDialog({ photo, onClose }: { photo: Photo | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const required = t("fieldErrors.required");
  const schema = z.object({
    alt_fr: z.string().trim().min(1, required).max(200),
    alt_en: z.string().trim().min(1, required).max(200),
    credit: z.string().trim().min(1, required).max(200),
    license: z.enum(["cc0", "public_domain", "cc_by", "cc_by_sa", "consent"]),
    recognizable: z.boolean(),
  });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: photo ?? {
      alt_fr: "",
      alt_en: "",
      credit: "",
      license: "consent",
      recognizable: false,
    },
  });
  const [image, setImage] = useState<File | null>(null);
  const [consent, setConsent] = useState<File | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [general, setGeneral] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const errors = form.formState.errors;
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.sitePhotos });
  const save = useMutation({
    mutationFn: (values: Values) => {
      if (photo) {
        const body = new FormData();
        for (const [key, value] of Object.entries(values)) body.append(key, String(value));
        if (consent) body.append("consent", consent);
        return call(
          api.PATCH("/api/console/site/photos/{id}/", {
            params: { path: { id: photo.id } },
            body: body as never,
          }),
        );
      }
      const body = new FormData();
      for (const [key, value] of Object.entries(values)) body.append(key, String(value));
      if (image) body.append("image", image);
      if (consent) body.append("consent", consent);
      return call(api.POST("/api/console/site/photos/", { body: body as never }));
    },
    onSuccess: () => {
      refresh();
      onClose();
    },
    onError: (error) => {
      const message = applyServerErrors(
        error,
        ["alt_fr", "alt_en", "credit", "license", "recognizable"],
        form.setError,
        t,
      );
      setGeneral(message);
    },
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/console/site/photos/{id}/", { params: { path: { id: photo?.id ?? "" } } }),
      ),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });
  const recognizable = useWatch({ control: form.control, name: "recognizable" });
  const license = useWatch({ control: form.control, name: "license" });
  const needsConsent = recognizable || license === "consent";

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t(photo ? "console.photos.editTitle" : "console.photos.upload")}
        footer={
          <>
            {photo && (
              <Button
                variant="destructive-outline"
                className="mr-auto"
                onClick={() => setConfirm(true)}
              >
                {t("console.site.delete")}
              </Button>
            )}
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              disabled={save.isPending}
              onClick={() => {
                setGeneral(null);
                setImageError(null);
                if (!photo && !image) {
                  setImageError(t("fieldErrors.required"));
                  return;
                }
                void form.handleSubmit((values) => save.mutate(values))();
              }}
            >
              {t(photo ? "console.site.save" : "console.photos.send")}
            </Button>
          </>
        }
      >
        {general && <Banner tone="due">{general}</Banner>}
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
        {photo ? (
          <img src={photo.small_url} alt="" className="aspect-3/2 w-full rounded-xl object-cover" />
        ) : (
          <Field
            id="photo-image"
            label={t("console.photos.choosePhoto")}
            required
            help={t("console.photos.imageHelp")}
            error={imageError}
          >
            {(control) => (
              <FilePicker
                id={control.id}
                file={image}
                onFile={setImage}
                deposited={false}
                accept="image/jpeg,image/png,image/webp"
              />
            )}
          </Field>
        )}
        <div className="grid gap-3 min-[560px]:grid-cols-2">
          {(["fr", "en"] as const).map((lang) => (
            <Field
              key={lang}
              id={`photo-alt_${lang}`}
              label={t(`console.photos.alt_${lang}`)}
              required
              help={lang === "fr" ? t("console.photos.altHelp") : undefined}
              error={errors[`alt_${lang}`]?.message}
            >
              {(control) => (
                <Input {...control} maxLength={200} {...form.register(`alt_${lang}`)} />
              )}
            </Field>
          ))}
        </div>
        <div className="grid gap-3 min-[560px]:grid-cols-2">
          <Field
            id="photo-credit"
            label={t("console.photos.credit")}
            required
            error={errors.credit?.message}
          >
            {(control) => <Input {...control} maxLength={200} {...form.register("credit")} />}
          </Field>
          <Field
            id="photo-license"
            label={t("console.photos.license")}
            required
            help={t("console.photos.licenseHelp")}
            error={errors.license?.message}
          >
            {(control) => (
              <Select {...control} {...form.register("license")}>
                {LICENSES.map((value) => (
                  <option key={value} value={value}>
                    {t(`console.photos.licenses.${value}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <CheckboxField
          id="photo-recognizable"
          checked={recognizable}
          onCheckedChange={(checked) => form.setValue("recognizable", checked === true)}
          label={t("console.photos.recognizableLabel")}
        />
        {needsConsent && (
          <Field
            id="photo-consent"
            label={t("console.photos.consent")}
            required
            help={t("console.photos.consentHelp")}
          >
            {(control) => (
              <FilePicker
                id={control.id}
                file={consent}
                onFile={setConsent}
                deposited={photo?.has_consent ?? false}
                download={photo ? `/api/console/site/photos/${photo.id}/consent/` : undefined}
              />
            )}
          </Field>
        )}
      </DialogContent>
      {photo && (
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={t("console.site.deleteTitle", { title: photo.alt_fr })}
          confirmLabel={t("console.site.delete")}
          cancelLabel={t("common.cancel")}
          pending={remove.isPending}
          onConfirm={() => remove.mutate()}
        >
          {t("console.photos.deleteText")}
        </ConfirmDialog>
      )}
    </DialogRoot>
  );
}
