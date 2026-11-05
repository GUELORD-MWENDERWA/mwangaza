// Cours communs (8.1.2a, maquette `cours-communs`) : le même cours donné ensemble à plusieurs
// classes d'un niveau. Un seul enseignant, donné au cours de chaque classe ; les maxima, les notes
// et les bulletins restent ceux de chaque classe. Droit `courses.configure`, en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { firstErrorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { fullName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { type ClassGroup, useClasses, useLevels, useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { type Course, useTeachingLoads } from "./data";

type JointCourse = Schemas["CourseGroup"];
type Person = Schemas["Person"];

const same = (a: string, b: string) =>
  a.trim().toLocaleLowerCase("fr") === b.trim().toLocaleLowerCase("fr");

export function JointCoursesPage() {
  const { t } = useTranslation();
  const years = useYears();
  const year = years.data?.find((item) => item.is_current) ?? years.data?.[0];
  const classes = useClasses(year?.id ?? "");
  const levels = useLevels();
  // Les cours communs de toute l'année : une lecture, et le niveau qui en a s'ouvre d'abord.
  const groups = useQuery({
    queryKey: [...keys.courseGroups, year?.id],
    queryFn: () =>
      call(api.GET("/api/course-groups/", { params: { query: { academic_year: year!.id } } })),
    enabled: Boolean(year),
  });
  const [chosen, setChosen] = useState<string | null>(null);

  if (years.isPending || levels.isPending || (year && (classes.isPending || groups.isPending))) {
    return <Skeleton label={t("common.loading")} />;
  }
  const failed = [years, levels, classes, groups].find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;
  // Un cours commun réunit au moins deux classes d'un niveau.
  const all = classes.data ?? [];
  const usable = (levels.data ?? []).filter(
    (level) => all.filter((group) => group.level === level.id).length >= 2,
  );
  const level =
    usable.find((item) => item.id === chosen) ??
    usable.find((item) => groups.data?.some((group) => group.level === item.id)) ??
    usable[0];
  if (!year || !level) {
    return (
      <>
        <PageHeader title={t("courses.joint.title")} subtitle={t("courses.joint.subtitleEmpty")} />
        <Banner tone="info">
          {t(year ? "courses.joint.noLevel" : "courses.noYear")}{" "}
          <Link to="/organisation" className="font-bold underline">
            {t("courses.toOrganisation")}
          </Link>
        </Banner>
      </>
    );
  }
  return (
    <LevelJointCourses
      key={level.id}
      yearId={year.id}
      yearName={year.name}
      level={level}
      levels={usable}
      classes={all.filter((group) => group.level === level.id)}
      groups={(groups.data ?? []).filter((group) => group.level === level.id)}
      onLevel={setChosen}
    />
  );
}

type LevelProps = {
  yearId: string;
  yearName: string;
  level: { id: string; name: string };
  levels: { id: string; name: string }[];
  classes: ClassGroup[];
  groups: JointCourse[];
  onLevel: (id: string) => void;
};

function LevelJointCourses({
  yearId,
  yearName,
  level,
  levels,
  classes,
  groups: list,
  onLevel,
}: LevelProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  // Les cours de chaque classe du niveau : les noms qu'on peut réunir (même requête que la grille).
  const grids = useQueries({
    queries: classes.map((group) => ({
      queryKey: [...keys.courses, group.id],
      queryFn: () =>
        call(api.GET("/api/class-groups/{id}/courses/", { params: { path: { id: group.id } } })),
    })),
  });
  const staff = useTeachingLoads();
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // Après un changement : groupes, grilles des classes et charges des enseignants relus.
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: [...keys.courseGroups, yearId] }),
      queryClient.invalidateQueries({ queryKey: keys.courses }),
      queryClient.invalidateQueries({ queryKey: keys.teachingLoads }),
    ]);
  };

  if (staff.isPending || grids.some((query) => query.isPending)) {
    return <Skeleton label={t("common.loading")} />;
  }
  const failed = [staff, ...grids].find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;

  const teachers = (staff.data?.loads ?? []).map((load) => load.teacher);
  const courseLists = classes.map((group, index) => ({
    group,
    courses: (grids[index]!.data ?? []).filter((course) => course.is_taught),
  }));
  // Noms de cours donnés dans au moins deux classes du niveau.
  const names: string[] = [];
  for (const { courses } of courseLists) {
    for (const course of courses) {
      if (names.some((name) => same(name, course.name))) continue;
      const count = courseLists.filter((item) =>
        item.courses.some((other) => same(other.name, course.name)),
      ).length;
      if (count >= 2) names.push(course.name);
    }
  }
  names.sort((a, b) => a.localeCompare(b, i18n.language));
  const open = list.find((item) => item.id === openId) ?? null;
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const classNames = new Intl.ListFormat(i18n.language, { type: "unit" });

  return (
    <>
      <PageHeader
        title={t("courses.joint.title")}
        subtitle={t("courses.joint.subtitle", { year: yearName })}
        actions={
          <>
            <Select
              aria-label={t("courses.joint.levelChoice")}
              value={level.id}
              onChange={(event) => onLevel(event.target.value)}
              className="w-auto min-w-[160px]"
            >
              {levels.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Button
              disabled={names.length === 0}
              onClick={() => {
                setNotice(null);
                setCreating(true);
              }}
            >
              {t("courses.joint.create")}
            </Button>
          </>
        }
      />
      {notice && (
        <div className="mb-4">
          <Banner tone="ok">{notice}</Banner>
        </div>
      )}
      <Card>
        {list.length === 0 ? (
          <p className="px-5 py-6 text-sm text-ink-2">
            {t(names.length === 0 ? "courses.joint.noName" : "courses.joint.empty")}
          </p>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>{t("courses.joint.columns.name")}</th>
                <th>{t("courses.joint.columns.classes")}</th>
                <th>{t("courses.joint.columns.teacher")}</th>
                <th className="text-right">{t("courses.joint.columns.students")}</th>
                <th>
                  <span className="sr-only">{t("courses.joint.open")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {list.map((item) => (
                <tr key={item.id}>
                  <td>
                    <b>{item.name}</b>
                  </td>
                  <td data-label={t("courses.joint.columns.classes")}>
                    {classNames.format(item.classes.map((member) => member.class_name))}
                  </td>
                  <td data-label={t("courses.joint.columns.teacher")}>
                    {item.teacher ? (
                      fullName(item.teacher)
                    ) : (
                      <StatusPill tone="warn">{t("courses.unassigned")}</StatusPill>
                    )}
                  </td>
                  <td
                    data-label={t("courses.joint.columns.students")}
                    className="text-right tabular-nums"
                  >
                    {number(item.students)}
                  </td>
                  <td className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      aria-label={t("courses.joint.openNamed", { name: item.name })}
                      onClick={() => {
                        setNotice(null);
                        setOpenId(item.id);
                      }}
                    >
                      {t("courses.joint.open")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {open && (
        <GroupCard
          key={open.id}
          group={open}
          levelName={level.name}
          teachers={teachers}
          onChanged={async (message, gone) => {
            setNotice(message);
            if (gone) setOpenId(null);
            await refresh();
          }}
        />
      )}
      {creating && (
        <CreateDialog
          names={names}
          classes={courseLists}
          teachers={teachers}
          onClose={() => setCreating(false)}
          onCreated={async (created) => {
            setCreating(false);
            setNotice(t("courses.joint.created", { name: created.name }));
            setOpenId(created.id);
            await refresh();
          }}
        />
      )}
    </>
  );
}

type GroupProps = {
  group: JointCourse;
  levelName: string;
  teachers: Person[];
  onChanged(message: string, gone: boolean): Promise<void>;
};

function GroupCard({ group, levelName, teachers, onChanged }: GroupProps) {
  const { t, i18n } = useTranslation();
  const [teacher, setTeacher] = useState(group.teacher?.id ?? "");
  const [leaving, setLeaving] = useState<JointCourse["classes"][number] | null>(null);
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const path = { params: { path: { id: group.id } } };
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/course-groups/{id}/", { ...path, body: { teacher_id: teacher || null } }),
      ),
    onSuccess: () => onChanged(t("courses.joint.saved"), false),
  });
  const remove = useMutation({
    mutationFn: (member: JointCourse["classes"][number]) =>
      call(
        api.POST("/api/course-groups/{id}/remove-class/", {
          ...path,
          body: { class_group: member.class_group },
        }),
      ),
    onSuccess: (_, member) => {
      setLeaving(null);
      const gone = group.classes.length <= 2;
      return onChanged(
        t(gone ? "courses.joint.dissolved" : "courses.joint.left", {
          className: member.class_name,
          name: group.name,
        }),
        gone,
      );
    },
  });
  const changed = teacher !== (group.teacher?.id ?? "");

  return (
    <Card className="mt-6">
      <CardHeader className="flex-wrap gap-1">
        <div>
          <CardTitle>{t("courses.joint.detail", { name: group.name, level: levelName })}</CardTitle>
          <p className="text-sm text-ink-3">{t("courses.joint.detailHelp")}</p>
        </div>
      </CardHeader>
      {(save.isError || remove.isError) && (
        <div className="px-5 pt-4">
          <Banner tone="due">{firstErrorMessage(save.error ?? remove.error, t)}</Banner>
        </div>
      )}
      <Table stacked>
        <thead>
          <tr>
            <th>{t("courses.joint.columns.class")}</th>
            <th className="text-right">{t("courses.joint.columns.periodMax")}</th>
            <th className="text-right">{t("courses.joint.columns.examMax")}</th>
            <th className="text-right">{t("courses.joint.columns.students")}</th>
            <th>
              <span className="sr-only">{t("courses.joint.leave")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {group.classes.map((member) => (
            <tr key={member.course}>
              <td>
                <b>{member.class_name}</b>
              </td>
              <td
                data-label={t("courses.joint.columns.periodMax")}
                className="text-right tabular-nums"
              >
                {number(member.period_max)}
              </td>
              <td
                data-label={t("courses.joint.columns.examMax")}
                className="text-right tabular-nums"
              >
                {member.has_exam ? number(member.period_max * 2) : t("courses.noExam")}
              </td>
              <td
                data-label={t("courses.joint.columns.students")}
                className="text-right tabular-nums"
              >
                {number(member.students)}
              </td>
              <td className="text-right">
                <Button
                  variant="outline"
                  size="sm"
                  aria-label={t("courses.joint.leaveNamed", { className: member.class_name })}
                  onClick={() => setLeaving(member)}
                >
                  {t("courses.joint.leave")}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <div className="space-y-2 border-t border-line-soft px-5 py-4">
        <Field
          id="joint-teacher"
          label={t("courses.joint.teacher")}
          help={t("courses.joint.teacherHelp")}
        >
          {(control) => (
            <Select
              {...control}
              value={teacher}
              onChange={(event) => setTeacher(event.target.value)}
              className="sm:max-w-[320px]"
            >
              <option value="">{t("courses.unassigned")}</option>
              {teachers.map((person) => (
                <option key={person.id} value={person.id}>
                  {fullName(person)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <CardFooter>
        <span className="text-sm text-ink-2">{t("courses.joint.leaveHint")}</span>
        <Button disabled={!changed || save.isPending} onClick={() => save.mutate()}>
          {t("courses.save")}
        </Button>
      </CardFooter>
      <ConfirmDialog
        open={leaving !== null}
        onOpenChange={(value) => !value && setLeaving(null)}
        title={t("courses.joint.leaveTitle", { className: leaving?.class_name ?? "" })}
        confirmLabel={t("courses.joint.leave")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => leaving && remove.mutate(leaving)}
      >
        {t(group.classes.length <= 2 ? "courses.joint.leaveLast" : "courses.joint.leaveBody")}
      </ConfirmDialog>
    </Card>
  );
}

type CreateProps = {
  names: string[];
  classes: { group: ClassGroup; courses: Course[] }[];
  teachers: Person[];
  onClose: () => void;
  onCreated(created: JointCourse): Promise<void>;
};

function CreateDialog({ names, classes, teachers, onClose, onCreated }: CreateProps) {
  const { t } = useTranslation();
  const [name, setName] = useState(names[0] ?? "");
  // Chaque classe : son cours de ce nom, s'il en a un, et s'il est déjà dans un cours commun.
  const rows = classes.map(({ group, courses }) => {
    const course = courses.find((item) => same(item.name, name));
    return { group, course, grouped: Boolean(course?.course_group) };
  });
  const eligible = rows.filter((row) => row.course && !row.grouped);
  const [picked, setPicked] = useState<string[] | null>(null);
  const chosen = picked ?? eligible.map((row) => row.group.id);
  // L'enseignant proposé : celui que ces cours ont déjà en commun.
  const current = new Set(eligible.map((row) => row.course?.teacher?.id ?? ""));
  const [teacher, setTeacher] = useState<string | null>(null);
  const teacherId = teacher ?? (current.size === 1 ? [...current][0]! : "");
  const create = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/course-groups/", {
          body: { name, class_groups: chosen, teacher_id: teacherId || null },
        }),
      ),
    onSuccess: onCreated,
  });

  return (
    <DialogRoot open onOpenChange={(value) => !value && onClose()}>
      <DialogContent
        title={t("courses.joint.create")}
        description={t("courses.joint.createHelp")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              disabled={chosen.length < 2 || create.isPending}
              onClick={() => create.mutate()}
            >
              {t("courses.joint.confirm")}
            </Button>
          </>
        }
      >
        {create.isError && <Banner tone="due">{firstErrorMessage(create.error, t)}</Banner>}
        <Field id="joint-name" label={t("courses.joint.course")} required>
          {(control) => (
            <Select
              {...control}
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                setPicked(null);
                setTeacher(null);
              }}
            >
              {names.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <fieldset className="space-y-2">
          <legend className="mb-1.5 text-sm font-semibold text-ink">
            {t("courses.joint.classes")} <span className="text-due">*</span>
          </legend>
          {rows.map((row) => {
            const usable = Boolean(row.course) && !row.grouped;
            const label = usable
              ? row.group.name
              : t(row.grouped ? "courses.joint.alreadyGrouped" : "courses.joint.withoutCourse", {
                  className: row.group.name,
                });
            return (
              <CheckboxField
                key={row.group.id}
                id={`joint-class-${row.group.id}`}
                label={label}
                disabled={!usable}
                checked={usable && chosen.includes(row.group.id)}
                onCheckedChange={(value) =>
                  setPicked(
                    value === true
                      ? [...chosen, row.group.id]
                      : chosen.filter((id) => id !== row.group.id),
                  )
                }
              />
            );
          })}
        </fieldset>
        <Field id="joint-new-teacher" label={t("courses.joint.teacher")}>
          {(control) => (
            <Select
              {...control}
              value={teacherId}
              onChange={(event) => setTeacher(event.target.value)}
            >
              <option value="">{t("courses.unassigned")}</option>
              {teachers.map((person) => (
                <option key={person.id} value={person.id}>
                  {fullName(person)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </DialogContent>
    </DialogRoot>
  );
}
