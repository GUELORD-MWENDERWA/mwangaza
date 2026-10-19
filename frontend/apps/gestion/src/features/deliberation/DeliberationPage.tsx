// Délibération d'une classe (8.4.2, maquette `deliberation`) : pour chaque élève, la décision
// proposée d'après les règles de l'école (8.4.1) et la décision prise ; un écart demande un motif.
// Proclamer fige les résultats ; les corriger ensuite demande de rouvrir la classe (motif). La
// conduite et l'application se corrigent dans leurs écrans. Conseil (NB.5) : une session par période,
// semestre et fin d'année ; ses membres lisent le tableau (secret), la direction des études écrit ;
// procès-verbal imprimable une fois la session proclamée.
import { api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  cn,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { termLabels } from "../../lib/terms";
import { useGrading } from "../grades/data";
import { LoadError } from "../status/StatusPages";
import { CouncilCard } from "./CouncilCard";
import { RuleCited } from "./RuleCited";
import {
  DECISIONS,
  minutesUrl,
  priorPercent,
  SECOND,
  sessionQuery,
  sessionTerms,
  TONES,
  useClassDeliberation,
  type Decision,
  type DeliberationRow,
  type SessionResult,
} from "./data";

// `percent` : pourcentage repris d'un élève sans aucune note cette année (8.4.7).
type Draft = { decision: string; reason: string; percent: string };

export function DeliberationPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const grading = useGrading();
  // Ouverte depuis « Repêchage » : la classe et la seconde session.
  const [params] = useSearchParams();
  const [classId, setClassId] = useState(params.get("class") ?? "");
  // Vide : fin d'année ; `SECOND` : seconde session ; sinon une période, un semestre ou un trimestre.
  const [termId, setTermId] = useState(params.get("session") === SECOND ? SECOND : "");
  const second = termId === SECOND;
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [day, setDay] = useState<string | null>(null);
  const [reopenReason, setReopenReason] = useState("");

  const classes = grading.data?.classes ?? [];
  const groupId = classId || classes[0]?.id || "";
  const table = useClassDeliberation(groupId, termId);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.deliberation });
  const sessionPath = {
    params: { path: { id: groupId }, query: sessionQuery(termId) },
  };
  const terms = grading.data?.terms ?? [];
  const sessions = sessionTerms(terms, termLabels(terms, t));

  const saveDate = useMutation({
    mutationFn: (heldOn: string) =>
      call(
        api.PUT("/api/class-groups/{id}/deliberation/", {
          ...sessionPath,
          body: { held_on: heldOn },
        }),
      ),
    onSuccess: () => {
      setDay(null);
      refresh();
    },
  });
  const decide = useMutation({
    mutationFn: ({ id, draft, unranked }: { id: string; draft: Draft; unranked: boolean }) =>
      call(
        api.PUT("/api/deliberation/enrollments/{id}/", {
          params: { path: { id }, query: sessionQuery(termId) },
          body: {
            decision: draft.decision as Decision,
            reason: draft.reason,
            percent: unranked ? priorPercent(draft.percent) : null,
          },
        }),
      ),
    onSuccess: (_data, { id }) => {
      setDrafts((current) => {
        const rest = { ...current };
        delete rest[id];
        return rest;
      });
      refresh();
    },
  });
  const apply = useMutation({
    mutationFn: () =>
      call(api.POST("/api/class-groups/{id}/deliberation/apply-proposals/", sessionPath)),
    onSuccess: refresh,
  });
  const proclaim = useMutation({
    mutationFn: () => call(api.POST("/api/class-groups/{id}/deliberation/proclaim/", sessionPath)),
    onSuccess: refresh,
  });
  const reopen = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/class-groups/{id}/deliberation/reopen/", {
          ...sessionPath,
          body: { reason: reopenReason },
        }),
      ),
    onSuccess: () => {
      setReopenReason("");
      refresh();
    },
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const decisionPill = (value: string) =>
    value ? (
      <StatusPill tone={TONES[value] ?? "gray"}>
        {t(`deliberation.decision_${value as Decision}`)}
      </StatusPill>
    ) : null;

  const studentRow = (row: DeliberationRow, closed: boolean) => {
    // Sans aucune note cette année : le pourcentage se reprend (8.4.7), il ne se calcule pas.
    const unranked = row.outcome === "unranked";
    const saved = { decision: row.decision, reason: row.reason, percent: row.percent ?? "" };
    const draft = drafts[row.enrollment] ?? saved;
    const gap = Boolean(row.proposed && draft.decision && draft.decision !== row.proposed);
    const changed =
      draft.decision !== row.decision ||
      draft.reason !== row.reason ||
      (unranked && priorPercent(draft.percent) !== row.percent);
    return (
      <tr key={row.enrollment}>
        <td data-label={t("deliberation.student")} data-wrap>
          <span className="flex flex-wrap items-center gap-2">
            {row.full_name}
            {unranked && <StatusPill tone="gray">{t("deliberation.noGrades")}</StatusPill>}
          </span>
        </td>
        <td data-label={t("deliberation.year")} className="whitespace-nowrap tabular-nums">
          {unranked && !closed ? (
            <span className="flex items-center gap-2">
              <Input
                aria-label={t("deliberation.priorPercentFor", { name: row.full_name })}
                inputMode="decimal"
                maxLength={5}
                className="w-20"
                value={draft.percent}
                onChange={(event) =>
                  setDrafts({
                    ...drafts,
                    [row.enrollment]: { ...draft, percent: event.target.value },
                  })
                }
              />
              <span className="text-xs text-ink-3">{t("deliberation.priorPercent")}</span>
            </span>
          ) : row.percent === null ? (
            "—"
          ) : (
            t("deliberation.percent", { value: row.percent })
          )}
        </td>
        {second && (
          <td data-label={t("deliberation.resits")} data-wrap>
            {/* Un cours par ligne ; le résultat du repêchage en colonne, aligné. */}
            <span className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5">
              {row.resits.map((line) => (
                <Fragment key={line.course}>
                  <span>
                    {line.course}{" "}
                    <span className="whitespace-nowrap text-ink-3 tabular-nums">
                      {t("deliberation.percent", { value: line.percent })}
                    </span>
                  </span>
                  {line.resit_percent === null ? (
                    <span className="whitespace-nowrap text-xs text-ink-3">
                      {t("deliberation.resitAwaited")}
                    </span>
                  ) : (
                    <StatusPill tone={line.passed ? "ok" : "due"}>
                      {t(line.passed ? "deliberation.resitPassed" : "deliberation.resitFailed", {
                        value: line.resit_percent,
                      })}
                    </StatusPill>
                  )}
                </Fragment>
              ))}
            </span>
          </td>
        )}
        <td data-label={t("deliberation.proposed")}>
          <span className="flex flex-col items-end min-[600px]:items-start">
            {row.proposed ? (
              decisionPill(row.proposed)
            ) : (
              <span className="text-xs text-ink-3">{t("deliberation.noProposal")}</span>
            )}
            <RuleCited rule={row.rule} params={row.rule_params} />
          </span>
        </td>
        <td data-label={t("deliberation.decision")} data-wrap>
          {closed ? (
            <span className="flex flex-wrap items-center gap-2">
              {decisionPill(row.decision)}
              {row.deviates && <StatusPill tone="warn">{t("deliberation.gap")}</StatusPill>}
            </span>
          ) : (
            <span className="flex flex-wrap items-center gap-2">
              <Select
                aria-label={t("deliberation.decision")}
                className="w-44"
                value={draft.decision}
                onChange={(event) =>
                  setDrafts({
                    ...drafts,
                    [row.enrollment]: { ...draft, decision: event.target.value },
                  })
                }
              >
                <option value="">{t("deliberation.choose")}</option>
                {DECISIONS.filter((value) => !second || value !== "resit").map((value) => (
                  <option key={value} value={value}>
                    {t(`deliberation.decision_${value}`)}
                  </option>
                ))}
              </Select>
              {gap && <StatusPill tone="warn">{t("deliberation.gap")}</StatusPill>}
            </span>
          )}
        </td>
        <td data-label={t("deliberation.reason")} data-wrap>
          {closed ? (
            <span className="text-sm">{row.reason || "—"}</span>
          ) : gap || row.reason ? (
            <span className="flex flex-wrap items-center gap-2">
              <Input
                aria-label={t("deliberation.reasonFor", { name: row.full_name })}
                maxLength={300}
                className="min-w-48"
                value={draft.reason}
                onChange={(event) =>
                  setDrafts({
                    ...drafts,
                    [row.enrollment]: { ...draft, reason: event.target.value },
                  })
                }
              />
            </span>
          ) : (
            <span className="text-ink-3">—</span>
          )}
          {!closed && changed && draft.decision && (
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              disabled={decide.isPending || (gap && draft.reason.trim() === "")}
              onClick={() => decide.mutate({ id: row.enrollment, draft, unranked })}
            >
              {t("deliberation.save")}
            </Button>
          )}
        </td>
      </tr>
    );
  };

  const board = table.data;
  const closed = board?.status === "proclaimed";
  const failure = [saveDate, decide, apply, proclaim, reopen].find((m) => m.isError)?.error;
  const readOnly = board ? !board.can_edit : true;
  // Fin d'année et seconde session : une décision par élève.
  const year = !board || board.kind === "year" || board.kind === "second";
  const sessionLabel = (id: string, label: string) => {
    const state = board?.sessions.find(
      (item) => (item.second_session ? SECOND : (item.term ?? "")) === id,
    );
    return state ? `${label} · ${t(`deliberation.status_${state.status}`)}` : label;
  };
  const passed = board ? board.results.filter((row) => row.passed).length : 0;

  const sessionTable = (rows: SessionResult[], period: boolean) => (
    <Table stacked>
      <thead>
        <tr>
          <th className="text-right">{t("deliberation.number")}</th>
          <th>{t("deliberation.student")}</th>
          <th className="text-right">%</th>
          <th className="text-right">{t("deliberation.place")}</th>
          {period && <th>{t("deliberation.conduct")}</th>}
          {period && <th>{t("deliberation.application")}</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={row.enrollment}>
            <td className="text-right text-ink-3 tabular-nums">{index + 1}</td>
            <td className="font-semibold" data-wrap>
              {row.full_name}
            </td>
            <td
              data-label="%"
              className={cn(
                "text-right tabular-nums",
                row.percent !== null && !row.passed && "text-due",
              )}
            >
              {row.percent === null ? "—" : t("deliberation.percent", { value: row.percent })}
            </td>
            <td data-label={t("deliberation.place")} className="text-right tabular-nums">
              {row.place ?? "—"}
            </td>
            {period && <td data-label={t("deliberation.conduct")}>{row.conduct || "—"}</td>}
            {period && <td data-label={t("deliberation.application")}>{row.application || "—"}</td>}
          </tr>
        ))}
      </tbody>
    </Table>
  );

  return (
    <>
      <PageHeader title={t("deliberation.title")} subtitle={t("deliberation.subtitle")} />
      {classes.length === 0 ? (
        <Banner tone="info">{t("deliberation.noClass")}</Banner>
      ) : (
        <Card>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-3">
              <div className="min-w-56">
                <Field id="deliberation-class" label={t("deliberation.class")}>
                  {(control) => (
                    <Select
                      {...control}
                      value={groupId}
                      onChange={(event) => {
                        setClassId(event.target.value);
                        setDrafts({});
                        setDay(null);
                      }}
                    >
                      {classes.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              </div>
              <div className="min-w-56">
                <Field id="deliberation-session" label={t("deliberation.session")}>
                  {(control) => (
                    <Select
                      {...control}
                      value={termId}
                      onChange={(event) => {
                        setTermId(event.target.value);
                        setDrafts({});
                        setDay(null);
                      }}
                    >
                      {sessions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {sessionLabel(item.id, item.label)}
                        </option>
                      ))}
                      <option value="">{sessionLabel("", t("deliberation.endOfYear"))}</option>
                      {(board?.has_second_session || second) && (
                        <option value={SECOND}>
                          {sessionLabel(SECOND, t("deliberation.secondSession"))}
                        </option>
                      )}
                    </Select>
                  )}
                </Field>
              </div>
            </div>
            {table.isPending ? (
              <Skeleton label={t("common.loading")} />
            ) : table.isError || !board ? (
              <LoadError error={table.error} onRetry={() => void table.refetch()} />
            ) : (
              <>
                {readOnly && <Banner tone="info">{t("deliberation.secret")}</Banner>}
                <div className="flex flex-wrap items-end gap-3">
                  <Field id="deliberation-date" label={t("deliberation.date")}>
                    {(control) => (
                      <Input
                        {...control}
                        type="date"
                        disabled={closed || readOnly}
                        value={day ?? board.held_on ?? ""}
                        onChange={(event) => setDay(event.target.value)}
                      />
                    )}
                  </Field>
                  {!closed && !readOnly && day !== null && day !== "" && day !== board.held_on && (
                    <Button
                      variant="outline"
                      disabled={saveDate.isPending}
                      onClick={() => saveDate.mutate(day)}
                    >
                      {t("deliberation.saveDate")}
                    </Button>
                  )}
                  <StatusPill tone={closed ? "ok" : "warn"}>
                    {t(`deliberation.status_${board.status}`)}
                  </StatusPill>
                  <span className="text-sm text-ink-3">
                    {board.latest
                      ? t("deliberation.latest", {
                          version: board.latest.version,
                          date: formatDay(board.latest.proclaimed_at.slice(0, 10), i18n.language),
                          name: board.latest.proclaimed_by,
                        })
                      : t("deliberation.noneYet")}
                  </span>
                  {!year && (
                    <StatusPill tone={board.ready ? "ok" : "warn"}>
                      {t(board.ready ? "deliberation.ready" : "deliberation.notReady")}
                    </StatusPill>
                  )}
                </div>
                {!year && (
                  <div className="flex flex-wrap gap-2">
                    <StatusPill tone="gray">
                      {t("deliberation.students", { count: board.results.length })}
                    </StatusPill>
                    <StatusPill tone="ok">
                      {t("deliberation.passed", { count: passed, percent: board.pass_percent })}
                    </StatusPill>
                  </div>
                )}
                {year && (
                  <div className="flex flex-wrap gap-2">
                    {second && (
                      <StatusPill tone="gray">
                        {t("deliberation.secondStudents", { count: board.students.length })}
                      </StatusPill>
                    )}
                    {second && board.exam_on && (
                      <StatusPill tone="gray">
                        {t("deliberation.examOn", {
                          date: formatDay(board.exam_on, i18n.language),
                        })}
                      </StatusPill>
                    )}
                    {DECISIONS.filter((value) => board.counts[value]).map((value) => (
                      <StatusPill key={value} tone={TONES[value] ?? "gray"}>
                        {t(`deliberation.decision_${value}`)} {board.counts[value]}
                      </StatusPill>
                    ))}
                    {board.deviations > 0 && (
                      <StatusPill tone="warn">
                        {t("deliberation.gaps", { count: board.deviations })}
                      </StatusPill>
                    )}
                  </div>
                )}
                {!year && sessionTable(board.results, board.kind === "period")}
                {year && (
                  <Table stacked>
                    <thead>
                      <tr>
                        <th>{t("deliberation.student")}</th>
                        <th>{t("deliberation.year")}</th>
                        {second && <th>{t("deliberation.resits")}</th>}
                        <th>{t("deliberation.proposed")}</th>
                        <th>{t("deliberation.decision")}</th>
                        <th>{t("deliberation.reason")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {board.students.map((row) => studentRow(row, closed || readOnly))}
                    </tbody>
                  </Table>
                )}
                {failure && <Banner tone="due">{firstErrorMessage(failure, t)}</Banner>}
                {board.latest && (
                  <div>
                    <Button asChild variant={closed ? "default" : "outline"}>
                      <a href={minutesUrl(groupId, termId)} target="_blank" rel="noreferrer">
                        <Icon name="print" />
                        {t("deliberation.minutes")}
                      </a>
                    </Button>
                  </div>
                )}
                {readOnly ? null : closed ? (
                  <div className="flex flex-col gap-3">
                    <Banner tone="info">
                      {t("deliberation.proclaimedHelp")}
                      {board.latest?.reason && (
                        <> {t("deliberation.correction", { reason: board.latest.reason })}</>
                      )}
                    </Banner>
                    <div className="flex flex-wrap items-end gap-3">
                      <div className="min-w-64">
                        <Field id="deliberation-reopen" label={t("deliberation.reopenReason")}>
                          {(control) => (
                            <Input
                              {...control}
                              maxLength={300}
                              value={reopenReason}
                              onChange={(event) => setReopenReason(event.target.value)}
                            />
                          )}
                        </Field>
                      </div>
                      <Button
                        variant="outline"
                        disabled={reopen.isPending || reopenReason.trim() === ""}
                        onClick={() => reopen.mutate()}
                      >
                        {t("deliberation.reopen")}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {year && (
                      <Button
                        variant="outline"
                        disabled={apply.isPending}
                        onClick={() => apply.mutate()}
                      >
                        {t("deliberation.applyProposals")}
                      </Button>
                    )}
                    <Button
                      disabled={proclaim.isPending || !board.ready}
                      onClick={() => proclaim.mutate()}
                    >
                      {t(
                        second
                          ? "deliberation.proclaimSecond"
                          : year
                            ? "deliberation.proclaim"
                            : "deliberation.proclaimSession",
                      )}
                    </Button>
                    {!second && (
                      <>
                        <Button asChild variant="ghost">
                          <Link to="/conduct">{t("deliberation.fixConduct")}</Link>
                        </Button>
                        <Button asChild variant="ghost">
                          <Link to="/application">{t("deliberation.fixApplication")}</Link>
                        </Button>
                      </>
                    )}
                    {second && (
                      <Button asChild variant="ghost">
                        <Link to={`/resits?class=${groupId}`}>{t("deliberation.resitGrades")}</Link>
                      </Button>
                    )}
                    {year && !second && (
                      <Button asChild variant="ghost">
                        <Link to="/deliberation/prior-results">
                          {t("deliberation.importPrior")}
                        </Link>
                      </Button>
                    )}
                  </div>
                )}
                <p className="text-xs text-ink-3">
                  {t(
                    second
                      ? "deliberation.secondHelp"
                      : year
                        ? "deliberation.help"
                        : "deliberation.sessionHelp",
                  )}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      )}
      {board && (
        <CouncilCard
          key={`${groupId}-${termId}-${board.status}-${board.version}`}
          classId={groupId}
          termId={termId}
          council={board.council}
          editable={board.can_edit && !closed}
          onSaved={refresh}
        />
      )}
    </>
  );
}
