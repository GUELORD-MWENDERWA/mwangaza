// Calcul automatique de l'horaire (EDT.3b, maquette `gestion/calcul-emploi-du-temps`, spec § 7) :
// brouillon de départ, portée et temps ; suivi, annulation, résultat. Le serveur calcule (EDT.3a)
// et le résultat est un nouveau brouillon. Droit `timetable.manage`, module `timetable` ; en ligne.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDateTime, formatTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { useCurrentSchool } from "../../lib/school";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import {
  type Run,
  type RunScope,
  STATUS_TONE,
  blockingReason,
  clock,
  defaultTime,
  isActive,
  timeChoices,
  unmetReason,
} from "./calculation";
import {
  draftListKey,
  runsKey,
  useDrafts,
  useRooms,
  useRuleChoices,
  useRules,
  useRuns,
  useTimetableChecks,
  useTimetableClasses,
} from "./data";
import { describe, lookupOf } from "./rules";

const SCOPES: RunScope[] = ["all", "class", "teacher"];

/** L'heure qui avance, seulement pendant un calcul (la barre du temps écoulé). */
function useNow(on: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!on) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [on]);
  return now;
}

function Line({ subject, text, action }: { subject: string; text: string; action?: ReactNode }) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-line-soft py-3 last:border-b-0">
      <div className="flex min-w-0 flex-1 basis-[240px] flex-col gap-0.5">
        <b>{subject}</b>
        {text && <span className="text-sm text-ink-2">{text}</span>}
      </div>
      {action}
    </li>
  );
}

export function CalculatePage() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const years = useYears();
  const list = useRuns();
  const drafts = useDrafts();
  const checks = useTimetableChecks();
  const classes = useTimetableClasses();
  const choices = useRuleChoices();
  const runs = list.data?.runs ?? [];
  const shown = runs.find((run) => run.id === params.get("run")) ?? runs[0];
  const needsRules = [...(shown?.blocking ?? []), ...(shown?.unmet ?? [])].some(
    (row) => row.code === "rule",
  );
  const rules = useRules(needsRules);
  const rooms = useRooms(needsRules);
  const lookup = useMemo(() => lookupOf(choices.data, rooms.data), [choices.data, rooms.data]);
  const now = useNow(isActive(shown));

  const [draftChoice, setDraftChoice] = useState(params.get("draft") ?? "");
  const [scope, setScope] = useState<RunScope>("all");
  const [target, setTarget] = useState("");
  const [seconds, setSeconds] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  // Une demande = un identifiant (deux appuis ou une reprise après coupure = un seul calcul).
  const requestId = useRef(uuidv7());

  const draft = drafts.data?.find((item) => item.id === draftChoice)?.id ?? drafts.data?.[0]?.id;
  const max = list.data?.time_limit_max ?? 60;
  const time = Math.min(seconds ?? defaultTime(max), max);

  // Calcul fini avec un résultat : la liste des brouillons le montre.
  const result = runs[0]?.result;
  useEffect(() => {
    if (result) void queryClient.invalidateQueries({ queryKey: draftListKey });
  }, [result, queryClient]);

  const start = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/timetable/runs/", {
          body: {
            request_id: requestId.current,
            timetable: draft ?? "",
            scope,
            target: scope === "all" ? null : target,
            time_limit: time,
          },
        }),
      ),
    onSuccess: (run) => {
      requestId.current = uuidv7();
      queryClient.setQueryData(runsKey, (old: Schemas["RunList"] | undefined) =>
        old ? { ...old, runs: [run, ...old.runs.filter((item) => item.id !== run.id)] } : old,
      );
      void queryClient.invalidateQueries({ queryKey: runsKey });
      setParams(
        (current) => {
          current.delete("run");
          return current;
        },
        { replace: true },
      );
    },
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      call(api.POST("/api/timetable/runs/{id}/cancel/", { params: { path: { id } } })),
    onSettled: () => {
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: runsKey });
    },
  });

  const queries = [years, list, drafts, checks, classes, choices];
  if (queries.some((query) => query.isPending)) return <Skeleton label={t("common.loading")} />;
  const failed = queries.find((query) => query.isError);
  if (failed) return <LoadError error={failed.error} onRetry={() => void failed.refetch()} />;

  const year = years.data?.find((item) => item.is_current);
  const errors = checks.data?.errors ?? 0;
  const busy = runs.some(isActive);
  const names = new Map<string, string>([
    ...(classes.data ?? []).map((row) => [row.id, row.name] as [string, string]),
    ...(choices.data?.teachers ?? []).map((row) => [row.id, row.name] as [string, string]),
  ]);
  const draftName = (id: string | null) => drafts.data?.find((item) => item.id === id)?.name;
  const ruleOf = (id: string) => {
    const found = rules.data?.find((rule) => rule.id === id);
    return found ? describe(found, lookup, t, i18n.language) : undefined;
  };
  const scopeText = (run: Run) =>
    run.scope === "all"
      ? t("timetable.calculation.scopes.all")
      : (names.get(run.target ?? "") ?? t(`timetable.calculation.scopes.${run.scope}`));
  const timeText = (value: number) =>
    value % 60 === 0
      ? t("timetable.calculation.minutes", { count: value / 60 })
      : t("timetable.calculation.seconds", { count: value });
  const meta = (run: Run) => {
    const when = formatDateTime(run.created_at, i18n.language, school.timezone);
    return run.duration_ms == null
      ? t("timetable.calculation.when", { scope: scopeText(run), when })
      : t("timetable.calculation.whenTook", {
          scope: scopeText(run),
          when,
          duration: clock(run.duration_ms / 1000),
        });
  };
  const targets =
    scope === "class"
      ? (classes.data ?? []).map((row) => ({ id: row.id, name: row.name }))
      : (choices.data?.teachers ?? []);
  const canStart = errors === 0 && !busy && Boolean(draft) && (scope === "all" || Boolean(target));

  const runBody = (run: Run) => {
    if (run.status === "queued" || run.status === "running") {
      const elapsed = run.started_at ? (now - Date.parse(run.started_at)) / 1000 : 0;
      const share = Math.min(100, Math.max(0, (elapsed / run.time_limit) * 100));
      return (
        <>
          <span>
            <b>{scopeText(run)}</b>{" "}
            <span className="text-ink-3">
              · {t("timetable.calculation.from", { name: draftName(run.timetable) ?? "—" })}
            </span>
          </span>
          {run.status === "queued" ? (
            <p className="text-sm text-ink-2">{t("timetable.calculation.queuedHelp")}</p>
          ) : (
            <>
              <div
                className="h-2 overflow-hidden rounded-full bg-line-soft"
                role="progressbar"
                aria-label={t("timetable.calculation.heading.running")}
                aria-valuemin={0}
                aria-valuemax={run.time_limit}
                aria-valuenow={Math.min(run.time_limit, Math.round(elapsed))}
              >
                <div className="h-full rounded-full bg-lake" style={{ width: `${share}%` }} />
              </div>
              <div className="flex flex-wrap justify-between gap-2 text-sm text-ink-3">
                <span>
                  {t("timetable.calculation.elapsed", {
                    elapsed: clock(Math.min(elapsed, run.time_limit)),
                    limit: clock(run.time_limit),
                  })}
                </span>
                {run.started_at && (
                  <span>
                    {t("timetable.calculation.startedAt", {
                      time: formatTime(run.started_at, i18n.language, school.timezone),
                    })}
                  </span>
                )}
              </div>
            </>
          )}
          <p className="text-sm text-ink-3">{t("timetable.calculation.leave")}</p>
          <div>
            <Button variant="outline" onClick={() => setConfirming(true)}>
              {t("timetable.calculation.cancel")}
            </Button>
          </div>
        </>
      );
    }
    if (run.status === "done") {
      const total = run.unmet.reduce((sum, row) => sum + row.count, 0);
      const name = draftName(run.result);
      return (
        <>
          <p className="text-sm">
            {meta(run)}.{" "}
            {name
              ? t("timetable.calculation.doneText", { name })
              : t("timetable.calculation.doneGone")}
          </p>
          <h3 className="text-md font-bold">
            {total === 0
              ? t("timetable.calculation.allMet")
              : t("timetable.calculation.unmetTitle", { count: total })}
          </h3>
          {total > 0 && (
            <ul className="flex flex-col">
              {run.unmet.map((row, index) => {
                const said = unmetReason(row, ruleOf, t);
                return (
                  <Line
                    key={`${row.code}-${row.rule ?? index}`}
                    {...said}
                    action={
                      <StatusPill tone="gray">
                        {t("timetable.calculation.times", { count: row.count })}
                      </StatusPill>
                    }
                  />
                );
              })}
            </ul>
          )}
          {name && run.result && (
            <div>
              <Button asChild>
                <Link to={`/timetable?draft=${run.result}`}>
                  {t("timetable.calculation.openResult")}
                </Link>
              </Button>
            </div>
          )}
        </>
      );
    }
    if (run.status === "infeasible") {
      return (
        <>
          <p className="text-sm">
            {meta(run)}.{" "}
            {run.blocking.length > 0
              ? t("timetable.calculation.infeasibleText")
              : t("timetable.calculation.infeasibleUnknown")}
          </p>
          <ul className="flex flex-col">
            {run.blocking.map((row, index) => {
              const reason = blockingReason(row, run.timetable, ruleOf, t);
              const fix = reason.fix;
              return (
                <Line
                  key={`${row.code}-${index}`}
                  subject={reason.subject}
                  text={reason.text}
                  action={
                    fix &&
                    (fix.to === null ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setScope("all");
                          setTarget("");
                        }}
                      >
                        {t("timetable.calculation.fix.all")}
                      </Button>
                    ) : (
                      <Button asChild variant="outline" size="sm">
                        <Link to={fix.to}>{t(`timetable.calculation.fix.${fix.label}`)}</Link>
                      </Button>
                    ))
                  }
                />
              );
            })}
          </ul>
          <p className="text-sm text-ink-3">{t("timetable.calculation.basics")}</p>
        </>
      );
    }
    const text = {
      timeout: "timetable.calculation.timeoutText",
      error: "timetable.calculation.errorText",
      cancelled: "timetable.calculation.cancelledText",
    } as const;
    return (
      <p className="text-sm">
        {meta(run)}. {t(text[run.status])}
      </p>
    );
  };

  return (
    <>
      <PageHeader
        title={t("timetable.calculation.title")}
        subtitle={t("timetable.calculation.subtitle", { year: year?.name ?? "—" })}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/timetable-checks">{t("shell.menu.timetableChecks")}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to={draft ? `/timetable?draft=${draft}` : "/timetable"}>
                {t("shell.menu.timetable")}
              </Link>
            </Button>
          </>
        }
      />
      <div className="grid items-start gap-6 min-[1100px]:grid-cols-[minmax(0,1fr)_400px]">
        {shown ? (
          <Card className="min-w-0">
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle>{t(`timetable.calculation.heading.${shown.status}`)}</CardTitle>
              <StatusPill tone={STATUS_TONE[shown.status]}>
                {t(`timetable.calculation.status.${shown.status}`)}
              </StatusPill>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">{runBody(shown)}</CardContent>
          </Card>
        ) : (
          <Card className="min-w-0">
            <CardContent className="pt-6 text-ink-2">
              {t("timetable.calculation.empty")}
            </CardContent>
          </Card>
        )}
        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("timetable.calculation.formTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {errors > 0 ? (
                <div className="flex flex-col items-start gap-2">
                  <span className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
                    <StatusPill tone="due">
                      {t("timetable.calculation.blocked", { count: errors })}
                    </StatusPill>
                    {t("timetable.calculation.blockedHelp")}
                  </span>
                  <Button asChild variant="outline" size="sm">
                    <Link to="/timetable-checks">{t("shell.menu.timetableChecks")}</Link>
                  </Button>
                </div>
              ) : (
                <span className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
                  <StatusPill tone="ok">{t("timetable.calculation.ready")}</StatusPill>
                  {t("timetable.calculation.readyHelp")}
                </span>
              )}
              {drafts.data?.length === 0 ? (
                <Banner tone="info">{t("timetable.calculation.noDraft")}</Banner>
              ) : (
                <Field
                  id="run-draft"
                  label={t("timetable.calculation.draft")}
                  help={t("timetable.calculation.draftHelp")}
                >
                  {(control) => (
                    <Select
                      {...control}
                      value={draft ?? ""}
                      onChange={(event) => setDraftChoice(event.target.value)}
                    >
                      {(drafts.data ?? []).map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-bold text-ink-2">
                  {t("timetable.calculation.scope")}
                </span>
                <Segmented
                  label={t("timetable.calculation.scope")}
                  value={scope}
                  onValueChange={(next) => {
                    setScope(next);
                    setTarget("");
                  }}
                  options={SCOPES.map((value) => ({
                    value,
                    label:
                      value === "all"
                        ? t("timetable.calculation.scopeAll")
                        : t(`timetable.calculation.scopes.${value}`),
                  }))}
                  className="flex-wrap"
                />
              </div>
              {scope !== "all" && (
                <Field
                  id="run-target"
                  label={t(
                    scope === "class"
                      ? "timetable.calculation.classLabel"
                      : "timetable.calculation.teacherLabel",
                  )}
                  help={t("timetable.calculation.scopeHelp")}
                >
                  {(control) => (
                    <Select
                      {...control}
                      value={target}
                      onChange={(event) => setTarget(event.target.value)}
                    >
                      <option value="">{t("timetable.calculation.choose")}</option>
                      {targets.map((row) => (
                        <option key={row.id} value={row.id}>
                          {row.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-bold text-ink-2">
                  {t("timetable.calculation.time")}
                </span>
                <Segmented
                  label={t("timetable.calculation.time")}
                  value={String(time)}
                  onValueChange={(next) => setSeconds(Number(next))}
                  options={timeChoices(max).map((value) => ({
                    value: String(value),
                    label: timeText(value),
                  }))}
                  className="w-fit max-w-full flex-wrap"
                />
                <p className="text-sm text-ink-3">
                  {t("timetable.calculation.timeHelp", { max: timeText(max) })}
                </p>
              </div>
              {busy && <p className="text-sm text-ink-2">{t("timetable.calculation.busy")}</p>}
              {start.isError && <Banner tone="due">{errorMessage(start.error, t)}</Banner>}
              <Button
                className="w-full"
                disabled={!canStart || start.isPending}
                onClick={() => start.mutate()}
              >
                {t("timetable.calculation.submit")}
              </Button>
            </CardContent>
          </Card>
          {runs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t("timetable.calculation.historyTitle")}</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col">
                  {runs.map((run) => (
                    <li key={run.id} className="border-b border-line-soft last:border-b-0">
                      <button
                        type="button"
                        aria-current={run.id === shown?.id ? "true" : undefined}
                        onClick={() =>
                          setParams(
                            (current) => {
                              current.set("run", run.id);
                              return current;
                            },
                            { replace: true },
                          )
                        }
                        className={cn(
                          "flex w-full items-center justify-between gap-3 rounded-md px-2 py-3 text-left hover:bg-line-soft",
                          run.id === shown?.id && "bg-info-50",
                        )}
                      >
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <b className="truncate">{scopeText(run)}</b>
                          <span className="text-sm text-ink-3">
                            {formatDateTime(run.created_at, i18n.language, school.timezone)}
                            {run.duration_ms != null && ` · ${clock(run.duration_ms / 1000)}`}
                          </span>
                        </span>
                        <StatusPill tone={STATUS_TONE[run.status]}>
                          {t(`timetable.calculation.status.${run.status}`)}
                        </StatusPill>
                      </button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("timetable.calculation.cancelTitle")}
        confirmLabel={t("timetable.calculation.cancel")}
        cancelLabel={t("timetable.calculation.keep")}
        pending={cancel.isPending}
        destructive
        onConfirm={() => shown && cancel.mutate(shown.id)}
      >
        {t("timetable.calculation.cancelBody")}
      </ConfirmDialog>
    </>
  );
}
