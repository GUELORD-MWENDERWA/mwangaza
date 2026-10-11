// Annuler un import (D6, maquette `gestion/eleves-import-annulation`) : les imports finis se
// retrouvent dans « Imports précédents » ; un import fini s'annule avec un motif. Le serveur efface
// les élèves que rien ne touche ; ceux qu'un paiement, une réduction, un échéancier particulier ou
// un compte parent touche restent, et l'écran les nomme.
import { formatDate, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { firstErrorMessage } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  cancelImport,
  type ImportCancellation,
  type StudentImport,
  useImportCancellation,
  useImportHistory,
} from "./data";

const PAGE_SIZE = 50;

function useNumber() {
  const { i18n } = useTranslation();
  return (value: number) => new Intl.NumberFormat(i18n.language).format(value);
}

/** Imports finis ou annulés de l'école ; rien tant qu'il n'y en a aucun. */
export function ImportHistory() {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const number = useNumber();
  const [page, setPage] = useState(1);
  const history = useImportHistory(page);
  if (!history.data?.count) return null;
  const results = history.data.results;
  const from = (page - 1) * PAGE_SIZE + 1;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("students.import.history.title")}</CardTitle>
      </CardHeader>
      <Table>
        <thead>
          <tr>
            {(["file", "year", "date", "by", "students", "status"] as const).map((column) => (
              <th key={column}>{t(`students.import.history.columns.${column}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((imp) => (
            <tr key={imp.id}>
              <td>
                <Link to={`/students/import/${imp.id}`} className="font-bold text-lake underline">
                  {imp.file_name}
                </Link>
              </td>
              <td>{imp.academic_year_name}</td>
              <td>
                {imp.finished_at && formatDate(imp.finished_at, i18n.language, school.timezone)}
              </td>
              <td>{imp.created_by_name}</td>
              <td>
                {number(imp.created_count)}
                {imp.status === "cancelled" && (
                  <span className="text-ink-3">
                    {" · "}
                    {t("students.import.history.removed", {
                      count: imp.cancelled_count,
                      number: number(imp.cancelled_count),
                    })}
                  </span>
                )}
              </td>
              <td>
                <StatusPill tone={imp.status === "cancelled" ? "gray" : "ok"}>
                  {t(
                    `students.import.history.status.${imp.status === "cancelled" ? "cancelled" : "done"}`,
                  )}
                </StatusPill>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      {history.data.count > PAGE_SIZE && (
        <Pagination
          page={page}
          hasPrevious={Boolean(history.data.previous)}
          hasNext={Boolean(history.data.next)}
          onPage={setPage}
          summary={t("students.list.range", {
            from,
            to: from + results.length - 1,
            count: history.data.count,
          })}
        />
      )}
    </Card>
  );
}

/** Élèves que l'annulation garde, avec ce qui les touche. */
function KeptStudents({ data }: { data: ImportCancellation }) {
  const { t } = useTranslation();
  const number = useNumber();
  const more = data.kept_count - data.kept.length;
  if (!data.kept_count) return null;
  return (
    <Banner tone="warn">
      <p className="font-bold">
        {t("students.import.cancel.kept", {
          count: data.kept_count,
          number: number(data.kept_count),
        })}
      </p>
      <ul className="mt-1.5 flex flex-col gap-1">
        {data.kept.map((student) => (
          <li key={student.id}>
            <Link to={`/students/${student.id}`} className="text-lake underline">
              {studentName(student)}
            </Link>{" "}
            <span className="text-ink-2">
              —{" "}
              {student.reasons
                .map((reason) => t(`students.import.cancel.reasons.${reason}`))
                .join(", ")}
            </span>
          </li>
        ))}
        {more > 0 && (
          <li className="text-ink-2">
            {t("students.import.cancel.more", { count: more, number: number(more) })}
          </li>
        )}
      </ul>
    </Banner>
  );
}

/** Import annulé : qui, quand, pourquoi, et les élèves restés dans l'école. */
export function CancelledImport({ imp }: { imp: StudentImport }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const number = useNumber();
  const cancellation = useImportCancellation(imp.id);
  return (
    <>
      <Banner tone="warn">
        <p className="font-bold">
          {t("students.import.cancel.done", {
            count: imp.cancelled_count,
            number: number(imp.cancelled_count),
            date: imp.cancelled_at
              ? formatDate(imp.cancelled_at, i18n.language, school.timezone)
              : "",
            name: imp.cancelled_by_name ?? "",
          })}
        </p>
        <p>{t("students.import.cancel.doneReason", { reason: imp.cancel_reason })}</p>
      </Banner>
      {cancellation.data && <KeptStudents data={cancellation.data} />}
    </>
  );
}

export function CancelImportDialog({ imp, onClose }: { imp: StudentImport; onClose: () => void }) {
  const { t } = useTranslation();
  const number = useNumber();
  const queryClient = useQueryClient();
  const preview = useImportCancellation(imp.id);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const cancel = useMutation({
    mutationFn: () => cancelImport(imp.id, reason.trim()),
    onSuccess: async (cancelled) => {
      queryClient.setQueryData([...keys.studentImports, imp.id], cancelled);
      // Aperçu, imports précédents, liste des élèves et effectifs des classes à relire.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.studentImports }),
        queryClient.invalidateQueries({ queryKey: keys.students }),
      ]);
      onClose();
    },
    onError: (failure) => setError(firstErrorMessage(failure, t)),
  });
  const removable = preview.data?.removable_count ?? 0;
  const submit = () => {
    if (!reason.trim()) setError(t("fieldErrors.required"));
    else cancel.mutate();
  };

  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("students.import.cancel.title")}
        description={imp.file_name}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("students.import.cancel.keep")}</Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={submit}
              disabled={!removable || cancel.isPending}
            >
              {t("students.import.cancel.confirm")}
            </Button>
          </>
        }
      >
        {preview.error ? (
          <LoadError error={preview.error} onRetry={() => void preview.refetch()} />
        ) : !preview.data ? (
          <Skeleton label={t("common.loading")} />
        ) : (
          <>
            {removable ? (
              <p className="font-bold">
                {t("students.import.cancel.removes", {
                  count: removable,
                  number: number(removable),
                })}
              </p>
            ) : (
              <Banner tone="due">{t("students.import.cancel.nothing")}</Banner>
            )}
            {removable > 0 && <KeptStudents data={preview.data} />}
            {removable > 0 && (
              <>
                <p className="text-sm text-ink-2">{t("students.import.cancel.offline")}</p>
                <Field
                  id="cancel-import-reason"
                  label={t("students.import.cancel.reason")}
                  help={t("students.import.cancel.reasonHelp")}
                  required
                  error={error ?? undefined}
                >
                  {(control) => (
                    <Input
                      {...control}
                      maxLength={255}
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                    />
                  )}
                </Field>
              </>
            )}
          </>
        )}
      </DialogContent>
    </DialogRoot>
  );
}
