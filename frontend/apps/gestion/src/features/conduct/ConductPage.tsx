// Conduite (8.5.1a, maquette `conduite-incidents`) : attribuer une infraction à un élève et voir
// ses incidents, avec les points et la cote de chaque période. Annuler un incident (motif) est
// réservé au directeur de discipline ; l'incident reste visible. Corriger la cote d'une période
// (8.5.1b : motif, journal) demande `discipline.override`. Sans réseau (HL.2, maquette
// `conduite-hors-ligne`) : attribuer passe par la file de l'appareil (`offline.ts`), l'historique
// lu ici reste lisible ; annuler et corriger demandent le réseau.
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
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { useOnline } from "../../lib/online";
import { fullName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { isNetworkError } from "../../lib/sync/reads";
import { useSyncStatus } from "../../lib/sync/session";
import { LoadError } from "../status/StatusPages";
import {
  useClassStudents,
  useConductClasses,
  useRules,
  useStudentIncidents,
  type Incident,
  type TermConduct,
} from "./data";
import { dismissRejected, sendIncident, useIncidentsQueue, type IncidentBody } from "./offline";

const GRADES = ["TB", "B", "AB", "ME", "MA"] as const;
type Grade = (typeof GRADES)[number];

const today = () => new Date().toISOString().slice(0, 10);

export function ConductPage() {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const queryClient = useQueryClient();
  const classes = useConductClasses();
  const rules = useRules();
  const [classId, setClassId] = useState("");
  const [enrollment, setEnrollment] = useState("");
  const [rule, setRule] = useState("");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<"sent" | "queued" | null>(null);
  const [cancelling, setCancelling] = useState<Incident | null>(null);
  const [reason, setReason] = useState("");
  const [correcting, setCorrecting] = useState<TermConduct | null>(null);
  const [newGrade, setNewGrade] = useState<Grade>("TB");
  const [correctReason, setCorrectReason] = useState("");

  const groupId = classId || classes.data?.[0]?.id || "";
  const students = useClassStudents(groupId);
  const history = useStudentIncidents(enrollment);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.conduct });
  const { db } = useSyncStatus();
  const online = useOnline();
  const queue = useIncidentsQueue(db);
  const waiting = queue?.waiting ?? [];
  // Infractions de l'appareil parties : l'historique du serveur les montre maintenant.
  const hadWaiting = useRef(false);
  useEffect(() => {
    if (hadWaiting.current && waiting.length === 0) refresh();
    hadWaiting.current = waiting.length > 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting.length]);

  const record = useMutation({
    mutationFn: () =>
      sendIncident(db, {
        enrollment,
        rule: rule || (rules.data?.[0]?.id ?? ""),
        occurred_on: date,
        note,
      }),
    onSuccess: (result) => {
      setSaved(result);
      setNote("");
      if (result === "sent") refresh();
    },
  });
  const cancel = useMutation({
    mutationFn: (incident: Incident) =>
      call(
        api.POST("/api/discipline/incidents/{id}/cancel/", {
          params: { path: { id: incident.id } },
          body: { reason },
        }),
      ),
    onSuccess: () => {
      setCancelling(null);
      setReason("");
      refresh();
    },
  });

  const correct = useMutation({
    mutationFn: (total: TermConduct) =>
      call(
        api.PUT("/api/discipline/enrollments/{id}/grade/", {
          params: { path: { id: enrollment } },
          body: { term: total.term, grade: newGrade, reason: correctReason },
        }),
      ),
    onSuccess: () => {
      setCorrecting(null);
      setCorrectReason("");
      refresh();
    },
  });
  const restore = useMutation({
    mutationFn: (total: TermConduct) =>
      call(
        api.DELETE("/api/discipline/enrollments/{id}/grade/", {
          params: { path: { id: enrollment }, query: { term: total.term } },
        }),
      ),
    onSuccess: () => {
      setCorrecting(null);
      refresh();
    },
  });

  if (classes.isPending || rules.isPending) return <Skeleton label={t("common.loading")} />;
  if (classes.isError) {
    return <LoadError error={classes.error} onRetry={() => void classes.refetch()} />;
  }
  if (rules.isError) return <LoadError error={rules.error} onRetry={() => void rules.refetch()} />;

  const mayCancel = online && can(me, ["discipline.configure"]);
  const mayCorrect = online && can(me, ["discipline.override"]);
  const format = new Intl.DateTimeFormat(i18n.language, { day: "2-digit", month: "2-digit" });
  const student = students.data?.find((item) => item.enrollment === enrollment);
  // Infractions de cet élève encore sur l'appareil, en tête de son historique.
  const pending = waiting.flatMap((op) => {
    const body = op.payload as IncidentBody & { id: string };
    if (body.enrollment !== enrollment) return [];
    const offence = rules.data.find((item) => item.id === body.rule);
    return [{ ...body, offence: offence?.label ?? "", points: offence?.points ?? 0 }];
  });
  const historyUnread = history.isError && isNetworkError(history.error);
  const incidents = history.data?.incidents ?? [];

  return (
    <>
      <PageHeader title={t("conduct.title")} subtitle={t("conduct.subtitle")} />
      {waiting.length > 0 && (
        <div className="mb-4">
          <Banner tone="warn">{t("conduct.offline.waiting", { count: waiting.length })}</Banner>
        </div>
      )}
      {queue && queue.rejected.length > 0 && db && (
        <div className="mb-4">
          <Banner
            tone="due"
            action={
              <Button variant="outline" onClick={() => void dismissRejected(db, queue.rejected)}>
                {t("conduct.offline.dismiss")}
              </Button>
            }
          >
            {t("conduct.offline.rejected", {
              reason: queue.rejected.at(-1)?.error?.detail ?? "",
            })}
          </Banner>
        </div>
      )}
      {classes.data.length === 0 ? (
        <Banner tone="info">{t("conduct.noClass")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[360px_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>{t("conduct.record")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {rules.data.length === 0 && <Banner tone="warn">{t("conduct.noOffences")}</Banner>}
              <Field id="conduct-class" label={t("conduct.class")}>
                {(control) => (
                  <Select
                    {...control}
                    value={groupId}
                    onChange={(event) => {
                      setClassId(event.target.value);
                      setEnrollment("");
                    }}
                  >
                    {classes.data.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="conduct-student" label={t("conduct.student")}>
                {(control) => (
                  <Select
                    {...control}
                    value={enrollment}
                    onChange={(event) => {
                      setEnrollment(event.target.value);
                      setSaved(null);
                    }}
                  >
                    <option value="" />
                    {students.data?.map((item) => (
                      <option key={item.enrollment} value={item.enrollment}>
                        {item.full_name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="conduct-rule" label={t("conduct.offence")} help={t("conduct.pickHelp")}>
                {(control) => (
                  <Select
                    {...control}
                    value={rule || (rules.data[0]?.id ?? "")}
                    onChange={(event) => setRule(event.target.value)}
                  >
                    {rules.data.map((item) => (
                      <option key={item.id} value={item.id}>
                        {t("conduct.offenceOption", { label: item.label, count: item.points })}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field id="conduct-date" label={t("conduct.date")}>
                {(control) => (
                  <Input
                    {...control}
                    type="date"
                    max={today()}
                    value={date}
                    onChange={(event) => setDate(event.target.value)}
                  />
                )}
              </Field>
              <Field id="conduct-note" label={t("conduct.note")}>
                {(control) => (
                  <Input
                    {...control}
                    maxLength={300}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                )}
              </Field>
              {saved && (
                <Banner tone="ok">
                  {saved === "sent" ? t("conduct.recorded") : t("conduct.offline.queued")}
                </Banner>
              )}
              {record.isError && <Banner tone="due">{firstErrorMessage(record.error, t)}</Banner>}
              <Button
                disabled={!enrollment || !date || rules.data.length === 0 || record.isPending}
                onClick={() => {
                  setSaved(null);
                  record.mutate();
                }}
              >
                {t("conduct.submit")}
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{student?.full_name ?? t("conduct.history")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {!enrollment ? (
                <p className="text-ink-3">{t("conduct.pickStudent")}</p>
              ) : history.isPending ? (
                <Skeleton label={t("common.loading")} />
              ) : history.isError && !historyUnread ? (
                <LoadError error={history.error} onRetry={() => void history.refetch()} />
              ) : (
                <>
                  {historyUnread && <p className="text-ink-3">{t("conduct.offline.noHistory")}</p>}
                  <div className="flex flex-wrap gap-2">
                    {history.data?.totals.map((total) => (
                      <span key={total.term} className="flex items-center gap-1">
                        <StatusPill tone={total.override_reason ? "ok" : "warn"}>
                          {total.override_reason
                            ? t("conduct.corrected", {
                                term: total.term_name,
                                count: total.points,
                                calculated: total.calculated,
                                grade: total.grade,
                              })
                            : t("conduct.proposed", {
                                term: total.term_name,
                                count: total.points,
                                grade: total.grade,
                              })}
                        </StatusPill>
                        {mayCorrect && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setNewGrade(total.grade as Grade);
                              setCorrectReason(total.override_reason);
                              setCorrecting(total);
                            }}
                          >
                            {t("conduct.correct")}
                          </Button>
                        )}
                      </span>
                    ))}
                  </div>
                  {incidents.length === 0 && pending.length === 0 ? (
                    !historyUnread && <p className="text-ink-3">{t("conduct.none")}</p>
                  ) : (
                    <Table stacked>
                      <thead>
                        <tr>
                          <th>{t("conduct.columns.date")}</th>
                          <th>{t("conduct.columns.offence")}</th>
                          <th className="text-right">{t("conduct.columns.points")}</th>
                          <th>{t("conduct.columns.by")}</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {pending.map((item) => (
                          <tr key={item.id}>
                            <td data-label={t("conduct.columns.date")}>
                              {format.format(new Date(item.occurred_on))}
                            </td>
                            <td data-label={t("conduct.columns.offence")} data-wrap>
                              {item.offence}
                              <StatusPill tone="warn" className="ml-2">
                                {t("conduct.offline.pending")}
                              </StatusPill>
                              {item.note && (
                                <span className="block text-xs text-ink-3">{item.note}</span>
                              )}
                            </td>
                            <td data-label={t("conduct.columns.points")} className="text-right">
                              {item.points}
                            </td>
                            <td data-label={t("conduct.columns.by")}>{fullName(me)}</td>
                            <td />
                          </tr>
                        ))}
                        {incidents.map((incident) => (
                          <tr key={incident.id} className={incident.cancelled ? "opacity-60" : ""}>
                            <td data-label={t("conduct.columns.date")}>
                              {format.format(new Date(incident.occurred_on))}
                            </td>
                            <td data-label={t("conduct.columns.offence")} data-wrap>
                              <span className={incident.cancelled ? "line-through" : ""}>
                                {incident.offence}
                              </span>
                              {incident.cancelled && (
                                <StatusPill tone="due" className="ml-2">
                                  {t("conduct.cancelled", { reason: incident.cancel_reason })}
                                </StatusPill>
                              )}
                              {incident.note && (
                                <span className="block text-xs text-ink-3">{incident.note}</span>
                              )}
                            </td>
                            <td data-label={t("conduct.columns.points")} className="text-right">
                              {incident.points}
                            </td>
                            <td data-label={t("conduct.columns.by")}>
                              {incident.recorded_by_name}
                            </td>
                            <td>
                              {mayCancel && !incident.cancelled && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setCancelling(incident)}
                                >
                                  {t("conduct.cancel")}
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  )}
                  {!online && <p className="text-xs text-ink-3">{t("conduct.offline.readOnly")}</p>}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
      <ConfirmDialog
        open={cancelling !== null}
        onOpenChange={(open) => {
          if (!open) setCancelling(null);
        }}
        title={t("conduct.cancelTitle")}
        confirmLabel={t("conduct.confirmCancel")}
        cancelLabel={t("conduct.keep")}
        destructive
        pending={cancel.isPending || reason.trim() === ""}
        onConfirm={() => cancelling && cancel.mutate(cancelling)}
      >
        <div className="flex flex-col gap-3">
          <p className="text-ink-3">{t("conduct.cancelHelp")}</p>
          <Field id="conduct-reason" label={t("conduct.reason")} required>
            {(control) => (
              <Textarea
                {...control}
                maxLength={300}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
          {cancel.isError && <Banner tone="due">{firstErrorMessage(cancel.error, t)}</Banner>}
        </div>
      </ConfirmDialog>
      <ConfirmDialog
        open={correcting !== null}
        onOpenChange={(open) => {
          if (!open) setCorrecting(null);
        }}
        title={t("conduct.correctTitle")}
        confirmLabel={t("conduct.confirmCorrect")}
        cancelLabel={t("conduct.keep")}
        pending={correct.isPending || correctReason.trim() === ""}
        onConfirm={() => correcting && correct.mutate(correcting)}
      >
        <div className="flex flex-col gap-3">
          <p className="text-ink-3">{t("conduct.correctHelp")}</p>
          <Field id="conduct-new-grade" label={t("conduct.newGrade")}>
            {(control) => (
              <Select
                {...control}
                value={newGrade}
                onChange={(event) => setNewGrade(event.target.value as Grade)}
              >
                {GRADES.map((grade) => (
                  <option key={grade} value={grade}>
                    {t(`conduct.grade${grade}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="conduct-correct-reason" label={t("conduct.reason")} required>
            {(control) => (
              <Textarea
                {...control}
                maxLength={300}
                value={correctReason}
                onChange={(event) => setCorrectReason(event.target.value)}
              />
            )}
          </Field>
          {correcting?.override_reason && (
            <Button
              variant="outline"
              disabled={restore.isPending}
              onClick={() => restore.mutate(correcting)}
            >
              {t("conduct.restore")}
            </Button>
          )}
          {(correct.isError || restore.isError) && (
            <Banner tone="due">{firstErrorMessage(correct.error ?? restore.error, t)}</Banner>
          )}
        </div>
      </ConfirmDialog>
    </>
  );
}
