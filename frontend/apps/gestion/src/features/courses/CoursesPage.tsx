// Cours et maxima (8.1, maquette `cours-maxima`) : la grille de la classe choisie (cours, domaine,
// maximum par période, examen, heures, enseignant) s'enregistre d'un seul envoi ; un modèle
// officiel la pré-remplit, « Copier » la donne à d'autres classes. Droit `courses.configure`,
// en ligne seulement. Vue « Emploi du temps » (EDT.1b, `PlacementTable`) avec le droit
// `timetable.manage` : le placement de chaque cours part dans le même envoi. Examen et T.G. calculés (`grid.ts`), jamais saisis.
import { ApiError, api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
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
  Icon,
  Input,
  List,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Switch,
  Table,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { errorMessage, fieldMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { type ClassGroup, useClasses, useYears, type Year } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { useRooms, useTimetableRules } from "../timetable/data";
import {
  type Course,
  type OfficialGrid,
  useCourses,
  useOfficialGrids,
  useTeachingLoads,
} from "./data";
import { examMax, type GridRow, gridSummary, termCounts, yearMax } from "./grid";
import {
  EMPTY_PLACEMENT,
  patternProblem,
  placementBody,
  placementDraft,
  type PlacementDraft,
} from "./placement";
import { PlacementTable } from "./PlacementTable";

/** Cours en cours de saisie ; `key` : repère local (un nouveau cours n'a pas encore d'`id`). */
type GradeEntry = Course["grade_entry"];
type Category = Course["category"];
const CATEGORIES: Category[] = ["general", "main", "option", "practical"];

type Draft = {
  key: string;
  id?: string;
  name: string;
  domain: string;
  period_max: string;
  has_exam: boolean;
  is_taught: boolean;
  grade_entry: GradeEntry;
  category: Category;
  weekly_hours: string;
  teacher_id: string;
  placement: PlacementDraft;
};

type View = "report" | "timetable";

let lastKey = 0;
const newKey = () => `new-${++lastKey}`;

const toDraft = (course: Course): Draft => ({
  key: course.id,
  id: course.id,
  name: course.name,
  domain: course.domain,
  period_max: String(course.period_max),
  has_exam: course.has_exam,
  is_taught: course.is_taught,
  grade_entry: course.grade_entry,
  category: course.category,
  weekly_hours: course.weekly_hours ? String(course.weekly_hours) : "",
  teacher_id: course.teacher?.id ?? "",
  placement: placementDraft(course.placement),
});

const toRow = (draft: Draft): GridRow => ({
  period_max: Number(draft.period_max) || 0,
  has_exam: draft.has_exam,
  weekly_hours: Number(draft.weekly_hours) || null,
  teacher_id: draft.teacher_id || null,
});

const blank = (): Draft => ({
  key: newKey(),
  name: "",
  domain: "",
  period_max: "",
  has_exam: true,
  is_taught: true,
  grade_entry: "",
  category: "general",
  weekly_hours: "",
  teacher_id: "",
  placement: EMPTY_PLACEMENT,
});

/** Un modèle officiel remplace les lignes ; un cours du même nom garde son `id` et son
 *  enseignant (rien n'est enregistré avant « Enregistrer »). */
function fromGrid(grid: OfficialGrid, current: Draft[]): Draft[] {
  const same = new Map(current.map((draft) => [draft.name.trim().toLowerCase(), draft]));
  return grid.courses.map((course) => {
    const kept = same.get(course.name.toLowerCase());
    return {
      key: kept?.key ?? newKey(),
      id: kept?.id,
      name: course.name,
      domain: kept?.domain ?? "",
      period_max: String(course.period_max),
      has_exam: course.has_exam,
      is_taught: course.is_taught,
      grade_entry: kept?.grade_entry ?? "",
      category: course.category,
      weekly_hours: course.weekly_hours ? String(course.weekly_hours) : (kept?.weekly_hours ?? ""),
      teacher_id: kept?.teacher_id ?? "",
      placement: kept?.placement ?? EMPTY_PLACEMENT,
    };
  });
}

export function CoursesPage() {
  const { t } = useTranslation();
  const years = useYears();
  const year = years.data?.find((item) => item.is_current) ?? years.data?.[0];
  const classes = useClasses(year?.id ?? "");
  // `?class=` : ouvert depuis les contrôles avant le calcul (EDT.1b).
  const [params] = useSearchParams();
  const [chosen, setChosen] = useState<string | null>(params.get("class"));

  if (years.isPending || (year && classes.isPending)) {
    return <Skeleton label={t("common.loading")} />;
  }
  if (years.isError) return <LoadError error={years.error} onRetry={() => void years.refetch()} />;
  if (classes.isError) {
    return <LoadError error={classes.error} onRetry={() => void classes.refetch()} />;
  }
  const list = classes.data ?? [];
  const group = list.find((item) => item.id === chosen) ?? list[0];
  if (!year || !group) {
    return (
      <>
        <PageHeader title={t("courses.title")} subtitle={t("courses.subtitleEmpty")} />
        <Banner tone="info">
          {t(year ? "courses.noClass" : "courses.noYear")}{" "}
          <Link to="/organisation" className="font-bold underline">
            {t("courses.toOrganisation")}
          </Link>
        </Banner>
      </>
    );
  }
  return (
    <CourseGrid key={group.id} group={group} year={year} classes={list} onChoose={setChosen} />
  );
}

type GridProps = {
  group: ClassGroup;
  year: Year;
  classes: ClassGroup[];
  onChoose: (id: string) => void;
};

function CourseGrid({ group, year, classes, onChoose }: GridProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const courses = useCourses(group.id);
  const staff = useTeachingLoads();
  const grids = useOfficialGrids();
  const canPlace = can(useCurrentMe(), ["timetable.manage"]);
  const rooms = useRooms(canPlace);
  const rules = useTimetableRules(canPlace);
  const [view, setView] = useState<View>("report");
  // `null` : rien de changé depuis la dernière lecture.
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [leaving, setLeaving] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  // Programme officiel à appliquer sur une grille déjà remplie : confirmé d'abord.
  const [replacing, setReplacing] = useState<OfficialGrid | null>(null);

  const save = useMutation({
    mutationFn: (rows: Draft[]) =>
      call(
        api.PUT("/api/class-groups/{id}/courses/", {
          params: { path: { id: group.id } },
          body: {
            courses: rows.map((draft) => ({
              ...(draft.id ? { id: draft.id } : {}),
              name: draft.name,
              domain: draft.domain,
              period_max: Number(draft.period_max),
              has_exam: draft.has_exam,
              is_taught: draft.is_taught,
              grade_entry: draft.grade_entry,
              category: draft.category,
              weekly_hours: draft.weekly_hours ? Number(draft.weekly_hours) : null,
              teacher_id: draft.teacher_id || null,
              ...(canPlace ? { placement: placementBody(draft.placement) } : {}),
            })),
          },
        }),
      ),
    onSuccess: async (saved) => {
      queryClient.setQueryData([...keys.courses, group.id], saved);
      setDrafts(null);
      setNotice(t("courses.saved"));
      await queryClient.invalidateQueries({ queryKey: keys.teachingLoads });
    },
  });

  if (courses.isPending || staff.isPending) return <Skeleton label={t("common.loading")} />;
  if (courses.isError) {
    return <LoadError error={courses.error} onRetry={() => void courses.refetch()} />;
  }
  if (staff.isError) return <LoadError error={staff.error} onRetry={() => void staff.refetch()} />;

  const rows = drafts ?? courses.data.map(toDraft);
  const dirty = drafts !== null;
  const counts = termCounts(year.terms);
  const summary = gridSummary(rows.filter((draft) => draft.is_taught).map(toRow), counts);
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const edit = (next: Draft[]) => {
    setNotice(null);
    setDrafts(next);
  };
  const update = (target: Draft, change: Partial<Draft>) =>
    edit(rows.map((draft) => (draft === target ? { ...draft, ...change } : draft)));

  const fields = save.error instanceof ApiError ? save.error.fields : {};
  const errorsOf = (index: number) =>
    [
      "name",
      "id",
      "period_max",
      "weekly_hours",
      "teacher_id",
      "domain",
      "has_exam",
      "is_taught",
      "grade_entry",
      "category",
      "placement.lesson_pattern",
      "placement.max_per_day",
      "placement.room_id",
    ]
      .flatMap((field) => fields[`courses.${index}.${field}`] ?? [])
      .map((error) => fieldMessage(error.code, t));
  // Bandeau de domaine devant chaque série de cours du même domaine (l'ordre du bulletin ne change
  // pas) : nombre de cours et total des maxima de la période de la série.
  const bands = new Map<number, { domain: string; count: number; period: number }>();
  let band: { domain: string; count: number; period: number } | undefined;
  rows.forEach((draft, index) => {
    const domain = draft.domain.trim();
    if (domain === "") {
      band = undefined;
      return;
    }
    if (!band || band.domain !== domain) {
      band = { domain, count: 0, period: 0 };
      bands.set(index, band);
    }
    band.count += 1;
    band.period += Number(draft.period_max) || 0;
  });
  const domains = [...new Set(rows.map((draft) => draft.domain.trim()).filter(Boolean))];
  const grouped = () => {
    const first = new Map<string, number>();
    rows.forEach((draft, index) => {
      if (!first.has(draft.domain.trim())) first.set(draft.domain.trim(), index);
    });
    // Tri stable : seuls les cours d'un même domaine se rapprochent, les autres gardent leur ordre.
    edit(
      rows
        .map((draft, index) => ({ draft, index, key: first.get(draft.domain.trim()) ?? index }))
        .sort((a, b) => a.key - b.key || a.index - b.index)
        .map((item) => item.draft),
    );
  };
  const placed = Object.keys(fields).some((path) => /^courses\.\d+\./.test(path));
  // Séances qui ne font pas les heures : dit dans la ligne, l'envoi attend la correction.
  const unplaceable =
    canPlace &&
    rows.some((draft) =>
      patternProblem(draft.placement.lesson_pattern, Number(draft.weekly_hours) || 0),
    );
  const choose = (id: string) => (dirty ? setLeaving(id) : onChoose(id));

  return (
    <>
      <PageHeader
        title={t("courses.title")}
        subtitle={t("courses.subtitle", { name: group.name, year: year.name })}
        actions={
          <>
            <Select
              aria-label={t("courses.classChoice")}
              value={group.id}
              onChange={(event) => choose(event.target.value)}
              className="w-auto min-w-[200px]"
            >
              {classes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Button
              variant="outline"
              disabled={dirty || rows.length === 0 || classes.length < 2}
              title={dirty ? t("courses.copy.saveFirst") : undefined}
              onClick={() => setCopying(true)}
            >
              {t("courses.copy.open")}
            </Button>
            <Button
              disabled={!dirty || save.isPending || unplaceable}
              onClick={() => save.mutate(rows)}
            >
              {t("courses.save")}
            </Button>
          </>
        }
      />
      {notice && (
        <div className="mb-4">
          <Banner tone="ok">{notice}</Banner>
        </div>
      )}
      {save.isError && !placed && (
        <div className="mb-4">
          <Banner tone="due">{errorMessage(save.error, t)}</Banner>
        </div>
      )}
      {/* Contrôle et modèles au-dessus : la grille a besoin de toute la largeur. */}
      <div className="mb-4 grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[900px]:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("courses.control.title")}</CardTitle>
            {dirty && <StatusPill tone="warn">{t("courses.control.unsaved")}</StatusPill>}
          </CardHeader>
          <CardContent>
            <List className="text-sm">
              <div>
                <span>{t("courses.control.courses")}</span>
                <b>{summary.count}</b>
              </div>
              <div>
                <span>{t("courses.control.period")}</span>
                <b className="tabular-nums">{number(summary.period)}</b>
              </div>
              <div>
                <span>{t("courses.control.exam")}</span>
                <b className="tabular-nums">{number(summary.exam)}</b>
              </div>
              <div>
                <span>{t("courses.control.year")}</span>
                <b className="tabular-nums">{counts.periods ? number(summary.year) : "—"}</b>
              </div>
              <div>
                <span>{t("courses.control.hours")}</span>
                <b className="tabular-nums">
                  {t("courses.hoursValue", {
                    count: summary.hours,
                    value: number(summary.hours),
                  })}
                </b>
              </div>
              <div>
                <span>{t("courses.control.assigned")}</span>
                <b className={cn(summary.assigned < summary.count && "text-warn")}>
                  {summary.assigned} / {summary.count}
                </b>
              </div>
            </List>
            {summary.groups.length > 0 && (
              <>
                <h3 className="mt-4 mb-1 text-sm font-bold">{t("courses.control.groups")}</h3>
                <List className="text-sm">
                  {summary.groups.map((group) => (
                    <div key={`${group.max}-${group.hasExam}`}>
                      <span>
                        {group.hasExam
                          ? t("courses.control.group", {
                              max: number(group.max),
                              exam: number(2 * group.max),
                              year: number(
                                yearMax({ period_max: group.max, has_exam: true }, counts),
                              ),
                            })
                          : t("courses.control.groupNoExam", {
                              max: number(group.max),
                              year: number(
                                yearMax({ period_max: group.max, has_exam: false }, counts),
                              ),
                            })}
                      </span>
                      <b className="whitespace-nowrap">
                        {t("courses.control.groupCount", { count: group.count })}
                      </b>
                    </div>
                  ))}
                </List>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle>{t("courses.templates.title")}</CardTitle>
              <p className="text-sm text-ink-3">{t("courses.templates.lead")}</p>
            </div>
          </CardHeader>
          <CardContent>
            {grids.isError ? (
              <Banner tone="due">{errorMessage(grids.error, t)}</Banner>
            ) : (
              <List className="text-sm">
                {(grids.data ?? []).map((grid) => {
                  const taught = grid.courses.filter((course) => course.is_taught);
                  const hours = taught.reduce((sum, course) => sum + (course.weekly_hours ?? 0), 0);
                  const maximum = taught.reduce((sum, course) => sum + course.period_max, 0);
                  return (
                    <div key={grid.key}>
                      <span>
                        <b>
                          {t(`courses.templates.names.${grid.key as "electricity"}`, {
                            defaultValue: grid.key,
                          })}
                        </b>{" "}
                        · {grid.reference}
                        <span className="block text-xs text-ink-3">
                          {t("courses.templates.summary", {
                            count: taught.length,
                            max: number(maximum),
                          })}
                          {hours > 0 && ` · ${t("courses.templates.hours", { hours })}`}
                        </span>
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          rows.length > 0 ? setReplacing(grid) : edit(fromGrid(grid, rows))
                        }
                      >
                        {t("courses.templates.apply")}
                      </Button>
                    </div>
                  );
                })}
              </List>
            )}
          </CardContent>
          <CardFooter>
            <p className="text-sm text-ink-2">{t("courses.templates.help")}</p>
          </CardFooter>
        </Card>
      </div>
      {canPlace && (
        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
          <Segmented<View>
            label={t("timetable.placement.view")}
            value={view}
            onValueChange={setView}
            options={[
              { value: "report", label: t("timetable.placement.report") },
              { value: "timetable", label: t("timetable.placement.timetable") },
            ]}
            className="max-[600px]:w-full"
          />
          <p className="text-sm text-ink-2">
            {t("timetable.placement.viewHelp")}{" "}
            <Link to="/timetable-checks" className="font-bold underline">
              {t("timetable.placement.checksLink")}
            </Link>
          </p>
        </div>
      )}
      <Card>
        {view === "timetable" && canPlace ? (
          <PlacementTable
            rows={rows}
            rooms={rooms.data ?? []}
            schoolMaxPerDay={rules.data?.max_same_course_per_day ?? 2}
            errorsOf={errorsOf}
            onChange={update}
          />
        ) : (
          // Tableau figé (2026-10-27) : la branche reste visible en allant jusqu'à l'enseignant.
          <Table freeze>
            <thead>
              <tr>
                <th>{t("courses.columns.name")}</th>
                <th>{t("courses.columns.domain")}</th>
                <th className="text-right">{t("courses.columns.periodMax")}</th>
                <th>{t("courses.columns.exam")}</th>
                <th className="text-right">{t("courses.columns.examMax")}</th>
                <th className="text-right">{t("courses.columns.year")}</th>
                <th>{t("courses.columns.taught")}</th>
                <th>{t("courses.columns.entry")}</th>
                <th>{t("courses.columns.category")}</th>
                <th className="text-right">{t("courses.columns.hours")}</th>
                <th>{t("courses.columns.teacher")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={11} className="text-center text-ink-2">
                    {t("courses.empty")}
                  </td>
                </tr>
              )}
              {rows.map((draft, index) => {
                const row = toRow(draft);
                const label = draft.name || t("courses.newCourse");
                const errors = errorsOf(index);
                const band = bands.get(index);
                return (
                  <Fragment key={draft.key}>
                    {band && (
                      <tr className="[&_td]:bg-lake-50">
                        <td colSpan={12} className="text-sm font-bold text-lake-700">
                          {t("courses.band", {
                            domain: band.domain,
                            count: band.count,
                            period: number(band.period),
                          })}
                        </td>
                      </tr>
                    )}
                    <tr>
                      <td>
                        <Input
                          aria-label={t("courses.columns.name")}
                          value={draft.name}
                          onChange={(event) => update(draft, { name: event.target.value })}
                          className="min-w-[220px] font-bold"
                        />
                        {errors.map((error) => (
                          <p key={error} role="alert" className="mt-1 text-xs text-due">
                            {error}
                          </p>
                        ))}
                      </td>
                      <td>
                        <Input
                          aria-label={`${t("courses.columns.domain")} | ${label}`}
                          list="course-domains"
                          value={draft.domain}
                          onChange={(event) => update(draft, { domain: event.target.value })}
                          className="min-w-[120px]"
                        />
                      </td>
                      <td className="text-right">
                        <Input
                          aria-label={`${t("courses.columns.periodMax")} | ${label}`}
                          inputMode="numeric"
                          value={draft.period_max}
                          onChange={(event) =>
                            update(draft, { period_max: event.target.value.replace(/\D/g, "") })
                          }
                          className="ml-auto w-[76px] text-right"
                        />
                      </td>
                      <td>
                        <Switch
                          aria-label={`${t("courses.columns.exam")} | ${label}`}
                          checked={draft.has_exam}
                          onCheckedChange={(checked) => update(draft, { has_exam: checked })}
                        />
                      </td>
                      <td className="text-right whitespace-nowrap tabular-nums">
                        {row.period_max ? (
                          row.has_exam ? (
                            number(examMax(row)!)
                          ) : (
                            <span className="text-ink-2">{t("courses.noExam")}</span>
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="text-right font-bold tabular-nums">
                        {row.period_max && counts.periods ? number(yearMax(row, counts)) : "—"}
                      </td>
                      <td>
                        <Switch
                          aria-label={`${t("courses.columns.taught")} | ${label}`}
                          checked={draft.is_taught}
                          onCheckedChange={(checked) => update(draft, { is_taught: checked })}
                        />
                      </td>
                      <td>
                        <Select
                          aria-label={`${t("courses.columns.entry")} | ${label}`}
                          value={draft.grade_entry}
                          onChange={(event) =>
                            update(draft, { grade_entry: event.target.value as GradeEntry })
                          }
                          className="min-w-[150px]"
                        >
                          <option value="">{t("courses.entry.school")}</option>
                          <option value="detailed">{t("courses.entry.detailed")}</option>
                          <option value="totals">{t("courses.entry.totals")}</option>
                        </Select>
                      </td>
                      <td>
                        <Select
                          aria-label={`${t("courses.columns.category")} | ${label}`}
                          value={draft.category}
                          onChange={(event) =>
                            update(draft, { category: event.target.value as Category })
                          }
                          className="min-w-[130px]"
                        >
                          {CATEGORIES.map((category) => (
                            <option key={category} value={category}>
                              {t(`courses.category.${category}`)}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="text-right">
                        <Input
                          aria-label={`${t("courses.columns.hours")} | ${label}`}
                          inputMode="numeric"
                          value={draft.weekly_hours}
                          onChange={(event) =>
                            update(draft, { weekly_hours: event.target.value.replace(/\D/g, "") })
                          }
                          className="ml-auto w-[64px] text-right"
                        />
                      </td>
                      <td>
                        <Select
                          aria-label={`${t("courses.columns.teacher")} | ${label}`}
                          value={draft.teacher_id}
                          onChange={(event) => update(draft, { teacher_id: event.target.value })}
                          className="min-w-[180px]"
                        >
                          <option value="">{t("courses.unassigned")}</option>
                          {staff.data.loads.map(({ teacher }) => (
                            <option key={teacher.id} value={teacher.id}>
                              {fullName(teacher)}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="w-10">
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={t("courses.remove", { name: label })}
                          onClick={() => edit(rows.filter((other) => other !== draft))}
                        >
                          <Icon name="x" size={16} />
                        </Button>
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
            {rows.length > 0 && (
              <tfoot>
                <tr className="font-bold [&_td]:bg-table-head">
                  <td colSpan={2}>{t("courses.totals")}</td>
                  <td className="text-right tabular-nums">{number(summary.period)}</td>
                  <td />
                  <td className="text-right tabular-nums">{number(summary.exam)}</td>
                  <td className="text-right tabular-nums">
                    {counts.periods ? number(summary.year) : "—"}
                  </td>
                  <td colSpan={3} />
                  <td className="text-right tabular-nums">{number(summary.hours)}</td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            )}
          </Table>
        )}
        <datalist id="course-domains">
          {domains.map((domain) => (
            <option key={domain} value={domain} />
          ))}
        </datalist>
        <CardFooter className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => edit([...rows, blank()])}>
            <Icon name="plus" size={14} />
            {t("courses.add")}
          </Button>
          {domains.length > 0 && (
            <Button variant="outline" size="sm" onClick={grouped}>
              {t("courses.groupByDomain")}
            </Button>
          )}
        </CardFooter>
      </Card>
      <ConfirmDialog
        open={replacing !== null}
        onOpenChange={(open) => !open && setReplacing(null)}
        title={t("courses.templates.replaceTitle")}
        confirmLabel={t("courses.templates.apply")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => {
          if (replacing) edit(fromGrid(replacing, rows));
          setReplacing(null);
        }}
      >
        {t("courses.templates.replaceBody", { count: rows.length, name: group.name })}
      </ConfirmDialog>
      <ConfirmDialog
        open={leaving !== null}
        onOpenChange={(open) => !open && setLeaving(null)}
        title={t("courses.leave.title")}
        confirmLabel={t("courses.leave.confirm")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          if (leaving) onChoose(leaving);
          setLeaving(null);
        }}
      >
        {t("courses.leave.body", { name: group.name })}
      </ConfirmDialog>
      <CopyDialog
        open={copying}
        onOpenChange={setCopying}
        group={group}
        classes={classes}
        onCopied={(count) => setNotice(t("courses.copy.done", { count }))}
      />
    </>
  );
}

type CopyProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group: ClassGroup;
  classes: ClassGroup[];
  onCopied: (count: number) => void;
};

function CopyDialog({ open, onOpenChange, group, classes, onCopied }: CopyProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [targets, setTargets] = useState<string[]>([]);
  const copy = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/class-groups/{id}/courses/copy/", {
          params: { path: { id: group.id } },
          body: { class_groups: targets },
        }),
      ),
    onSuccess: async ({ copied }) => {
      onCopied(copied);
      onOpenChange(false);
      setTargets([]);
      await queryClient.invalidateQueries({ queryKey: keys.courses });
      await queryClient.invalidateQueries({ queryKey: keys.teachingLoads });
    },
  });
  const others = classes.filter((item) => item.id !== group.id);
  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={t("courses.copy.title", { name: group.name })}
        description={t("courses.copy.help")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button disabled={targets.length === 0 || copy.isPending} onClick={() => copy.mutate()}>
              {t("courses.copy.submit", { count: targets.length })}
            </Button>
          </>
        }
      >
        {copy.isError && <Banner tone="due">{errorMessage(copy.error, t)}</Banner>}
        <div className="grid grid-cols-[minmax(0,1fr)] gap-2.5 min-[600px]:grid-cols-2">
          {others.map((item) => (
            <CheckboxField
              key={item.id}
              id={`copy-${item.id}`}
              label={item.name}
              checked={targets.includes(item.id)}
              onCheckedChange={(checked) =>
                setTargets((current) =>
                  checked ? [...current, item.id] : current.filter((id) => id !== item.id),
                )
              }
            />
          ))}
        </div>
      </DialogContent>
    </DialogRoot>
  );
}
