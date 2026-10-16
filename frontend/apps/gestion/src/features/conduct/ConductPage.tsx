// Conduite (8.5.1a, maquette `conduite-incidents`) : attribuer une infraction à un élève et voir
// ses incidents, avec les points et la cote proposée de chaque période. Annuler un incident
// (motif) est réservé au directeur de discipline ; l'incident reste visible.
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
import { useState } from "react";

import { firstErrorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  useClassStudents,
  useConductClasses,
  useRules,
  useStudentIncidents,
  type Incident,
} from "./data";

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
  const [saved, setSaved] = useState(false);
  const [cancelling, setCancelling] = useState<Incident | null>(null);
  const [reason, setReason] = useState("");

  const groupId = classId || classes.data?.[0]?.id || "";
  const students = useClassStudents(groupId);
  const history = useStudentIncidents(enrollment);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: keys.conduct });

  const record = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/discipline/incidents/", {
          body: { enrollment, rule: rule || (rules.data?.[0]?.id ?? ""), occurred_on: date, note },
        }),
      ),
    onSuccess: () => {
      setSaved(true);
      setNote("");
      refresh();
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

  if (classes.isPending || rules.isPending) return <Skeleton label={t("common.loading")} />;
  if (classes.isError) {
    return <LoadError error={classes.error} onRetry={() => void classes.refetch()} />;
  }
  if (rules.isError) return <LoadError error={rules.error} onRetry={() => void rules.refetch()} />;

  const mayCancel = can(me, ["discipline.configure"]);
  const format = new Intl.DateTimeFormat(i18n.language, { day: "2-digit", month: "2-digit" });
  const student = students.data?.find((item) => item.enrollment === enrollment);

  return (
    <>
      <PageHeader title={t("conduct.title")} subtitle={t("conduct.subtitle")} />
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
                      setSaved(false);
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
              {saved && <Banner tone="ok">{t("conduct.recorded")}</Banner>}
              {record.isError && <Banner tone="due">{firstErrorMessage(record.error, t)}</Banner>}
              <Button
                disabled={!enrollment || !date || rules.data.length === 0 || record.isPending}
                onClick={() => {
                  setSaved(false);
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
              ) : history.isError ? (
                <LoadError error={history.error} onRetry={() => void history.refetch()} />
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    {history.data.totals.map((total) => (
                      <StatusPill key={total.term} tone="warn">
                        {t("conduct.proposed", {
                          term: total.term_name,
                          count: total.points,
                          grade: total.grade,
                        })}
                      </StatusPill>
                    ))}
                  </div>
                  {history.data.incidents.length === 0 ? (
                    <p className="text-ink-3">{t("conduct.none")}</p>
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
                        {history.data.incidents.map((incident) => (
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
    </>
  );
}
