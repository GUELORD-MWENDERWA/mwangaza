// Onglets du suivi : absents à suivre (corriger, noter un mot de parent), justifications reçues
// (accepter ou refuser, certificat), journal des corrections.
import { formatDay, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Textarea,
} from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { useCurrentSchool } from "../../lib/school";
import { useClasses, useYears } from "../organisation/data";
import { Pagination } from "../shell/Pagination";
import type { Target } from "./CorrectDialog";
import {
  type Absence,
  type AbsenceState,
  type Justification,
  useAbsences,
  useCorrections,
  useDecide,
  useJustifications,
  useRecordJustification,
} from "./follow";

const PAGE_SIZE = 50;
const STATE_TONES = { absent: "due", pending: "warn", justified: "ok" } as const;
const JUSTIFICATION_TONES = { pending: "warn", accepted: "ok", refused: "due" } as const;

function range(page: number, shown: number, count: number) {
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return { from, to: from + shown - (shown ? 1 : 0), count };
}

export function AbsentsTab({
  date,
  alertAfter,
  mayCorrect,
  onCorrect,
}: {
  date: string;
  alertAfter: number;
  mayCorrect: boolean;
  onCorrect: (target: Target) => void;
}) {
  const { t } = useTranslation();
  const [classGroup, setClassGroup] = useState("");
  const [state, setState] = useState<"" | AbsenceState>("");
  const [page, setPage] = useState(1);
  const [noting, setNoting] = useState<Absence | null>(null);
  const years = useYears();
  const year = years.data?.find((candidate) => candidate.is_current)?.id ?? "";
  const classes = useClasses(year);
  const list = useAbsences(date, { classGroup, state }, page);
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const filter = (patch: () => void) => {
    patch();
    setPage(1);
  };
  return (
    <Card className="mt-4">
      <CardHeader className="flex-wrap gap-3">
        <CardTitle>{t("follow.tabs.absents")}</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          {alertAfter > 0 && (
            <span className="text-sm text-ink-3">{t("follow.alert", { count: alertAfter })}</span>
          )}
          <Select
            aria-label={t("follow.filter.class")}
            value={classGroup}
            onChange={(event) => filter(() => setClassGroup(event.target.value))}
          >
            <option value="">{t("follow.filter.allClasses")}</option>
            {(classes.data ?? []).map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("follow.filter.state")}
            value={state}
            onChange={(event) => filter(() => setState(event.target.value as "" | AbsenceState))}
          >
            <option value="">{t("follow.filter.anyState")}</option>
            <option value="absent">{t("follow.absence.absent")}</option>
            <option value="pending">{t("follow.absence.pending")}</option>
            <option value="justified">{t("follow.absence.justified")}</option>
          </Select>
        </div>
      </CardHeader>
      {list.isError && <Banner tone="due">{errorMessage(list.error, t)}</Banner>}
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : rows.length === 0 ? (
        <p className="px-[18px] py-6 text-ink-3">{t("follow.noAbsents")}</p>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("follow.columns.student")}</th>
              <th>{t("follow.columns.absences")}</th>
              <th>{t("follow.columns.state")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.student_id}>
                <td data-label={t("follow.columns.student")}>
                  <b>{row.name}</b>
                  <br />
                  <span className="text-sm text-ink-3">
                    {row.class_name} · {row.matricule}
                  </span>
                </td>
                <td data-label={t("follow.columns.absences")}>
                  <span
                    className={
                      alertAfter > 0 && row.unjustified >= alertAfter ? "font-bold text-due" : ""
                    }
                  >
                    {t("follow.unjustified", { count: row.unjustified })}
                  </span>
                  {!row.parent_on_portal && (
                    <span className="block text-sm text-ink-3">{t("follow.callFamily")}</span>
                  )}
                </td>
                <td data-label={t("follow.columns.state")}>
                  <StatusPill tone={STATE_TONES[row.state]}>
                    {t(`follow.absence.${row.state}`)}
                  </StatusPill>
                </td>
                <td className="whitespace-nowrap">
                  {mayCorrect && (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          onCorrect({
                            kind: "student",
                            id: row.student_id,
                            name: row.name,
                            status: "absent",
                          })
                        }
                      >
                        {t("follow.correct")}
                      </Button>
                      {row.state === "absent" && (
                        <Button variant="outline" size="sm" onClick={() => setNoting(row)}>
                          {t("follow.justify")}
                        </Button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Pagination
        summary={t("follow.range", range(page, rows.length, count))}
        page={page}
        hasPrevious={Boolean(list.data?.previous)}
        hasNext={Boolean(list.data?.next)}
        onPage={setPage}
      />
      <NoteDialog date={date} absence={noting} onClose={() => setNoting(null)} />
    </Card>
  );
}

/** Un parent est venu avec un mot : l'école le note, la justification est acceptée d'emblée. */
function NoteDialog({
  date,
  absence,
  onClose,
}: {
  date: string;
  absence: Absence | null;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const record = useRecordJustification();
  const [reason, setReason] = useState("");
  const [endsOn, setEndsOn] = useState(date);
  const [document, setDocument] = useState<File | null>(null);
  const [shown, setShown] = useState<Absence | null>(null);
  if (absence !== shown) {
    setShown(absence);
    setReason("");
    setEndsOn(date);
    setDocument(null);
    record.reset();
  }
  return (
    <ConfirmDialog
      open={absence !== null}
      onOpenChange={(open) => !open && onClose()}
      title={t("follow.note.title", { name: absence?.name ?? "" })}
      confirmLabel={t("follow.note.confirm")}
      cancelLabel={t("common.cancel")}
      pending={record.isPending}
      confirmDisabled={reason.trim() === "" || endsOn < date}
      onConfirm={() =>
        absence &&
        record.mutate(
          { student: absence.student_id, startsOn: date, endsOn, reason: reason.trim(), document },
          { onSuccess: onClose },
        )
      }
    >
      <p className="text-sm text-ink-2">
        {t("follow.note.text", { date: formatDay(date, i18n.language) })}
      </p>
      <Field id="note-ends" label={t("follow.note.endsOn")}>
        {(control) => (
          <Input
            {...control}
            type="date"
            min={date}
            value={endsOn}
            onChange={(event) => setEndsOn(event.target.value)}
          />
        )}
      </Field>
      <Field id="note-reason" label={t("follow.note.reason")}>
        {(control) => (
          <Input
            {...control}
            maxLength={300}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        )}
      </Field>
      <Field id="note-document" label={t("follow.note.document")}>
        {(control) => (
          <Input
            {...control}
            type="file"
            accept="image/*,application/pdf"
            onChange={(event) => setDocument(event.target.files?.[0] ?? null)}
          />
        )}
      </Field>
      {record.isError && <Banner tone="due">{errorMessage(record.error, t)}</Banner>}
    </ConfirmDialog>
  );
}

export function JustificationsTab({ mayCorrect }: { mayCorrect: boolean }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [status, setStatus] = useState<"" | Justification["status"]>("pending");
  const [page, setPage] = useState(1);
  const [deciding, setDeciding] = useState<{ item: Justification; accept: boolean } | null>(null);
  const [note, setNote] = useState("");
  const list = useJustifications(status, page);
  const decide = useDecide();
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  return (
    <Card className="mt-4">
      <CardHeader className="flex-wrap gap-3">
        <CardTitle>{t("follow.tabs.justifications")}</CardTitle>
        <Select
          aria-label={t("follow.filter.status")}
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as "" | Justification["status"]);
            setPage(1);
          }}
        >
          <option value="pending">{t("follow.justification.pending")}</option>
          <option value="accepted">{t("follow.justification.accepted")}</option>
          <option value="refused">{t("follow.justification.refused")}</option>
          <option value="">{t("follow.filter.anyStatus")}</option>
        </Select>
      </CardHeader>
      {list.isError && <Banner tone="due">{errorMessage(list.error, t)}</Banner>}
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : rows.length === 0 ? (
        <p className="px-[18px] py-6 text-ink-3">{t("follow.noJustifications")}</p>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("follow.columns.student")}</th>
              <th>{t("follow.columns.period")}</th>
              <th>{t("follow.columns.reason")}</th>
              <th>{t("follow.columns.state")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td data-label={t("follow.columns.student")}>
                  <b>{item.student_name}</b>
                  <br />
                  <span className="text-sm text-ink-3">
                    {t(`follow.source.${item.source}`)} ·{" "}
                    {formatDateTime(item.created_at, i18n.language, school.timezone)}
                  </span>
                </td>
                <td data-label={t("follow.columns.period")}>
                  {item.starts_on === item.ends_on
                    ? formatDay(item.starts_on, i18n.language)
                    : `${formatDay(item.starts_on, i18n.language)} → ${formatDay(item.ends_on, i18n.language)}`}
                </td>
                <td data-label={t("follow.columns.reason")}>
                  {item.reason}
                  {item.has_document && (
                    <a
                      className="block text-sm font-bold underline"
                      href={`/api/attendance/justifications/${item.id}/document/`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t("follow.certificate")}
                    </a>
                  )}
                  {item.decision_note && (
                    <span className="block text-sm text-ink-3">{item.decision_note}</span>
                  )}
                </td>
                <td data-label={t("follow.columns.state")}>
                  <StatusPill tone={JUSTIFICATION_TONES[item.status]}>
                    {t(`follow.justification.${item.status}`)}
                  </StatusPill>
                </td>
                <td className="whitespace-nowrap">
                  {mayCorrect && item.status === "pending" && (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        onClick={() => {
                          setNote("");
                          setDeciding({ item, accept: true });
                        }}
                      >
                        {t("follow.accept")}
                      </Button>
                      <Button
                        variant="destructive-outline"
                        size="sm"
                        onClick={() => {
                          setNote("");
                          setDeciding({ item, accept: false });
                        }}
                      >
                        {t("follow.refuse")}
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Pagination
        summary={t("follow.range", range(page, rows.length, count))}
        page={page}
        hasPrevious={Boolean(list.data?.previous)}
        hasNext={Boolean(list.data?.next)}
        onPage={setPage}
      />
      <ConfirmDialog
        open={deciding !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeciding(null);
            decide.reset();
          }
        }}
        title={t(deciding?.accept ? "follow.decide.acceptTitle" : "follow.decide.refuseTitle", {
          name: deciding?.item.student_name ?? "",
        })}
        confirmLabel={t(deciding?.accept ? "follow.accept" : "follow.refuse")}
        cancelLabel={t("common.cancel")}
        destructive={deciding?.accept === false}
        pending={decide.isPending}
        onConfirm={() =>
          deciding &&
          decide.mutate(
            { id: deciding.item.id, accept: deciding.accept, note: note.trim() },
            { onSuccess: () => setDeciding(null) },
          )
        }
      >
        <Field id="decide-note" label={t("follow.decide.note")} help={t("follow.decide.noteHelp")}>
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              maxLength={300}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          )}
        </Field>
        {decide.isError && <Banner tone="due">{errorMessage(decide.error, t)}</Banner>}
      </ConfirmDialog>
    </Card>
  );
}

export function CorrectionsTab() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const [page, setPage] = useState(1);
  const list = useCorrections(page);
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  return (
    <Card className="mt-4">
      <CardHeader>
        <CardTitle>{t("follow.tabs.corrections")}</CardTitle>
      </CardHeader>
      {list.isError && <Banner tone="due">{errorMessage(list.error, t)}</Banner>}
      {list.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : rows.length === 0 ? (
        <p className="px-[18px] py-6 text-ink-3">{t("follow.noCorrections")}</p>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("follow.columns.person")}</th>
              <th>{t("follow.columns.day")}</th>
              <th>{t("follow.columns.change")}</th>
              <th>{t("follow.columns.reason")}</th>
              <th>{t("follow.columns.author")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td data-label={t("follow.columns.person")}>
                  <b>{row.name}</b>
                </td>
                <td data-label={t("follow.columns.day")}>{formatDay(row.date, i18n.language)}</td>
                <td data-label={t("follow.columns.change")}>
                  {t(`follow.status.${row.previous_status}`)} → {t(`follow.status.${row.status}`)}
                </td>
                <td data-label={t("follow.columns.reason")}>{row.reason}</td>
                <td data-label={t("follow.columns.author")} className="text-sm text-ink-3">
                  {row.author}
                  <br />
                  {formatDateTime(row.created_at, i18n.language, school.timezone)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Pagination
        summary={t("follow.range", range(page, rows.length, count))}
        page={page}
        hasPrevious={Boolean(list.data?.previous)}
        hasNext={Boolean(list.data?.next)}
        onPage={setPage}
      />
    </Card>
  );
}
