// Onglet « Niveaux et options » (C2) : niveaux dans l'ordre de l'école (flèches), options avec
// leur code (matricule `{OPT}`). Suppression refusée par le serveur si des classes s'en servent.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
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
  Icon,
  Input,
  Select,
  Skeleton,
  Table,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  CYCLES,
  type Cycle,
  type Level,
  type Track,
  useLevels,
  useRefresh,
  useTracks,
} from "./data";

const TRACK_CODE = /^[A-Z0-9]{1,10}$/;

function useLevelSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z.object({
        name: z.string().trim().min(1, t("validation.nameRequired")).max(40),
        cycle: z.string(),
      }),
    [t],
  );
}

function useTrackSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z.object({
        name: z.string().trim().min(1, t("validation.nameRequired")).max(80),
        code: z
          .string()
          .trim()
          .transform((code) => code.toUpperCase())
          .refine((code) => TRACK_CODE.test(code), t("validation.codeFormat")),
      }),
    [t],
  );
}

// Niveaux

export function LevelsCard() {
  const { t } = useTranslation();
  const levels = useLevels();
  const refresh = useRefresh();
  const [editing, setEditing] = useState<Level | null>(null);
  const [deleting, setDeleting] = useState<Level | null>(null);
  const reorder = useMutation({
    mutationFn: (ids: string[]) => call(api.POST("/api/levels/reorder/", { body: { ids } })),
    onSuccess: () => refresh(keys.levels, keys.classes),
  });
  const remove = useMutation({
    mutationFn: (level: Level) =>
      call(api.DELETE("/api/levels/{id}/", { params: { path: { id: level.id } } })),
    onSuccess: async () => {
      setDeleting(null);
      await refresh(keys.levels);
    },
  });

  if (levels.isPending) return <Skeleton label={t("common.loading")} />;
  if (levels.isError)
    return <LoadError error={levels.error} onRetry={() => void levels.refetch()} />;
  const list = levels.data;
  const move = (index: number, offset: number) => {
    const ids = list.map((level) => level.id);
    const [moved] = ids.splice(index, 1);
    ids.splice(index + offset, 0, moved!);
    reorder.mutate(ids);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("organisation.levels.title")}</CardTitle>
      </CardHeader>
      {reorder.isError && (
        <CardContent>
          <Banner tone="due">{errorMessage(reorder.error, t)}</Banner>
        </CardContent>
      )}
      {list.length === 0 ? (
        <CardContent className="text-ink-3">{t("organisation.levels.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("organisation.levels.name")}</th>
              <th>{t("organisation.levels.cycle")}</th>
              <th>{t("organisation.levels.order")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.map((level, index) => (
              <tr key={level.id}>
                <td className="font-bold">{level.name}</td>
                <td className="text-ink-2">{t(`cycles.${level.cycle}`)}</td>
                <td className="whitespace-nowrap">
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("organisation.levels.up", { name: level.name })}
                    disabled={index === 0 || reorder.isPending}
                    onClick={() => move(index, -1)}
                  >
                    <Icon name="chevdown" size={16} className="rotate-180" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={t("organisation.levels.down", { name: level.name })}
                    disabled={index === list.length - 1 || reorder.isPending}
                    onClick={() => move(index, 1)}
                  >
                    <Icon name="chevdown" size={16} />
                  </Button>
                </td>
                <td className="text-right whitespace-nowrap">
                  <RowActions
                    name={level.name}
                    onEdit={() => setEditing(level)}
                    onDelete={() => {
                      remove.reset();
                      setDeleting(level);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <CardContent className="border-t border-line">
        <LevelForm />
      </CardContent>
      <LevelDialog level={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`${t("common.delete")} — ${deleting?.name ?? ""}`}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => deleting && remove.mutate(deleting)}
        pending={remove.isPending}
        destructive
      >
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}

function RowActions({
  name,
  onEdit,
  onDelete,
}: {
  name: string;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <Button variant="ghost" size="sm" aria-label={`${t("common.edit")} ${name}`} onClick={onEdit}>
        <Icon name="edit" size={16} />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`${t("common.delete")} ${name}`}
        onClick={onDelete}
        className="text-due hover:bg-due-50"
      >
        <Icon name="x" size={16} />
      </Button>
    </>
  );
}

function LevelFields({
  form,
  idPrefix,
}: {
  form: ReturnType<typeof useLevelForm>;
  idPrefix: string;
}) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  return (
    <>
      <Field
        id={`${idPrefix}-name`}
        label={t("organisation.levels.name")}
        required
        error={errors.name?.message}
      >
        {(control) => (
          <Input
            {...control}
            placeholder={t("organisation.levels.namePlaceholder")}
            {...form.register("name")}
          />
        )}
      </Field>
      <Field id={`${idPrefix}-cycle`} label={t("organisation.levels.cycle")}>
        {(control) => (
          <Select {...control} {...form.register("cycle")}>
            {CYCLES.map((cycle) => (
              <option key={cycle} value={cycle}>
                {t(`cycles.${cycle}`)}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </>
  );
}

function useLevelForm(level?: Level | null) {
  const schema = useLevelSchema();
  return useForm({
    resolver: zodResolver(schema),
    values: { name: level?.name ?? "", cycle: level?.cycle ?? "secondary_general" },
  });
}

function LevelForm() {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const form = useLevelForm();
  const [general, setGeneral] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (body: { name: string; cycle: string }) =>
      call(api.POST("/api/levels/", { body: { ...body, cycle: body.cycle as Cycle } })),
    onSuccess: async () => {
      form.reset({ name: "", cycle: form.getValues("cycle") });
      await refresh(keys.levels);
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["name", "cycle"], form.setError, t)),
  });
  return (
    <form
      noValidate
      className="grid items-start gap-3 min-[600px]:grid-cols-[1fr_1fr_auto]"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        create.mutate(values);
      })}
    >
      {general && (
        <Banner tone="due" className="min-[600px]:col-span-3">
          {general}
        </Banner>
      )}
      <LevelFields form={form} idPrefix="new-level" />
      <Button type="submit" className="min-[600px]:mt-[26px]" disabled={create.isPending}>
        <Icon name="plus" size={16} />
        {t("organisation.levels.add")}
      </Button>
    </form>
  );
}

function LevelDialog({ level, onClose }: { level: Level | null; onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const form = useLevelForm(level);
  const [general, setGeneral] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (body: { name: string; cycle: string }) =>
      call(
        api.PATCH("/api/levels/{id}/", {
          params: { path: { id: level!.id } },
          body: { ...body, cycle: body.cycle as Cycle },
        }),
      ),
    onSuccess: async () => {
      await refresh(keys.levels, keys.classes);
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["name", "cycle"], form.setError, t)),
  });
  return (
    <DialogRoot open={level !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("organisation.levels.editTitle")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="edit-level" disabled={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form
          id="edit-level"
          noValidate
          className="flex flex-col gap-3"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            save.mutate(values);
          })}
        >
          {general && <Banner tone="due">{general}</Banner>}
          <LevelFields form={form} idPrefix="edit-level" />
        </form>
      </DialogContent>
    </DialogRoot>
  );
}

// Options

export function TracksCard() {
  const { t } = useTranslation();
  const tracks = useTracks();
  const refresh = useRefresh();
  const [editing, setEditing] = useState<Track | null>(null);
  const [deleting, setDeleting] = useState<Track | null>(null);
  const remove = useMutation({
    mutationFn: (track: Track) =>
      call(api.DELETE("/api/tracks/{id}/", { params: { path: { id: track.id } } })),
    onSuccess: async () => {
      setDeleting(null);
      await refresh(keys.tracks);
    },
  });
  if (tracks.isPending) return <Skeleton label={t("common.loading")} />;
  if (tracks.isError)
    return <LoadError error={tracks.error} onRetry={() => void tracks.refetch()} />;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("organisation.tracks.title")}</CardTitle>
      </CardHeader>
      {tracks.data.length === 0 ? (
        <CardContent className="text-ink-3">{t("organisation.tracks.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("organisation.tracks.name")}</th>
              <th>{t("organisation.tracks.code")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {tracks.data.map((track) => (
              <tr key={track.id}>
                <td className="font-bold">{track.name}</td>
                <td className="font-mono">{track.code}</td>
                <td className="text-right whitespace-nowrap">
                  <RowActions
                    name={track.name}
                    onEdit={() => setEditing(track)}
                    onDelete={() => {
                      remove.reset();
                      setDeleting(track);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <CardContent className="border-t border-line">
        <TrackForm />
      </CardContent>
      <TrackDialog track={editing} onClose={() => setEditing(null)} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`${t("common.delete")} — ${deleting?.name ?? ""}`}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => deleting && remove.mutate(deleting)}
        pending={remove.isPending}
        destructive
      >
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}

function useTrackForm(track?: Track | null) {
  const schema = useTrackSchema();
  return useForm({
    resolver: zodResolver(schema),
    values: { name: track?.name ?? "", code: track?.code ?? "" },
  });
}

function TrackFields({
  form,
  idPrefix,
}: {
  form: ReturnType<typeof useTrackForm>;
  idPrefix: string;
}) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  return (
    <>
      <Field
        id={`${idPrefix}-name`}
        label={t("organisation.tracks.name")}
        required
        error={errors.name?.message}
      >
        {(control) => (
          <Input
            {...control}
            placeholder={t("organisation.tracks.namePlaceholder")}
            {...form.register("name")}
          />
        )}
      </Field>
      <Field
        id={`${idPrefix}-code`}
        label={t("organisation.tracks.code")}
        required
        help={t("organisation.tracks.codeHelp")}
        error={errors.code?.message}
      >
        {(control) => (
          <Input {...control} className="font-mono uppercase" {...form.register("code")} />
        )}
      </Field>
    </>
  );
}

function TrackForm() {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const form = useTrackForm();
  const [general, setGeneral] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (body: { name: string; code: string }) => call(api.POST("/api/tracks/", { body })),
    onSuccess: async () => {
      form.reset({ name: "", code: "" });
      await refresh(keys.tracks, keys.matricule);
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["name", "code"], form.setError, t)),
  });
  return (
    <form
      noValidate
      className="grid items-start gap-3 min-[600px]:grid-cols-[1fr_1fr_auto]"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        create.mutate(values);
      })}
    >
      {general && (
        <Banner tone="due" className="min-[600px]:col-span-3">
          {general}
        </Banner>
      )}
      <TrackFields form={form} idPrefix="new-track" />
      <Button type="submit" className="min-[600px]:mt-[26px]" disabled={create.isPending}>
        <Icon name="plus" size={16} />
        {t("organisation.tracks.add")}
      </Button>
    </form>
  );
}

function TrackDialog({ track, onClose }: { track: Track | null; onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const form = useTrackForm(track);
  const [general, setGeneral] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (body: { name: string; code: string }) =>
      call(api.PATCH("/api/tracks/{id}/", { params: { path: { id: track!.id } }, body })),
    onSuccess: async () => {
      await refresh(keys.tracks, keys.classes, keys.matricule);
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["name", "code"], form.setError, t)),
  });
  return (
    <DialogRoot open={track !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("organisation.tracks.editTitle")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="edit-track" disabled={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form
          id="edit-track"
          noValidate
          className="flex flex-col gap-3"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            save.mutate(values);
          })}
        >
          {general && <Banner tone="due">{general}</Banner>}
          <TrackFields form={form} idPrefix="edit-track" />
        </form>
      </DialogContent>
    </DialogRoot>
  );
}
