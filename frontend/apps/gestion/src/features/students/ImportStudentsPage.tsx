// Importer des élèves depuis Excel ou CSV (D1, maquette `gestion/eleves-import`) : fichier,
// colonnes, vérification, import. L'import en cours est dans l'adresse (`/students/import/<id>`) :
// un rechargement retrouve l'étape. Le serveur vérifie chaque ligne ; les lignes en erreur ne sont
// pas importées, celles en avertissement le sont (à vérifier ensuite). Un import fini se retrouve
// sous l'étape « Fichier » et s'annule (`ImportCancellation`).
import { formatDate, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Steps,
  Table,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useClasses, useYears } from "../organisation/data";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  confirmImport,
  IMPORT_FIELDS,
  type ImportField,
  type ImportLine,
  importReportUrl,
  importTemplateUrl,
  type StudentImport,
  updateImport,
  uploadImport,
  useImportLines,
  useStudentImport,
} from "./data";
import { CancelImportDialog, CancelledImport, ImportHistory } from "./ImportCancellation";

type Step = "file" | "columns" | "check" | "import";
const STEPS: Step[] = ["file", "columns", "check", "import"];
const REQUIRED: ImportField[] = ["last_name", "sex", "class_name"];
const PAGE_SIZE = 50;

function useNumber() {
  const { i18n } = useTranslation();
  return (value: number) => new Intl.NumberFormat(i18n.language).format(value);
}

export function ImportStudentsPage() {
  const { t } = useTranslation();
  const { importId } = useParams();
  const imp = useStudentImport(importId);
  const current: Step = !importId
    ? "file"
    : !imp.data
      ? "check"
      : imp.data.status !== "analysed"
        ? "import"
        : imp.data.missing_fields.length
          ? "columns"
          : "check";
  const position = STEPS.indexOf(current);
  const finished = imp.data?.status === "done" || imp.data?.status === "cancelled";
  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            / {t("students.import.crumb")}
          </>
        }
        title={t("students.import.title")}
        actions={
          <Button asChild variant="outline">
            <a href={importTemplateUrl} download>
              <Icon name="download" size={16} />
              {t("students.import.template")}
            </a>
          </Button>
        }
      />
      <Card>
        <CardContent>
          <Steps
            steps={STEPS.map((step, index) => ({
              label: t(`students.import.steps.${step}`),
              state:
                index < position || finished ? "done" : index === position ? "current" : "todo",
            }))}
          />
        </CardContent>
      </Card>
      {!importId ? (
        <>
          <FileStep />
          <ImportHistory />
        </>
      ) : imp.error ? (
        <LoadError error={imp.error} onRetry={() => void imp.refetch()} />
      ) : !imp.data ? (
        <Skeleton label={t("common.loading")} />
      ) : imp.data.status === "analysed" ? (
        <CheckStep imp={imp.data} />
      ) : (
        <ImportStep imp={imp.data} />
      )}
    </>
  );
}

/** Étape 1 : l'année des classes du fichier, puis le fichier, vérifié aussitôt. */
function FileStep() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const years = useYears();
  const [year, setYear] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const yearId = year || years.data?.find((item) => item.is_current)?.id || "";
  const upload = useMutation({
    mutationFn: () => uploadImport(file!, yearId),
    onSuccess: (imp) => {
      queryClient.setQueryData([...keys.studentImports, imp.id], imp);
      void navigate(`/students/import/${imp.id}`);
    },
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("students.import.file.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 min-[700px]:grid-cols-2">
        <Field id="import-year" label={t("students.import.file.year")}>
          {(control) => (
            <Select {...control} value={yearId} onChange={(e) => setYear(e.target.value)}>
              {years.data?.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id="import-file"
          label={t("students.import.file.file")}
          help={t("students.import.file.help")}
        >
          {(control) => (
            <Input
              {...control}
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          )}
        </Field>
        {upload.error && (
          <Banner tone="due" className="min-[700px]:col-span-2">
            {errorMessage(upload.error, t)}
          </Banner>
        )}
      </CardContent>
      <CardFooter className="justify-end">
        <Button disabled={!file || !yearId || upload.isPending} onClick={() => upload.mutate()}>
          {upload.isPending ? t("students.import.file.reading") : t("students.import.file.check")}
        </Button>
      </CardFooter>
    </Card>
  );
}

/** Étapes 2 et 3 : totaux, colonnes et classes choisies à la main, aperçu, puis import. */
function CheckStep({ imp }: { imp: StudentImport }) {
  const { t } = useTranslation();
  const number = useNumber();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (body: Parameters<typeof updateImport>[1]) => updateImport(imp.id, body),
    onSuccess: (updated) => {
      queryClient.setQueryData([...keys.studentImports, imp.id], updated);
      void queryClient.invalidateQueries({ queryKey: [...keys.studentImports, imp.id, "lines"] });
    },
  });
  const start = useMutation({
    mutationFn: () => confirmImport(imp.id),
    onSuccess: (updated) => queryClient.setQueryData([...keys.studentImports, imp.id], updated),
  });
  const { counts } = imp;
  return (
    <>
      <div className="grid grid-cols-2 gap-4 min-[1000px]:grid-cols-4">
        <Kpi
          label={t("students.import.counts.rows")}
          value={number(counts.rows)}
          sub={
            imp.sheet_name
              ? t("students.import.counts.sheet", { file: imp.file_name, sheet: imp.sheet_name })
              : imp.file_name
          }
        />
        <Kpi label={t("students.import.counts.ready")} value={number(counts.ready)} tone="ok" />
        <Kpi
          label={t("students.import.counts.warning")}
          value={number(counts.warning)}
          tone="warn"
          sub={t("students.import.counts.warningHelp")}
        />
        <Kpi
          label={t("students.import.counts.error")}
          value={number(counts.error)}
          tone="due"
          sub={t("students.import.counts.errorHelp")}
        />
      </div>
      {save.error && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
      {imp.missing_fields.length > 0 && (
        <Banner tone="warn">
          {t("students.import.missingFields", {
            fields: imp.missing_fields
              .map((name) => t(`students.import.fields.${name}`))
              .join(", "),
          })}
        </Banner>
      )}
      <div className="grid grid-cols-1 items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <ColumnsCard imp={imp} busy={save.isPending} onChange={save.mutate} />
        <Card>
          <Preview imp={imp} />
          <CardFooter className="flex-wrap items-center justify-between gap-3">
            <span className="text-[.85rem] text-ink-3">
              {t("students.import.footer", {
                count: imp.importable_count,
                number: number(imp.importable_count),
              })}
            </span>
            <div className="flex flex-wrap gap-2.5">
              <Button asChild variant="outline">
                <Link to="/students/import">{t("students.import.otherFile")}</Link>
              </Button>
              {counts.warning + counts.error > 0 && (
                <Button asChild variant="outline">
                  <a href={importReportUrl(imp.id)} download>
                    {t("students.import.report")}
                  </a>
                </Button>
              )}
              <Button
                disabled={!imp.importable_count || save.isPending || start.isPending}
                onClick={() => start.mutate()}
              >
                {t("students.import.start", {
                  count: imp.importable_count,
                  number: number(imp.importable_count),
                })}
              </Button>
            </div>
          </CardFooter>
          {start.error && (
            <CardContent>
              <Banner tone="due">{errorMessage(start.error, t)}</Banner>
            </CardContent>
          )}
        </Card>
      </div>
    </>
  );
}

function ColumnsCard({
  imp,
  busy,
  onChange,
}: {
  imp: StudentImport;
  busy: boolean;
  onChange: (body: Parameters<typeof updateImport>[1]) => void;
}) {
  const { t } = useTranslation();
  const classes = useClasses(imp.academic_year);
  const toMatch = imp.classes.filter((item) => item.chosen || !item.class_group);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("students.import.columns.title")}</CardTitle>
      </CardHeader>
      <Table>
        <tbody>
          {IMPORT_FIELDS.map((name) => {
            const column = imp.mapping[name];
            const mapped = column !== null && column !== undefined;
            return (
              <tr key={name}>
                <td className="font-bold">{t(`students.import.fields.${name}`)}</td>
                <td>
                  <Select
                    aria-label={t(`students.import.fields.${name}`)}
                    value={mapped ? String(column) : ""}
                    disabled={busy}
                    onChange={(e) =>
                      onChange({
                        mapping: { [name]: e.target.value === "" ? null : Number(e.target.value) },
                      })
                    }
                  >
                    <option value="">{t("students.import.columns.ignore")}</option>
                    {imp.headers.map((title, index) => (
                      <option key={index} value={index}>
                        {title || t("students.import.columns.untitled", { number: index + 1 })}
                      </option>
                    ))}
                  </Select>
                </td>
                <td>
                  {mapped ? (
                    <StatusPill tone="ok" className="max-[560px]:hidden">
                      {t("students.import.columns.found")}
                    </StatusPill>
                  ) : REQUIRED.includes(name) ? (
                    <StatusPill tone="due">{t("students.import.columns.required")}</StatusPill>
                  ) : (
                    <StatusPill tone="gray">{t("students.import.columns.optional")}</StatusPill>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
      {toMatch.length > 0 && (
        <CardContent className="flex flex-col gap-3">
          <h3 className="font-bold">{t("students.import.classes.title")}</h3>
          {toMatch.map((item) => (
            <Field
              key={item.label}
              id={`import-class-${item.label}`}
              label={t("students.import.classes.label", { label: item.label, count: item.rows })}
            >
              {(control) => (
                <Select
                  {...control}
                  value={item.chosen ? (item.class_group ?? "") : ""}
                  disabled={busy}
                  onChange={(e) =>
                    onChange({
                      class_mapping: { ...imp.class_mapping, [item.label]: e.target.value },
                    })
                  }
                >
                  <option value="">{t("students.import.classes.choose")}</option>
                  {classes.data?.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          ))}
        </CardContent>
      )}
    </Card>
  );
}

function Preview({ imp }: { imp: StudentImport }) {
  const { t } = useTranslation();
  const problemCount = imp.counts.warning + imp.counts.error;
  const [filter, setFilter] = useState<"all" | "problems">(problemCount ? "problems" : "all");
  const [page, setPage] = useState(1);
  const lines = useImportLines(imp.id, filter === "problems", page);
  const results = lines.data?.results ?? [];
  const from = results.length ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle>{t("students.import.preview.title")}</CardTitle>
        <Segmented
          label={t("students.import.preview.filter")}
          value={filter}
          onValueChange={(value) => {
            setFilter(value);
            setPage(1);
          }}
          options={[
            { value: "all", label: t("students.import.preview.all") },
            {
              value: "problems",
              label: t("students.import.preview.problems", { count: problemCount }),
            },
          ]}
        />
      </CardHeader>
      {lines.error ? (
        <LoadError error={lines.error} onRetry={() => void lines.refetch()} />
      ) : !lines.data ? (
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                {(
                  ["line", "last_name", "middle_name", "first_name", "sex", "birth_date"] as const
                ).map((column) => (
                  <th key={column}>{t(`students.import.preview.columns.${column}`)}</th>
                ))}
                <th>{t("students.import.preview.columns.class")}</th>
                <th>{t("students.import.preview.columns.status")}</th>
              </tr>
            </thead>
            <tbody>
              {results.map((line) => (
                <Line key={line.line} line={line} />
              ))}
            </tbody>
          </Table>
          {results.length === 0 && (
            <CardContent className="text-ink-3">{t("students.import.preview.empty")}</CardContent>
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(lines.data.previous)}
            hasNext={Boolean(lines.data.next)}
            onPage={setPage}
            summary={t("students.list.range", {
              from,
              to: from ? from + results.length - 1 : 0,
              count: lines.data.count,
            })}
          />
        </>
      )}
    </>
  );
}

function Line({ line }: { line: ImportLine }) {
  const { t } = useTranslation();
  const { values } = line;
  const problems = line.issues.filter((issue) => issue.code !== "same_family");
  const family = line.issues.find((issue) => issue.code === "same_family");
  const issueTone = line.status === "error" ? "due" : "warn";
  return (
    <tr data-tone={line.status === "ready" ? undefined : issueTone}>
      <td className="text-ink-3">{line.line}</td>
      <td>{values.last_name}</td>
      <td>{values.middle_name}</td>
      <td>{values.first_name}</td>
      <td>{values.sex}</td>
      <td className="tabular-nums">{values.birth_date}</td>
      <td>{values.class_name}</td>
      <td>
        <div className="flex flex-col items-start gap-1">
          {problems.length === 0 ? (
            <StatusPill tone="ok">{t("students.import.preview.ready")}</StatusPill>
          ) : (
            problems.map((issue) => (
              <StatusPill key={issue.code} tone={issueTone}>
                {t(`students.import.issues.${issue.code as IssueCode}`, { line: issue.line })}
              </StatusPill>
            ))
          )}
          {family && (
            <span className="text-[.8rem] text-ink-3">
              {t("students.import.issues.same_family", { line: family.line })}
            </span>
          )}
        </div>
      </td>
    </tr>
  );
}

type IssueCode =
  | "missing_last_name"
  | "invalid_sex"
  | "invalid_date"
  | "missing_class"
  | "unknown_class"
  | "matricule_taken"
  | "matricule_repeated"
  | "already_in_school"
  | "duplicate_in_file"
  | "missing_birth_date"
  | "invalid_phone"
  | "guardian_without_name";

/** Étape 4 : import en tâche de fond, suivi jusqu'au bout. */
function ImportStep({ imp }: { imp: StudentImport }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const number = useNumber();
  const queryClient = useQueryClient();
  const [cancelling, setCancelling] = useState(false);
  const running = t("students.import.running", {
    count: imp.importable_count,
    number: number(imp.importable_count),
  });
  useEffect(() => {
    // Liste des élèves et effectifs des classes à relire.
    if (imp.status === "done") void queryClient.invalidateQueries({ queryKey: keys.students });
  }, [imp.status, queryClient]);
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        {imp.status === "importing" ? (
          <>
            <p className="font-bold">{running}</p>
            <Skeleton label={running} />
          </>
        ) : imp.status === "failed" ? (
          <Banner tone="due">{t("students.import.failed")}</Banner>
        ) : imp.status === "cancelled" ? (
          <CancelledImport imp={imp} />
        ) : (
          <>
            <Banner tone="ok">
              {t("students.import.done", {
                count: imp.created_count,
                number: number(imp.created_count),
              })}
            </Banner>
            {imp.counts.error > 0 && (
              <p>{t("students.import.notImported", { count: imp.counts.error })}</p>
            )}
          </>
        )}
      </CardContent>
      {imp.status !== "importing" && (
        <CardFooter className="flex-wrap justify-end gap-2.5">
          {imp.status === "done" &&
            imp.created_count > 0 &&
            imp.cancellable_until &&
            (new Date(imp.cancellable_until) > new Date() ? (
              <Button variant="outline" className="mr-auto" onClick={() => setCancelling(true)}>
                {t("students.import.cancel.action")}
              </Button>
            ) : (
              <span className="mr-auto text-sm text-ink-3">
                {t("students.import.cancel.tooLate", {
                  date: formatDate(imp.cancellable_until, i18n.language, school.timezone),
                })}
              </span>
            ))}
          {imp.status === "done" && imp.counts.error > 0 && (
            <Button asChild variant="outline">
              <a href={importReportUrl(imp.id)} download>
                {t("students.import.report")}
              </a>
            </Button>
          )}
          <Button asChild variant="outline">
            <Link to="/students/import">{t("students.import.otherFile")}</Link>
          </Button>
          {(imp.status === "done" || imp.status === "cancelled") && (
            <Button asChild>
              <Link to="/students">{t("students.import.seeStudents")}</Link>
            </Button>
          )}
        </CardFooter>
      )}
      {cancelling && <CancelImportDialog imp={imp} onClose={() => setCancelling(false)} />}
    </Card>
  );
}
