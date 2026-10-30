// Classes de l'année (C2) : une ligne par option et niveau, une étiquette par section (A, B…) qui
// ouvre la classe ; titulaire choisi parmi le personnel actif. Une classe ne se supprime que sans
// élève (vérifié par le serveur). Effectifs : avec les inscriptions (2.1).
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
import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  type ClassGroup,
  type Level,
  type Track,
  type Year,
  useClasses,
  useHomeroomCandidates,
  useLevels,
  useRefresh,
  useTracks,
} from "./data";

type Row = { key: string; level: Level; track: Track | null; groups: ClassGroup[] };

/** Une ligne par option et niveau : sans option d'abord (éducation de base), puis par option. */
function rows(groups: ClassGroup[], levels: Level[], tracks: Track[]): Row[] {
  const byId = <T extends { id: string }>(items: T[]) =>
    new Map(items.map((item) => [item.id, item]));
  const levelById = byId(levels);
  const trackById = byId(tracks);
  const result = new Map<string, Row>();
  for (const group of groups) {
    const level = levelById.get(group.level);
    if (!level) continue;
    const track = group.track ? (trackById.get(group.track) ?? null) : null;
    const key = `${track?.id ?? ""}:${level.id}`;
    const row = result.get(key) ?? { key, level, track, groups: [] };
    row.groups.push(group);
    result.set(key, row);
  }
  const trackOrder = (track: Track | null) => (track ? tracks.indexOf(track) + 1 : 0);
  return [...result.values()].sort(
    (a, b) =>
      trackOrder(a.track) - trackOrder(b.track) ||
      levels.indexOf(a.level) - levels.indexOf(b.level),
  );
}

export function ClassesCard({ year }: { year: Year }) {
  const { t } = useTranslation();
  const classes = useClasses(year.id);
  const levels = useLevels();
  const tracks = useTracks();
  const [open, setOpen] = useState<ClassGroup | "new" | null>(null);

  const failed = [classes, levels, tracks].find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;
  if (!classes.data || !levels.data || !tracks.data) {
    return <Skeleton label={t("common.loading")} />;
  }
  const list = rows(classes.data, levels.data, tracks.data);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("organisation.classes.title", { year: year.name })}</CardTitle>
        <div className="flex items-center gap-3">
          <span className="text-sm text-ink-3">
            {t("organisation.classes.count", { count: classes.data.length })}
          </span>
          <Button size="sm" disabled={levels.data.length === 0} onClick={() => setOpen("new")}>
            <Icon name="plus" size={14} />
            {t("organisation.classes.add")}
          </Button>
        </div>
      </CardHeader>
      {levels.data.length === 0 ? (
        <CardContent>
          <Banner tone="info">{t("organisation.classes.needLevel")}</Banner>
        </CardContent>
      ) : list.length === 0 ? (
        <CardContent className="text-ink-3">{t("organisation.classes.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("organisation.classes.track")}</th>
              <th>{t("organisation.classes.level")}</th>
              <th>{t("organisation.classes.sections")}</th>
              <th className="text-right">{t("organisation.classes.headcount")}</th>
              <th>{t("organisation.classes.homeroom")}</th>
            </tr>
          </thead>
          <tbody>
            {list.map((row) => (
              <ClassRow key={row.key} row={row} onOpen={setOpen} />
            ))}
          </tbody>
        </Table>
      )}
      <ClassDialog
        year={year}
        group={open === "new" ? null : open}
        open={open !== null}
        levels={levels.data}
        tracks={tracks.data}
        onClose={() => setOpen(null)}
      />
    </Card>
  );
}

function ClassRow({ row, onOpen }: { row: Row; onOpen: (group: ClassGroup) => void }) {
  const { t } = useTranslation();
  const capacities = row.groups.map((group) => group.capacity).filter((c) => c !== null);
  const students = row.groups.reduce((sum, group) => sum + group.student_count, 0);
  const missing = row.groups.filter((group) => !group.homeroom_teacher).length;
  const [single] = row.groups;
  let teacher: React.ReactNode;
  if (row.groups.length === 1 && single?.homeroom_teacher) {
    teacher = fullName(single.homeroom_teacher);
  } else if (missing === 0) {
    teacher = t("organisation.classes.teachersAssigned");
  } else {
    teacher = (
      <span className="text-warn">
        {row.groups.length === 1
          ? t("organisation.classes.noTeacher")
          : t("organisation.classes.missingTeachers", { count: missing })}
      </span>
    );
  }
  return (
    <tr>
      <td>{row.track ? row.track.name : t(`cycles.${row.level.cycle}`)}</td>
      <td className="font-bold">{row.level.name}</td>
      <td>
        <div className="flex flex-wrap gap-1.5">
          {row.groups.map((group) => (
            <button
              key={group.id}
              type="button"
              aria-label={t("organisation.classes.open", { name: group.name })}
              onClick={() => onOpen(group)}
              className="min-w-8 cursor-pointer rounded-[6px] bg-gray-50 px-2 py-0.5 text-xs font-bold text-ink-2 hover:bg-lake-50 hover:text-lake focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
            >
              {group.section || t("common.none")}
            </button>
          ))}
        </div>
      </td>
      <td className="text-right tabular-nums">
        {students}
        {capacities.length > 0 && ` / ${capacities.reduce((sum, value) => sum + value, 0)}`}
      </td>
      <td className="text-sm">{teacher}</td>
    </tr>
  );
}

function useClassSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z.object({
        level: z.string().min(1, t("validation.levelRequired")),
        track: z.string(),
        section: z.string().trim().max(10),
        capacity: z
          .string()
          .trim()
          .refine(
            (value) => value === "" || (/^\d+$/.test(value) && +value >= 1 && +value <= 1000),
            t("validation.capacityRange"),
          ),
        homeroom_teacher: z.string(),
        co_homeroom_teacher: z.string(),
      }),
    [t],
  );
}

type ClassDialogProps = {
  year: Year;
  group: ClassGroup | null;
  open: boolean;
  levels: Level[];
  tracks: Track[];
  onClose: () => void;
};

function ClassDialog({ year, group, open, levels, tracks, onClose }: ClassDialogProps) {
  const { t } = useTranslation();
  const refresh = useRefresh();
  const schema = useClassSchema();
  const candidates = useHomeroomCandidates();
  const [general, setGeneral] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const form = useForm({
    resolver: zodResolver(schema),
    values: {
      level: group?.level ?? levels[0]?.id ?? "",
      track: group?.track ?? "",
      section: group?.section ?? "",
      capacity: group?.capacity?.toString() ?? "",
      homeroom_teacher: group?.homeroom_teacher?.id ?? "",
      co_homeroom_teacher: group?.co_homeroom_teacher?.id ?? "",
    },
  });
  const done = async () => {
    await refresh(keys.classes);
    setDeleting(false);
    onClose();
  };
  const save = useMutation({
    mutationFn: (values: z.output<typeof schema>) => {
      const body = {
        level: values.level,
        track: values.track || null,
        section: values.section,
        capacity: values.capacity ? Number(values.capacity) : null,
        homeroom_teacher: values.homeroom_teacher || null,
        co_homeroom_teacher: values.co_homeroom_teacher || null,
      };
      return group
        ? call(api.PATCH("/api/class-groups/{id}/", { params: { path: { id: group.id } }, body }))
        : call(api.POST("/api/class-groups/", { body: { ...body, academic_year: year.id } }));
    },
    onSuccess: done,
    onError: (error) =>
      setGeneral(
        applyServerErrors(
          error,
          ["level", "track", "section", "capacity", "homeroom_teacher", "co_homeroom_teacher"],
          form.setError,
          t,
        ),
      ),
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/class-groups/{id}/", { params: { path: { id: group!.id } } })),
    onSuccess: done,
  });
  const { errors } = form.formState;
  const close = (next: boolean) => {
    if (next) return;
    setGeneral(null);
    save.reset();
    remove.reset();
    onClose();
  };

  return (
    <DialogRoot open={open && !deleting} onOpenChange={close}>
      <DialogContent
        title={
          group
            ? t("organisation.classes.editTitle", { name: group.name })
            : t("organisation.classes.newTitle")
        }
        footer={
          <>
            {group && (
              <Button
                variant="destructive-outline"
                className="mr-auto"
                onClick={() => setDeleting(true)}
              >
                {t("organisation.classes.delete")}
              </Button>
            )}
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="class-form" disabled={save.isPending}>
              {group ? t("common.save") : t("organisation.classes.create")}
            </Button>
          </>
        }
      >
        <form
          id="class-form"
          noValidate
          className="grid gap-3 min-[600px]:grid-cols-2"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            save.mutate(values);
          })}
        >
          {general && (
            <Banner tone="due" className="min-[600px]:col-span-2">
              {general}
            </Banner>
          )}
          <Field
            id="class-level"
            label={t("organisation.classes.level")}
            required
            error={errors.level?.message}
          >
            {(control) => (
              <Select {...control} {...form.register("level")}>
                {levels.map((level) => (
                  <option key={level.id} value={level.id}>
                    {level.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id="class-track"
            label={t("organisation.classes.track")}
            error={errors.track?.message}
          >
            {(control) => (
              <Select {...control} {...form.register("track")}>
                <option value="">{t("organisation.classes.noTrack")}</option>
                {tracks.map((track) => (
                  <option key={track.id} value={track.id}>
                    {track.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id="class-section"
            label={t("organisation.classes.section")}
            help={t("organisation.classes.sectionHelp")}
            error={errors.section?.message}
          >
            {(control) => (
              <Input {...control} className="uppercase" {...form.register("section")} />
            )}
          </Field>
          <Field
            id="class-capacity"
            label={t("organisation.classes.capacity")}
            error={errors.capacity?.message}
          >
            {(control) => <Input {...control} inputMode="numeric" {...form.register("capacity")} />}
          </Field>
          <Field
            id="class-teacher"
            label={t("organisation.classes.homeroom")}
            error={errors.homeroom_teacher?.message}
            className="min-[600px]:col-span-2"
          >
            {(control) => (
              <Select {...control} {...form.register("homeroom_teacher")}>
                <option value="">{t("organisation.classes.noTeacher")}</option>
                {(candidates.data ?? []).map((person) => (
                  <option key={person.id} value={person.id}>
                    {fullName(person)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id="class-co-teacher"
            label={t("organisation.classes.coHomeroom")}
            help={t("organisation.classes.coHomeroomHelp")}
            error={errors.co_homeroom_teacher?.message}
            className="min-[600px]:col-span-2"
          >
            {(control) => (
              <Select {...control} {...form.register("co_homeroom_teacher")}>
                <option value="">{t("organisation.classes.noCoTeacher")}</option>
                {(candidates.data ?? []).map((person) => (
                  <option key={person.id} value={person.id}>
                    {fullName(person)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {group && (
            <p className="text-xs text-ink-3 min-[600px]:col-span-2">
              {t("organisation.classes.deleteHelp")}
            </p>
          )}
        </form>
      </DialogContent>
      <ConfirmDialog
        open={deleting}
        onOpenChange={(next) => {
          setDeleting(next);
          remove.reset();
        }}
        title={`${t("organisation.classes.delete")} | ${group?.name ?? ""}`}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      </ConfirmDialog>
    </DialogRoot>
  );
}
