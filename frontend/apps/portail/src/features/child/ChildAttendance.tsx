// Présences de l'enfant (lot 10, 6.6 · maquette `enfant-presences`) : jours présents, retards,
// absences ; le parent justifie une absence (motif, certificat en option) et voit la réponse de l'école.
import { errorMessage, formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Kpi,
  StatusPill,
} from "@mwangaza/ui";
import { useState } from "react";

import { useChildAttendance, useJustify } from "../../lib/families";

const ABSENCE_TONES = { absent: "due", pending: "warn", justified: "ok" } as const;
const JUSTIFICATION_TONES = { pending: "warn", accepted: "ok", refused: "due" } as const;

export function ChildAttendance({ id }: { id: string }) {
  const { t, i18n } = useTranslation();
  const query = useChildAttendance(id);
  const justify = useJustify(id);
  const [day, setDay] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [document, setDocument] = useState<File | null>(null);
  const data = query.data;
  if (!data) return null;
  const { totals } = data;
  const open = (date: string) => {
    setDay(date);
    setReason("");
    setDocument(null);
    justify.reset();
  };
  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-2.5">
        <Kpi
          label={t("portal.child.attendance.present")}
          tone="ok"
          value={totals.present}
          sub={t("portal.child.attendance.days")}
        />
        <Kpi label={t("portal.child.attendance.late")} value={totals.late} />
        <Kpi
          label={t("portal.child.attendance.absent")}
          tone={totals.absent > totals.justified ? "due" : undefined}
          value={totals.absent}
          sub={t("portal.child.attendance.justified", { count: totals.justified })}
        />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t("portal.child.attendance.absences")}</CardTitle>
        </CardHeader>
        <CardContent className="py-1">
          {data.absences.length === 0 && (
            <p className="py-3 text-ink-3">{t("portal.child.attendance.none")}</p>
          )}
          <ul className="divide-y divide-line">
            {data.absences.map((absence) => (
              <li key={absence.date} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <b className="block">{formatDay(absence.date, i18n.language)}</b>
                  <StatusPill tone={ABSENCE_TONES[absence.state]}>
                    {t(`portal.child.attendance.states.${absence.state}`)}
                  </StatusPill>
                </div>
                {absence.state === "absent" && (
                  <Button size="sm" onClick={() => open(absence.date)}>
                    {t("portal.child.attendance.justify")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {day && (
        <Card>
          <CardHeader>
            <CardTitle>
              {t("portal.child.attendance.justifyTitle", { date: formatDay(day, i18n.language) })}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-col gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                justify.mutate(
                  { day, reason: reason.trim(), document },
                  { onSuccess: () => setDay(null) },
                );
              }}
            >
              <Field id="justify-reason" label={t("portal.child.attendance.reason")} required>
                {(control) => (
                  <Input
                    {...control}
                    maxLength={300}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                )}
              </Field>
              <Field id="justify-document" label={t("portal.child.attendance.document")}>
                {(control) => (
                  <Input
                    {...control}
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(event) => setDocument(event.target.files?.[0] ?? null)}
                  />
                )}
              </Field>
              {justify.isError && <Banner tone="due">{errorMessage(justify.error, t)}</Banner>}
              <Button type="submit" size="lg" disabled={reason.trim() === "" || justify.isPending}>
                {t("portal.child.attendance.send")}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}
      {data.justifications.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{t("portal.child.attendance.sent")}</CardTitle>
          </CardHeader>
          <CardContent className="py-1">
            <ul className="divide-y divide-line">
              {data.justifications.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <b className="block">
                      {item.starts_on === item.ends_on
                        ? formatDay(item.starts_on, i18n.language)
                        : `${formatDay(item.starts_on, i18n.language)} → ${formatDay(item.ends_on, i18n.language)}`}
                    </b>
                    <span className="text-sm text-ink-3">{item.reason}</span>
                    {item.decision_note && (
                      <span className="block text-sm text-ink-2">{item.decision_note}</span>
                    )}
                  </div>
                  <StatusPill tone={JUSTIFICATION_TONES[item.status]}>
                    {t(`portal.child.attendance.answers.${item.status}`)}
                  </StatusPill>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
