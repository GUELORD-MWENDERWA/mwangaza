// Fenêtre d'une règle de l'horaire (EDT.1c, maquette `regle-emploi-du-temps`) : le type de règle
// (liste fermée), ses champs, obligatoire ou souhait avec un poids, active ou non. Le serveur
// vérifie tout (schéma du type, cours et salles de l'école) ; le premier refus s'affiche en haut.
// Droit `timetable.manage`.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  CheckboxField,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Segmented,
  Select,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { dayKey } from "./AvailabilityDialog";
import { keys } from "../../lib/queries";
import type { Room, Rule, RuleChoices, RuleCourse, RuleKind, RuleStrength } from "./data";
import {
  CATEGORIES,
  RULE_KINDS,
  type Params,
  type Target,
  courseLabel,
  emptyParams,
  isComplete,
} from "./rules";

type Props = {
  rule: Rule | null;
  choices: RuleChoices;
  rooms: Room[];
  /** Jours qui ont des heures de cours, et le plus grand numéro d'heure des grilles. */
  days: number[];
  maxLessons: number;
  onClose: () => void;
};

const WEIGHTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export function RuleDialog({ rule, choices, rooms, days, maxLessons, onClose }: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const specOf = (kind: RuleKind) => choices.kinds.find((item) => item.kind === kind);
  const [kind, setKind] = useState<RuleKind>(rule?.kind ?? "fixed_lesson");
  const [params, setParams] = useState<Params>(
    rule ? (rule.params as Params) : emptyParams("fixed_lesson"),
  );
  const [strength, setStrength] = useState<RuleStrength>(
    rule?.strength ?? specOf(kind)?.strength ?? "hard",
  );
  const [weight, setWeight] = useState(rule?.weight ?? specOf(kind)?.weight ?? 5);
  const [active, setActive] = useState(rule?.active ?? true);
  const [confirming, setConfirming] = useState(false);
  const spec = specOf(kind);
  const set = (changes: Partial<Params>) => setParams((current) => ({ ...current, ...changes }));

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: keys.timetable });
    onClose();
  };
  const save = useMutation({
    mutationFn: () => {
      const body = { kind, params, strength, weight, active };
      return rule
        ? call(
            api.PUT("/api/timetable/constraints/{id}/", {
              params: { path: { id: rule.id } },
              body,
            }),
          )
        : call(api.POST("/api/timetable/constraints/", { body }));
    },
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        api.DELETE("/api/timetable/constraints/{id}/", {
          params: { path: { id: rule?.id ?? "" } },
        }),
      ),
    onSuccess: done,
  });

  const chooseKind = (next: RuleKind) => {
    setKind(next);
    setParams(emptyParams(next));
    setStrength(specOf(next)?.strength ?? "hard");
    setWeight(specOf(next)?.weight ?? 5);
  };
  const error = save.error ?? remove.error;

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t(
          rule ? "timetable.constraints.form.editTitle" : "timetable.constraints.form.newTitle",
        )}
        description={t("timetable.constraints.form.subtitle")}
        className="w-[min(640px,calc(100vw-32px))]"
        footer={
          <>
            {rule && (
              <Button
                variant="ghost"
                className="mr-auto text-due"
                onClick={() => setConfirming(true)}
              >
                {t("timetable.constraints.form.delete")}
              </Button>
            )}
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              disabled={save.isPending || !isComplete(kind, params)}
              onClick={() => save.mutate()}
            >
              {t("timetable.constraints.form.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field
            id="rule-kind"
            label={t("timetable.constraints.form.kind")}
            help={t(`timetable.constraints.examples.${kind}`)}
          >
            {(control) => (
              <Select
                {...control}
                value={kind}
                onChange={(event) => chooseKind(event.target.value as RuleKind)}
              >
                {RULE_KINDS.map((item) => (
                  <option key={item} value={item}>
                    {t(`timetable.constraints.kinds.${item}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <KindFields
            kind={kind}
            params={params}
            set={set}
            choices={choices}
            rooms={rooms}
            days={days}
            maxLessons={maxLessons}
          />
          {spec && spec.strengths.length > 1 ? (
            <div className="flex flex-col gap-2">
              <b className="text-sm text-ink-2">{t("timetable.constraints.form.strength")}</b>
              <Segmented<RuleStrength>
                label={t("timetable.constraints.form.strength")}
                value={strength}
                onValueChange={setStrength}
                options={[
                  { value: "hard", label: t("timetable.constraints.strength.hard") },
                  { value: "soft", label: t("timetable.constraints.strength.soft") },
                ]}
                className="self-start max-[600px]:w-full"
              />
            </div>
          ) : (
            <p className="text-sm text-ink-3">
              {t(
                strength === "hard"
                  ? "timetable.constraints.form.alwaysHard"
                  : "timetable.constraints.form.alwaysSoft",
              )}
            </p>
          )}
          {strength === "soft" && (
            <Field
              id="rule-weight"
              label={t("timetable.constraints.form.weight")}
              help={t("timetable.constraints.form.weightHelp")}
            >
              {(control) => (
                <Select
                  {...control}
                  value={weight}
                  onChange={(event) => setWeight(Number(event.target.value))}
                  className="w-auto"
                >
                  {WEIGHTS.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <CheckboxField
            id="rule-active"
            checked={active}
            onCheckedChange={(checked) => setActive(checked === true)}
            label={
              <>
                {t("timetable.constraints.form.active")}{" "}
                <span className="text-sm text-ink-3">
                  {t("timetable.constraints.form.activeHelp")}
                </span>
              </>
            }
          />
          {error && <Banner tone="due">{firstErrorMessage(error, t)}</Banner>}
        </div>
      </DialogContent>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("timetable.constraints.form.deleteTitle")}
        confirmLabel={t("timetable.constraints.form.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        {t("timetable.constraints.form.deleteText")}
      </ConfirmDialog>
    </DialogRoot>
  );
}

type FieldsProps = {
  kind: RuleKind;
  params: Params;
  set: (changes: Partial<Params>) => void;
  choices: RuleChoices;
  rooms: Room[];
  days: number[];
  maxLessons: number;
};

/** Les champs du type choisi (maquette : encadré des règles). */
function KindFields({ kind, params, set, choices, rooms, days, maxLessons }: FieldsProps) {
  const { t } = useTranslation();
  const courses = choices.courses;
  const day = (empty?: string) => (
    <DayField days={days} value={params.weekday ?? null} empty={empty} onChange={set} />
  );
  const target = (allowAll: boolean) => (
    <TargetField
      value={params.target ?? { scope: "all", value: "" }}
      onChange={(next) => set({ target: next })}
      courses={courses}
      allowAll={allowAll}
    />
  );

  switch (kind) {
    case "fixed_lesson": {
      const first = params.first ?? 1;
      const last = Number(params.last ?? 1);
      return (
        <>
          <CoursePicker
            id="rule-course"
            courses={courses}
            value={params.course ?? ""}
            onChange={(course) => set({ course })}
          />
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
            {day()}
            <LessonField
              id="rule-first"
              label={t("timetable.constraints.form.from")}
              max={maxLessons}
              value={first}
              onChange={(value) => set({ first: value, last: Math.max(value, last) })}
            />
            <LessonField
              id="rule-last"
              label={t("timetable.constraints.form.to")}
              max={maxLessons}
              value={last}
              onChange={(value) => set({ last: value, first: Math.min(value, first) })}
            />
          </div>
          <RoomField
            rooms={rooms}
            value={params.room ?? ""}
            empty={t("timetable.constraints.form.courseRoom")}
            help={t("timetable.constraints.form.courseRoomHelp")}
            onChange={(room) => set({ room: room || null })}
          />
        </>
      );
    }
    case "course_not_slot":
      return (
        <>
          {target(false)}
          {day(t("timetable.constraints.form.everyDay"))}
          <LessonToggles
            max={maxLessons}
            lessons={params.lessons ?? []}
            last={params.last === true}
            onChange={set}
          />
        </>
      );
    case "course_part_of_day":
      return (
        <>
          {target(false)}
          <div className="flex flex-col gap-2">
            <b className="text-sm text-ink-2">{t("timetable.constraints.form.part")}</b>
            <Segmented<"morning" | "afternoon">
              label={t("timetable.constraints.form.part")}
              value={params.part ?? "morning"}
              onValueChange={(part) => set({ part })}
              options={[
                { value: "morning", label: t("timetable.constraints.form.morning") },
                { value: "afternoon", label: t("timetable.constraints.form.afternoon") },
              ]}
              className="self-start max-[600px]:w-full"
            />
          </div>
          {day(t("timetable.constraints.form.everyDay"))}
        </>
      );
    case "parallel_courses":
      return <ParallelFields params={params} set={set} courses={courses} />;
    case "joint_courses":
      return <JointFields params={params} set={set} choices={choices} />;
    case "room_unavailable": {
      const whole = !params.start;
      return (
        <>
          <RoomField
            rooms={rooms}
            value={params.room ?? ""}
            empty={t("timetable.constraints.form.choose")}
            onChange={(room) => set({ room })}
          />
          {day()}
          <CheckboxField
            id="rule-whole-day"
            checked={whole}
            onCheckedChange={(checked) =>
              set(
                checked === true
                  ? { start: undefined, end: undefined }
                  : { start: "07:30", end: "12:00" },
              )
            }
            label={t("timetable.constraints.form.wholeDay")}
          />
          {!whole && (
            <div className="grid grid-cols-2 gap-3">
              {(["start", "end"] as const).map((key) => (
                <Field key={key} id={`rule-${key}`} label={t(`timetable.constraints.form.${key}`)}>
                  {(control) => (
                    <Input
                      {...control}
                      type="time"
                      value={params[key] ?? ""}
                      onChange={(event) => set({ [key]: event.target.value })}
                    />
                  )}
                </Field>
              ))}
            </div>
          )}
        </>
      );
    }
    case "spread_over_week":
      return (
        <>
          {target(true)}
          <CheckboxField
            id="rule-not-in-row"
            checked={params.no_consecutive_days !== false}
            onCheckedChange={(checked) => set({ no_consecutive_days: checked === true })}
            label={t("timetable.constraints.form.notInRow")}
          />
        </>
      );
    case "teacher_compact":
      return (
        <TeacherField
          teachers={choices.teachers}
          value={params.teacher ?? ""}
          empty={t("timetable.constraints.allTeachers")}
          onChange={(teacher) => set({ teacher: teacher || null })}
        />
      );
    case "teacher_free_day":
      return (
        <>
          <TeacherField
            teachers={choices.teachers}
            value={params.teacher ?? ""}
            empty={t("timetable.constraints.form.choose")}
            onChange={(teacher) => set({ teacher })}
          />
          {day(t("timetable.constraints.form.anyDay"))}
        </>
      );
  }
}

function classesOf(courses: RuleCourse[]): { id: string; name: string }[] {
  const seen = new Map<string, string>();
  for (const course of courses) seen.set(course.class_group, course.class_name);
  return [...seen].map(([id, name]) => ({ id, name }));
}

function DayField({
  days,
  value,
  empty,
  onChange,
}: {
  days: number[];
  value: number | null;
  empty?: string;
  onChange: (changes: Partial<Params>) => void;
}) {
  const { t } = useTranslation();
  return (
    <Field id="rule-day" label={t("timetable.constraints.form.day")}>
      {(control) => (
        <Select
          {...control}
          value={value ?? ""}
          onChange={(event) =>
            onChange({ weekday: event.target.value ? Number(event.target.value) : null })
          }
        >
          {empty !== undefined && <option value="">{empty}</option>}
          {days.map((weekday) => (
            <option key={weekday} value={weekday}>
              {t(`timetable.days.${dayKey(weekday)}`)}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

function LessonField(props: {
  id: string;
  label: string;
  max: number;
  value: number;
  onChange: (value: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <Field id={props.id} label={props.label}>
      {(control) => (
        <Select
          {...control}
          value={props.value}
          onChange={(event) => props.onChange(Number(event.target.value))}
        >
          {Array.from({ length: props.max }, (_, index) => index + 1).map((count) => (
            <option key={count} value={count}>
              {t("timetable.constraints.nthHour", { count })}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

function Toggle({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "min-h-9 rounded-pill px-3 py-1 text-sm font-bold ring-1 ring-inset",
        pressed ? "bg-due-50 text-due ring-due-200" : "bg-gray-50 text-ink-2 ring-line",
      )}
    >
      {children}
    </button>
  );
}

function LessonToggles(props: {
  max: number;
  lessons: number[];
  last: boolean;
  onChange: (changes: Partial<Params>) => void;
}) {
  const { t } = useTranslation();
  const flip = (count: number) =>
    props.onChange({
      lessons: props.lessons.includes(count)
        ? props.lessons.filter((item) => item !== count)
        : [...props.lessons, count].sort((a, b) => a - b),
    });
  return (
    <div className="flex flex-col gap-2">
      <b className="text-sm text-ink-2">{t("timetable.constraints.form.lessons")}</b>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: props.max }, (_, index) => index + 1).map((count) => (
          <Toggle key={count} pressed={props.lessons.includes(count)} onClick={() => flip(count)}>
            {t("timetable.constraints.nthHour", { count })}
          </Toggle>
        ))}
        <Toggle pressed={props.last} onClick={() => props.onChange({ last: !props.last })}>
          {t("timetable.constraints.form.lastLesson")}
        </Toggle>
      </div>
      <p className="text-sm text-ink-3">{t("timetable.constraints.form.lessonsHelp")}</p>
    </div>
  );
}

function CoursePicker({
  id,
  courses,
  value,
  onChange,
}: {
  id: string;
  courses: RuleCourse[];
  value: string;
  onChange: (course: string) => void;
}) {
  const { t } = useTranslation();
  const [classId, setClassId] = useState(
    () => courses.find((course) => course.id === value)?.class_group ?? "",
  );
  const mine = courses.filter((course) => course.class_group === classId);
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
      <Field id={`${id}-class`} label={t("timetable.constraints.form.class")}>
        {(control) => (
          <Select
            {...control}
            value={classId}
            onChange={(event) => {
              setClassId(event.target.value);
              onChange("");
            }}
          >
            <option value="">{t("timetable.constraints.form.choose")}</option>
            {classesOf(courses).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field id={id} label={t("timetable.constraints.form.course")}>
        {(control) => (
          <Select
            {...control}
            value={value}
            disabled={!classId}
            onChange={(event) => onChange(event.target.value)}
          >
            <option value="">{t("timetable.constraints.form.choose")}</option>
            {mine.map((course) => (
              <option key={course.id} value={course.id}>
                {t("timetable.constraints.form.courseOption", {
                  name: course.name,
                  hours: course.weekly_hours,
                  sessions: course.sessions.join(" + ") || "0",
                })}
              </option>
            ))}
          </Select>
        )}
      </Field>
    </div>
  );
}

function TargetField({
  value,
  onChange,
  courses,
  allowAll,
}: {
  value: Target;
  onChange: (target: Target) => void;
  courses: RuleCourse[];
  allowAll: boolean;
}) {
  const { t, i18n } = useTranslation();
  const names = [...new Set(courses.map((course) => course.name))].sort((a, b) =>
    a.localeCompare(b, i18n.language),
  );
  if (value.scope === "name" && value.value && !names.includes(value.value)) {
    names.unshift(value.value);
  }
  const encoded = value.scope === "course" ? "course:" : `${value.scope}:${value.value}`;
  return (
    <>
      <Field id="rule-target" label={t("timetable.constraints.form.target")}>
        {(control) => (
          <Select
            {...control}
            value={encoded}
            onChange={(event) => {
              const [scope = "all", ...rest] = event.target.value.split(":");
              onChange({
                scope: scope as Target["scope"],
                value: scope === "course" ? "" : rest.join(":"),
              });
            }}
          >
            {allowAll ? (
              <option value="all:">{t("timetable.constraints.allCourses")}</option>
            ) : (
              encoded === "name:" && (
                <option value="name:">{t("timetable.constraints.form.choose")}</option>
              )
            )}
            <optgroup label={t("timetable.constraints.form.byCategory")}>
              {CATEGORIES.map((category) => (
                <option key={category} value={`category:${category}`}>
                  {t(`timetable.constraints.categories.${category}`)}
                </option>
              ))}
            </optgroup>
            <optgroup label={t("timetable.constraints.form.byName")}>
              {names.map((name) => (
                <option key={name} value={`name:${name}`}>
                  {name}
                </option>
              ))}
            </optgroup>
            <option value="course:">{t("timetable.constraints.form.oneCourse")}</option>
          </Select>
        )}
      </Field>
      {value.scope === "course" && (
        <CoursePicker
          id="rule-target-course"
          courses={courses}
          value={value.value}
          onChange={(course) => onChange({ scope: "course", value: course })}
        />
      )}
    </>
  );
}

function RoomField(props: {
  rooms: Room[];
  value: string;
  empty: string;
  help?: string;
  onChange: (room: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Field id="rule-room" label={t("timetable.constraints.form.room")} help={props.help}>
      {(control) => (
        <Select
          {...control}
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
        >
          <option value="">{props.empty}</option>
          {props.rooms
            .filter((room) => room.is_active || room.id === props.value)
            .map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
        </Select>
      )}
    </Field>
  );
}

function TeacherField(props: {
  teachers: RuleChoices["teachers"];
  value: string;
  empty: string;
  onChange: (teacher: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Field id="rule-teacher" label={t("timetable.constraints.form.teacher")}>
      {(control) => (
        <Select
          {...control}
          value={props.value}
          onChange={(event) => props.onChange(event.target.value)}
        >
          <option value="">{props.empty}</option>
          {props.teachers.map((teacher) => (
            <option key={teacher.id} value={teacher.id}>
              {teacher.name}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

function CourseChecklist(props: {
  id: string;
  label: string;
  courses: RuleCourse[];
  value: string[];
  named: (course: RuleCourse) => string;
  onChange: (courses: string[]) => void;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-bold text-ink-2">{props.label}</legend>
      {props.courses.length === 0 ? (
        <p className="text-sm text-ink-3">{t("timetable.constraints.form.noCourses")}</p>
      ) : (
        props.courses.map((course) => (
          <CheckboxField
            key={course.id}
            id={`${props.id}-${course.id}`}
            checked={props.value.includes(course.id)}
            onCheckedChange={(checked) =>
              props.onChange(
                checked === true
                  ? [...props.value, course.id]
                  : props.value.filter((item) => item !== course.id),
              )
            }
            label={props.named(course)}
          />
        ))
      )}
    </fieldset>
  );
}

function ParallelFields({
  params,
  set,
  courses,
}: {
  params: Params;
  set: (changes: Partial<Params>) => void;
  courses: RuleCourse[];
}) {
  const { t } = useTranslation();
  const chosen = params.courses ?? [];
  const [classId, setClassId] = useState(
    () => courses.find((course) => course.id === chosen[0])?.class_group ?? "",
  );
  return (
    <>
      <Field id="rule-class" label={t("timetable.constraints.form.class")}>
        {(control) => (
          <Select
            {...control}
            value={classId}
            onChange={(event) => {
              setClassId(event.target.value);
              set({ courses: [] });
            }}
          >
            <option value="">{t("timetable.constraints.form.choose")}</option>
            {classesOf(courses).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {classId && (
        <CourseChecklist
          id="rule-parallel"
          label={t("timetable.constraints.form.parallelCourses")}
          courses={courses.filter((course) => course.class_group === classId)}
          value={chosen}
          named={(course) => `${course.name} · ${course.weekly_hours} h`}
          onChange={(next) => set({ courses: next })}
        />
      )}
    </>
  );
}

function JointFields({
  params,
  set,
  choices,
}: {
  params: Params;
  set: (changes: Partial<Params>) => void;
  choices: RuleChoices;
}) {
  const { t } = useTranslation();
  const chosen = params.courses ?? [];
  const [teacherId, setTeacherId] = useState(
    () => choices.courses.find((course) => course.id === chosen[0])?.teacher ?? "",
  );
  return (
    <>
      <TeacherField
        teachers={choices.teachers}
        value={teacherId}
        empty={t("timetable.constraints.form.choose")}
        onChange={(teacher) => {
          setTeacherId(teacher);
          set({ courses: [] });
        }}
      />
      {teacherId && (
        <CourseChecklist
          id="rule-joint"
          label={t("timetable.constraints.form.jointCourses")}
          courses={choices.courses.filter((course) => course.teacher === teacherId)}
          value={chosen}
          named={(course) => `${courseLabel(course)} · ${course.weekly_hours} h`}
          onChange={(next) => set({ courses: next })}
        />
      )}
    </>
  );
}
