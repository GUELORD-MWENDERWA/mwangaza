import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Icon,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useClasses, useYears } from "../organisation/data";
import { type ClassListColumn, type ClassListOrder, classListUrl } from "./data";
import { DocumentPreview } from "./DocumentPreview";

const COLUMNS = ["matricule", "sex_birth", "guardian_phone", "payments"] as const;
const BLANK_COLUMNS = [0, 1, 2, 3, 4, 5];

/** Liste d'une classe de l'année en cours (D5, M11) : élèves actifs, en PDF ou Excel, avec les
 * mêmes colonnes. */
export function ClassListPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const years = useYears();
  const year = years.data?.find((candidate) => candidate.is_current);
  const classes = useClasses(year?.id ?? "");
  const [chosen, setChosen] = useState(params.get("class") ?? "");
  // Situation des paiements (2.7) : seulement avec `finance.view_reports`, vérifié par le serveur.
  const offered = can(useCurrentMe(), ["finance.view_reports"])
    ? COLUMNS
    : COLUMNS.filter((column) => column !== "payments");
  const [columns, setColumns] = useState<ClassListColumn[]>(["matricule", "sex_birth"]);
  const [blankColumns, setBlankColumns] = useState(2);
  const [order, setOrder] = useState<ClassListOrder>("name");

  const groups = classes.data ?? [];
  const group = groups.find((candidate) => candidate.id === chosen) ?? groups[0];
  const options = { columns, blankColumns, order };
  const toggle = (column: ClassListColumn, on: boolean) =>
    setColumns((current) =>
      COLUMNS.filter((name) => (name === column ? on : current.includes(name))),
    );

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            / {t("students.print.classList.title")}
          </>
        }
        title={t("students.print.classList.title")}
        subtitle={t("students.print.classList.subtitle")}
        actions={
          group && (
            <>
              <Select
                aria-label={t("students.print.classList.class")}
                value={group.id}
                onChange={(event) => setChosen(event.target.value)}
              >
                {groups.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.name}
                  </option>
                ))}
              </Select>
              <Button asChild variant="outline">
                <a href={classListUrl(group.id, { output: "xlsx", ...options })} download>
                  <Icon name="excel" size={16} />
                  {t("students.print.excel")}
                </a>
              </Button>
              <Button asChild>
                <a
                  href={classListUrl(group.id, { output: "pdf", ...options })}
                  target="_blank"
                  rel="noopener"
                >
                  <Icon name="print" size={16} />
                  {t("students.print.classList.pdf")}
                </a>
              </Button>
            </>
          )
        }
      />
      {!years.data || (year && !classes.data) ? (
        <Skeleton label={t("common.loading")} />
      ) : !group ? (
        <Banner tone="warn">{t("students.print.classList.noClasses")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="min-[1000px]:order-2">
            <CardHeader>
              <CardTitle>{t("students.print.classList.options")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <fieldset className="flex flex-col gap-2.5">
                <legend className="mb-1.5 text-sm font-bold text-ink-2">
                  {t("students.print.classList.columns")}
                </legend>
                {offered.map((column) => (
                  <CheckboxField
                    key={column}
                    id={`column-${column}`}
                    label={t(`students.print.classList.column.${column}`)}
                    checked={columns.includes(column)}
                    onCheckedChange={(checked) => toggle(column, checked === true)}
                  />
                ))}
              </fieldset>
              <Field
                id="blank-columns"
                label={t("students.print.classList.blankColumns")}
                help={t("students.print.classList.blankHelp")}
              >
                {(control) => (
                  <Select
                    {...control}
                    value={blankColumns}
                    onChange={(event) => setBlankColumns(Number(event.target.value))}
                  >
                    {BLANK_COLUMNS.map((count) => (
                      <option key={count} value={count}>
                        {count}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-bold text-ink-2">
                  {t("students.print.classList.order")}
                </span>
                <Segmented
                  label={t("students.print.classList.order")}
                  value={order}
                  onValueChange={setOrder}
                  options={[
                    { value: "name", label: t("students.print.classList.byName") },
                    { value: "matricule", label: t("students.print.classList.byMatricule") },
                  ]}
                />
              </div>
            </CardContent>
          </Card>
          <div className="min-[1000px]:order-1">
            <DocumentPreview
              title={t("students.print.classList.preview")}
              src={classListUrl(group.id, { output: "html", ...options })}
            />
          </div>
        </div>
      )}
    </>
  );
}
