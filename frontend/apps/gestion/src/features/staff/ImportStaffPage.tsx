// Import du personnel depuis Excel (R.1, maquette `gestion/personnel-import`) : fichier, aperçu
// ligne par ligne, puis comptes créés d'un bloc et lettres d'accès à imprimer. Le serveur ne
// garde pas le fichier : il est renvoyé pour l'enregistrement et vérifié de nouveau. Droit
// `roles.manage`, comme les comptes du personnel.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
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
  List,
  PageHeader,
  Segmented,
  StatusPill,
  Steps,
  Table,
  Tag,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { formatPhone } from "../../lib/people";
import { keys, useRoles } from "../../lib/queries";

type Result = Schemas["StaffImport"];
type Line = Schemas["StaffImportLine"];
type Step = "file" | "check" | "done";
const STEPS: Step[] = ["file", "check", "done"];
/** Lettres par PDF : chacune hache un mot de passe sur le serveur (`staff_import.MAX_LETTERS`). */
const LETTERS_PER_PDF = 50;
const templateUrl = "/api/staff/import/template/";

function sendFile(file: File, expected?: number) {
  const body = new FormData();
  body.append("file", file);
  if (expected !== undefined) body.append("expected", String(expected));
  return call(api.POST("/api/staff/import/", { body: body as unknown as { file: string } }));
}

/** Liens des lettres d'accès, par paquets de 50 (adresse courte, PDF rapide). */
export function letterLinks(ids: string[]) {
  const links = [];
  for (let start = 0; start < ids.length; start += LETTERS_PER_PDF) {
    const part = ids.slice(start, start + LETTERS_PER_PDF);
    links.push({
      from: start + 1,
      to: start + part.length,
      url: `/api/staff/access-letters/?ids=${part.join(",")}`,
    });
  }
  return links;
}

export function ImportStaffPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const roles = useRoles();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [filter, setFilter] = useState<"problems" | "all">("problems");
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const check = useMutation({
    mutationFn: () => sendFile(file!),
    onSuccess: (data) => {
      setResult(data);
      setFilter(data.ready_count === data.lines.length ? "all" : "problems");
    },
  });
  const record = useMutation({
    mutationFn: () => sendFile(file!, result!.ready_count),
    onSuccess: async (data) => {
      setResult(data);
      await queryClient.invalidateQueries({ queryKey: keys.staff });
    },
  });
  const restart = () => {
    setFile(null);
    setResult(null);
    check.reset();
    record.reset();
  };
  const current: Step = !result ? "file" : result.recorded ? "done" : "check";
  const position = STEPS.indexOf(current);
  const error = record.error ?? check.error;
  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/staff" className="text-lake underline">
              {t("staff.title")}
            </Link>{" "}
            / {t("staff.importButton")}
          </>
        }
        title={t("staff.import.title")}
        subtitle={t("staff.import.subtitle")}
        actions={
          <Button asChild variant="outline">
            <a href={templateUrl} download>
              <Icon name="download" size={16} />
              {t("staff.import.template")}
            </a>
          </Button>
        }
      />
      <Card>
        <CardContent>
          <Steps
            steps={STEPS.map((step, index) => ({
              label: t(`staff.import.steps.${step}`),
              state:
                index < position || current === "done"
                  ? "done"
                  : index === position
                    ? "current"
                    : "todo",
            }))}
          />
        </CardContent>
      </Card>
      {error && <Banner tone="due">{errorMessage(error, t)}</Banner>}
      {result?.recorded ? (
        <Done result={result} onAgain={restart} />
      ) : (
        <div className="grid grid-cols-1 gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)]">
          {/* Au téléphone, l'aide passe après le fichier et l'aperçu. */}
          <div className="order-2 grid content-start gap-4 min-[1000px]:order-1">
            <Card>
              <CardHeader>
                <CardTitle>{t("staff.import.columnsCard.title")}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <List>
                  {(
                    [
                      ["lastName", true],
                      ["names", false],
                      ["phone", true],
                      ["roles", true],
                    ] as const
                  ).map(([column, required]) => (
                    <div key={column}>
                      <span>{t(`staff.import.columnsCard.${column}`)}</span>
                      {required ? (
                        <b>{t("staff.import.columnsCard.required")}</b>
                      ) : (
                        <span className="text-ink-3">{t("staff.import.columnsCard.optional")}</span>
                      )}
                    </div>
                  ))}
                </List>
                <p className="text-ink-3">{t("staff.import.columnsCard.help")}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("staff.import.rolesCard.title")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5">
                {(roles.data ?? []).map((role) => (
                  <Tag key={role.id}>{role.name}</Tag>
                ))}
              </CardContent>
              <CardFooter>
                <Link to="/roles" className="text-sm text-lake underline">
                  {t("staff.import.rolesCard.create")}
                </Link>
              </CardFooter>
            </Card>
          </div>
          {!result ? (
            <Card className="order-1 content-start min-[1000px]:order-2">
              <CardHeader>
                <CardTitle>{t("staff.import.file.title")}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4">
                <Banner tone="info">{t("staff.import.file.rules")}</Banner>
                <Field
                  id="staff-import-file"
                  label={t("staff.import.file.file")}
                  help={t("staff.import.file.help")}
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
              </CardContent>
              <CardFooter className="justify-end">
                <Button disabled={!file || check.isPending} onClick={() => check.mutate()}>
                  {check.isPending ? t("staff.import.file.reading") : t("staff.import.file.check")}
                </Button>
              </CardFooter>
            </Card>
          ) : (
            <div className="order-1 grid content-start gap-4 min-[1000px]:order-2">
              <div className="grid grid-cols-1 gap-4 min-[600px]:grid-cols-3">
                <Kpi
                  label={t("staff.import.counts.ready")}
                  value={number(result.ready_count)}
                  tone="ok"
                  sub={t("staff.import.counts.read", {
                    count: result.lines.length,
                    number: number(result.lines.length),
                    file: file?.name ?? "",
                  })}
                />
                <Kpi
                  label={t("staff.import.counts.skipped")}
                  value={number(result.skipped_count)}
                  sub={t("staff.import.counts.skippedHelp")}
                />
                <Kpi
                  label={t("staff.import.counts.error")}
                  value={number(result.error_count)}
                  tone={result.error_count ? "due" : undefined}
                  sub={t("staff.import.counts.errorHelp")}
                />
              </div>
              <Preview
                result={result}
                filter={filter}
                onFilter={setFilter}
                footer={
                  <CardFooter className="flex-wrap items-center justify-between gap-3">
                    <span className="text-sm text-ink-3">
                      {t("staff.import.preview.footer", {
                        count: result.ready_count,
                        number: number(result.ready_count),
                      })}
                    </span>
                    <div className="flex flex-wrap gap-2.5">
                      <Button variant="outline" onClick={restart}>
                        {t("staff.import.preview.otherFile")}
                      </Button>
                      <Button
                        disabled={result.ready_count === 0 || record.isPending}
                        onClick={() => record.mutate()}
                      >
                        {record.isPending
                          ? t("staff.import.preview.recording")
                          : t("staff.import.preview.record", {
                              count: result.ready_count,
                              number: number(result.ready_count),
                            })}
                      </Button>
                    </div>
                  </CardFooter>
                }
              />
            </div>
          )}
        </div>
      )}
    </>
  );
}

function Preview({
  result,
  filter,
  onFilter,
  footer,
}: {
  result: Result;
  filter: "problems" | "all";
  onFilter: (value: "problems" | "all") => void;
  footer: React.ReactNode;
}) {
  const { t } = useTranslation();
  const problems = result.lines.filter((line) => line.status !== "ready");
  const lines = filter === "all" ? result.lines : problems;
  return (
    <Card>
      <CardHeader className="flex-wrap gap-3">
        <CardTitle>{t("staff.import.preview.title")}</CardTitle>
        <Segmented
          label={t("staff.import.preview.title")}
          value={filter}
          onValueChange={onFilter}
          options={[
            { value: "all", label: t("staff.import.preview.all") },
            {
              value: "problems",
              label: t("staff.import.preview.problems", { number: problems.length }),
            },
          ]}
        />
      </CardHeader>
      {lines.length === 0 ? (
        <CardContent className="text-ink-3">{t("staff.import.preview.none")}</CardContent>
      ) : (
        <Table stacked>
          <thead>
            <tr>
              <th>{t("staff.import.columns.line")}</th>
              <th>{t("staff.import.columns.name")}</th>
              <th>{t("staff.import.columns.phone")}</th>
              <th>{t("staff.import.columns.roles")}</th>
              <th>{t("staff.import.columns.state")}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.line} className={line.status === "error" ? "bg-due-50/60" : undefined}>
                <td data-label={t("staff.import.columns.line")} className="text-ink-3">
                  {line.line}
                </td>
                <td data-label={t("staff.import.columns.name")} data-wrap>
                  <b>{line.name || "—"}</b>
                </td>
                <td data-label={t("staff.import.columns.phone")} className="whitespace-nowrap">
                  {line.phone_text || "—"}
                </td>
                <td data-label={t("staff.import.columns.roles")} data-wrap>
                  {line.roles_text || "—"}
                </td>
                <td data-label={t("staff.import.columns.state")} data-wrap>
                  <LineState line={line} />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {footer}
    </Card>
  );
}

function LineState({ line }: { line: Line }) {
  const { t } = useTranslation();
  if (line.status === "ready") return <StatusPill tone="ok">{t("staff.import.ready")}</StatusPill>;
  return (
    <span className="flex flex-wrap gap-1.5">
      {line.issues.map((issue) => (
        <StatusPill
          key={issue.code + (issue.role ?? "")}
          tone={line.status === "error" ? "due" : "gray"}
          className="whitespace-normal"
        >
          {t(`staff.import.issues.${issue.code}`, { line: issue.line, role: issue.role })}
        </StatusPill>
      ))}
    </span>
  );
}

function Done({ result, onAgain }: { result: Result; onAgain: () => void }) {
  const { t, i18n } = useTranslation();
  const number = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const letters = result.added.filter((person) => person.letter);
  const existing = result.added.filter((person) => person.existing_account).length;
  const count = (
    key:
      | "staff.import.done.added"
      | "staff.import.done.letters"
      | "staff.import.done.existing"
      | "staff.import.letters.count",
    value: number,
  ) => t(key, { count: value, number: number(value) });
  return (
    <>
      <Banner tone="ok">
        <b>{count("staff.import.done.added", result.added.length)}</b>{" "}
        {letters.length > 0 && count("staff.import.done.letters", letters.length)}{" "}
        {existing > 0 && count("staff.import.done.existing", existing)}
      </Banner>
      <Card>
        <CardHeader>
          <CardTitle>{t("staff.import.letters.title")}</CardTitle>
        </CardHeader>
        {letters.length > 0 && (
          <CardContent className="grid gap-3">
            <p className="text-sm text-ink-3">{t("staff.import.letters.help")}</p>
            <div className="flex flex-wrap gap-2.5">
              {letterLinks(letters.map((person) => person.id)).map((link, index) => (
                <Button key={link.from} asChild variant={index === 0 ? "default" : "outline"}>
                  <a href={link.url} target="_blank" rel="noopener">
                    <Icon name="print" size={16} />
                    {link.from === link.to
                      ? t("staff.import.letters.printOne", { from: link.from })
                      : t("staff.import.letters.print", { from: link.from, to: link.to })}
                  </a>
                </Button>
              ))}
            </div>
          </CardContent>
        )}
        <Table stacked>
          <thead>
            <tr>
              <th>{t("staff.import.columns.name")}</th>
              <th>{t("staff.import.columns.phone")}</th>
              <th>{t("staff.import.columns.roles")}</th>
              <th>{t("staff.import.letters.access")}</th>
            </tr>
          </thead>
          <tbody>
            {result.added.map((person: Schemas["StaffImportAdded"]) => (
              <tr key={person.id}>
                <td data-label={t("staff.import.columns.name")} data-wrap>
                  <b>{person.name}</b>
                </td>
                <td data-label={t("staff.import.columns.phone")} className="whitespace-nowrap">
                  {formatPhone(person.phone)}
                </td>
                <td data-label={t("staff.import.columns.roles")} data-wrap>
                  <span className="flex flex-wrap gap-1.5">
                    {person.roles.map((role) => (
                      <Tag key={role}>{role}</Tag>
                    ))}
                  </span>
                </td>
                <td data-label={t("staff.import.letters.access")} data-wrap>
                  {person.letter ? (
                    <StatusPill tone="info">{t("staff.import.letters.letter")}</StatusPill>
                  ) : person.existing_account ? (
                    <StatusPill tone="gray" className="whitespace-normal">
                      {t("staff.import.letters.existing")}
                    </StatusPill>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <CardFooter className="flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-ink-3">
            {count("staff.import.letters.count", letters.length)}
          </span>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="outline" onClick={onAgain}>
              {t("staff.import.again")}
            </Button>
            <Button asChild variant="outline">
              <Link to="/staff">{t("staff.import.back")}</Link>
            </Button>
          </div>
        </CardFooter>
      </Card>
    </>
  );
}
