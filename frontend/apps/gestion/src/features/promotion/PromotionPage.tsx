// Passage de classe (8.4.5, maquette `passage-classe`) : classes de l'année finie, puis élèves
// d'une classe avec la décision proclamée, la place proposée (modifiable), la réponse du parent au
// Portail et l'état ; trois actions en lot. Rien n'est inscrit sans l'école.
import { api, call } from "@mwangaza/api";
import { formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  buttonVariants,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { TONES, type Decision } from "../deliberation/data";
import { LoadError } from "../status/StatusPages";
import {
  type ClassPassage,
  destination,
  type PassageRow,
  type Promotion,
  rowActions,
  useClassPassage,
  usePromotion,
} from "./data";

export function PromotionPage() {
  const { t, i18n } = useTranslation();
  const summary = usePromotion();
  const [classId, setClassId] = useState("");

  if (summary.isPending) return <Skeleton label={t("common.loading")} />;
  if (summary.isError) {
    return <LoadError error={summary.error} onRetry={() => void summary.refetch()} />;
  }
  const { year, following, classes } = summary.data;
  const chosen = classId || (classes.find((item) => item.proclaimed_on) ?? classes[0])?.id || "";

  return (
    <>
      <PageHeader
        title={t("promotion.title")}
        subtitle={
          year && following
            ? t("promotion.subtitle", { from: year.name, to: following.name })
            : t("promotion.subtitleNoYear")
        }
      />
      {!following ? (
        <Banner
          tone="info"
          action={
            <Link to="/organisation" className={buttonVariants({ variant: "outline", size: "sm" })}>
              {t("promotion.createYear")}
            </Link>
          }
        >
          {t("promotion.noNextYear")}
        </Banner>
      ) : (
        <>
          <ClassesCard
            data={summary.data}
            chosen={chosen}
            onChoose={setClassId}
            language={i18n.language}
          />
          {chosen && <ClassPlaces key={chosen} classId={chosen} />}
        </>
      )}
    </>
  );
}

function count(value: number | undefined) {
  return value ? value : "—";
}

function ClassesCard({
  data,
  chosen,
  onChoose,
  language,
}: {
  data: Promotion;
  chosen: string;
  onChoose: (id: string) => void;
  language: string;
}) {
  const { t } = useTranslation();
  const { year, following, classes } = data;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("promotion.classesOf", { year: year?.name })}</CardTitle>
        {following && (
          <span className="text-sm text-ink-3">
            {t("promotion.startsOn", {
              year: following.name,
              date: formatDay(following.starts_on, language),
            })}
          </span>
        )}
      </CardHeader>
      {classes.length === 0 ? (
        <CardContent>
          <Banner tone="info">{t("promotion.noClass")}</Banner>
        </CardContent>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("promotion.class")}</th>
              <th>{t("promotion.decisions")}</th>
              <th className="text-right">{t("promotion.students")}</th>
              <th className="text-right">{t("promotion.offered")}</th>
              <th className="text-right">{t("promotion.yes")}</th>
              <th className="text-right">{t("promotion.no")}</th>
              <th className="text-right">{t("promotion.noAnswer")}</th>
              <th className="text-right">{t("promotion.enrolledIn", { year: following?.name })}</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((item) => (
              <tr key={item.id} aria-selected={item.id === chosen}>
                <td>
                  <button
                    type="button"
                    className="font-bold hover:underline focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
                    onClick={() => onChoose(item.id)}
                  >
                    {item.name}
                  </button>
                </td>
                <td data-label={t("promotion.decisions")}>
                  <StatusPill tone={item.proclaimed_on ? "ok" : "warn"}>
                    {item.proclaimed_on ? t("promotion.proclaimed") : t("promotion.notProclaimed")}
                  </StatusPill>
                </td>
                <td data-label={t("promotion.students")} className="text-right tabular-nums">
                  {item.counts.students}
                </td>
                <td data-label={t("promotion.offered")} className="text-right tabular-nums">
                  {item.counts.offered}
                </td>
                <td data-label={t("promotion.yes")} className="text-right tabular-nums">
                  {count(item.counts.yes)}
                </td>
                <td data-label={t("promotion.no")} className="text-right tabular-nums">
                  {count(item.counts.no)}
                </td>
                <td data-label={t("promotion.noAnswer")} className="text-right tabular-nums">
                  {count(item.counts.no_answer)}
                </td>
                <td
                  data-label={t("promotion.enrolledIn", { year: following?.name })}
                  className="text-right tabular-nums"
                >
                  {item.counts.enrolled}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function ClassPlaces({ classId }: { classId: string }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const table = useClassPassage(classId);
  const [selected, setSelected] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const done = () => {
    setSelected([]);
    setDrafts({});
    void queryClient.invalidateQueries({ queryKey: keys.promotion });
  };
  const path = { params: { path: { id: classId } } };
  const offer = useMutation({
    mutationFn: (places: { enrollment: string; class_group: string }[]) =>
      call(api.POST("/api/class-groups/{id}/promotion/offer/", { ...path, body: { places } })),
    onSuccess: done,
  });
  const enroll = useMutation({
    mutationFn: (enrollments: string[]) =>
      call(
        api.POST("/api/class-groups/{id}/promotion/enroll/", { ...path, body: { enrollments } }),
      ),
    onSuccess: done,
  });
  const withdraw = useMutation({
    mutationFn: (enrollments: string[]) =>
      call(
        api.POST("/api/class-groups/{id}/promotion/withdraw/", { ...path, body: { enrollments } }),
      ),
    onSuccess: done,
  });

  if (table.isPending) return <Skeleton label={t("common.loading")} />;
  if (table.isError) return <LoadError error={table.error} onRetry={() => void table.refetch()} />;

  const board: ClassPassage = table.data;
  const following = board.following?.name ?? "";
  const actionable = board.students.filter((row) => Object.values(rowActions(row)).some(Boolean));
  const chosen = board.students.filter((row) => selected.includes(row.enrollment));
  const toOffer = chosen.filter((row) => rowActions(row).offer && destination(row, drafts));
  const toEnroll = chosen.filter((row) => rowActions(row).enroll);
  const busy = offer.isPending || enroll.isPending || withdraw.isPending;
  const failure = [offer, enroll, withdraw].find((m) => m.isError)?.error;
  const select = (ids: string[], on: boolean) =>
    setSelected((current) =>
      on ? [...new Set([...current, ...ids])] : current.filter((id) => !ids.includes(id)),
    );

  const decisionPill = (row: PassageRow) =>
    row.decision ? (
      <StatusPill tone={TONES[row.decision] ?? "gray"}>
        {t(`deliberation.decision_${row.decision as Decision}`)}
      </StatusPill>
    ) : (
      <span className="text-ink-3">—</span>
    );

  const placeCell = (row: PassageRow) => {
    if (row.enrolled_class) return row.enrolled_class;
    if (!rowActions(row).offer) {
      return <span className="text-ink-3">{t(`promotion.proposal_${row.proposal}`)}</span>;
    }
    return (
      <Select
        aria-label={t("promotion.placeFor", { name: row.full_name })}
        className="min-w-48"
        value={destination(row, drafts)}
        onChange={(event) => {
          setDrafts({ ...drafts, [row.enrollment]: event.target.value });
          select([row.enrollment], true);
        }}
      >
        <option value="">{t("promotion.choose")}</option>
        {board.targets.map((target) => (
          <option key={target.id} value={target.id}>
            {target.name}
          </option>
        ))}
      </Select>
    );
  };

  const parentCell = (row: PassageRow) => {
    const place = row.place;
    if (!place || place.status !== "offered" || row.enrolled_class) {
      return <span className="text-ink-3">—</span>;
    }
    if (!place.answer) {
      return row.on_portal ? (
        <StatusPill tone="gray">{t("promotion.noAnswer")}</StatusPill>
      ) : (
        <span className="text-sm text-ink-3">{t("promotion.noPortal")}</span>
      );
    }
    return (
      <span className="flex flex-col items-end gap-1 sm:items-start">
        <StatusPill tone={place.answer === "yes" ? "ok" : "due"}>
          {t(place.answer === "yes" ? "promotion.yes" : "promotion.no")}
        </StatusPill>
        {place.answered_at && (
          <span className="text-sm text-ink-3">
            {formatDate(place.answered_at, i18n.language, school.timezone)}
          </span>
        )}
      </span>
    );
  };

  const stateCell = (row: PassageRow) => {
    if (row.enrolled_class) return <StatusPill tone="ok">{t("promotion.enrolled")}</StatusPill>;
    if (row.place?.status === "offered") {
      return <StatusPill tone="info">{t("promotion.statusOffered")}</StatusPill>;
    }
    if (row.place?.status === "withdrawn") {
      return <StatusPill tone="gray">{t("promotion.statusWithdrawn")}</StatusPill>;
    }
    if (rowActions(row).offer) {
      return <StatusPill tone="gray">{t("promotion.toOffer")}</StatusPill>;
    }
    return <span className="text-ink-3">—</span>;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("promotion.classTo", { name: board.class_name, year: following })}</CardTitle>
        <StatusPill tone={board.proclaimed_on ? "ok" : "warn"}>
          {board.proclaimed_on
            ? t("promotion.proclaimedOn", {
                date: formatDay(board.proclaimed_on, i18n.language),
              })
            : t("promotion.notProclaimed")}
        </StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {!board.proclaimed_on && <Banner tone="warn">{t("promotion.proclaimFirst")}</Banner>}
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="info">
            {t("promotion.offered")} {board.counts.offered}
          </StatusPill>
          <StatusPill tone="ok">
            {t("promotion.yes")} {board.counts.yes}
          </StatusPill>
          <StatusPill tone="due">
            {t("promotion.no")} {board.counts.no}
          </StatusPill>
          <StatusPill tone="gray">
            {t("promotion.noAnswer")} {board.counts.no_answer}
          </StatusPill>
          <StatusPill tone="ok">
            {t("promotion.enrolled")} {board.counts.enrolled}
          </StatusPill>
        </div>
      </CardContent>
      <Table stacked>
        <thead>
          <tr>
            <th className="w-10">
              <Checkbox
                aria-label={t("promotion.selectAll")}
                disabled={actionable.length === 0}
                checked={
                  selected.length === 0
                    ? false
                    : selected.length === actionable.length || "indeterminate"
                }
                onCheckedChange={(checked) =>
                  select(
                    actionable.map((row) => row.enrollment),
                    checked === true,
                  )
                }
              />
            </th>
            <th>{t("promotion.student")}</th>
            <th>{t("promotion.decision")}</th>
            <th>{t("promotion.placeIn", { year: following })}</th>
            <th>{t("promotion.parent")}</th>
            <th>{t("promotion.state")}</th>
          </tr>
        </thead>
        <tbody>
          {board.students.map((row) => (
            <tr key={row.enrollment}>
              <td className="stack-check">
                {Object.values(rowActions(row)).some(Boolean) && (
                  <Checkbox
                    aria-label={t("promotion.select", { name: row.full_name })}
                    checked={selected.includes(row.enrollment)}
                    onCheckedChange={(checked) => select([row.enrollment], checked === true)}
                  />
                )}
              </td>
              <td className="min-w-44">
                <b>{row.full_name}</b>
                <span className="block text-sm text-ink-3">
                  {[row.matricule, row.percent && t("deliberation.percent", { value: row.percent })]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </td>
              <td data-label={t("promotion.decision")}>{decisionPill(row)}</td>
              <td data-label={t("promotion.placeIn", { year: following })}>{placeCell(row)}</td>
              <td data-label={t("promotion.parent")}>{parentCell(row)}</td>
              <td data-label={t("promotion.state")}>{stateCell(row)}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      <CardContent className="flex flex-col gap-3">
        {failure && <Banner tone="due">{firstErrorMessage(failure, t)}</Banner>}
        <p className="text-sm text-ink-3">{t("promotion.help")}</p>
      </CardContent>
      <CardFooter className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ink-3">
          {t("promotion.selected", { count: selected.length })}
        </span>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy || toEnroll.length === 0}
            onClick={() => withdraw.mutate(toEnroll.map((row) => row.enrollment))}
          >
            {t("promotion.withdraw", { count: toEnroll.length })}
          </Button>
          <Button
            variant="outline"
            disabled={busy || toEnroll.length === 0}
            onClick={() => enroll.mutate(toEnroll.map((row) => row.enrollment))}
          >
            {t("promotion.enroll", { year: following, count: toEnroll.length })}
          </Button>
          <Button
            disabled={busy || toOffer.length === 0}
            onClick={() =>
              offer.mutate(
                toOffer.map((row) => ({
                  enrollment: row.enrollment,
                  class_group: destination(row, drafts),
                })),
              )
            }
          >
            {t("promotion.offer", { count: toOffer.length })}
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
