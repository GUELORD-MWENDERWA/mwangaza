// Fiches de cotes (8.3.6, maquette `notes-fiches`) : la fiche d'un cours (avec moyenne, plus haute
// et plus basse note, nombre sous la moitié), la fiche vierge à remplir à la main et le tableau de
// toute la classe. Le serveur fait le document ; papier et sens : options d'impression (8.3.4).
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

import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { termLabels, type TermShape } from "../../lib/terms";
import { PrintLayoutFields } from "../printing/PrintLayoutFields";
import { DEFAULT_LAYOUT, usePrintOptions } from "../printing/printOptions";
import { LoadError } from "../status/StatusPages";
import { DocumentPreview } from "../students/DocumentPreview";
import { gradeSheetUrl, type SheetKind, useGrading } from "./data";

const BLANK_COLUMNS = [4, 6, 8, 10, 12, 16, 20];

/** Colonnes du tableau de la classe : l'année, puis chaque semestre, période et examen. */
function columnChoices(terms: TermShape[], labels: Map<TermShape, string>, year: string) {
  const choices = [{ id: "year", label: year }];
  const visit = (node: TermShape & { id?: string }) => {
    if (node.id) choices.push({ id: node.id, label: labels.get(node) ?? node.name });
    node.children?.forEach(visit);
  };
  terms.forEach(visit);
  return choices;
}

export function GradeSheetsPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const grading = useGrading();
  const [kind, setKind] = useState<SheetKind>("course");
  const [classId, setClassId] = useState("");
  const [courseId, setCourseId] = useState("");
  const [column, setColumn] = useState("year");
  const [saved, save] = usePrintOptions("grade-sheets", {
    ...DEFAULT_LAYOUT,
    matricule: true,
    totals: true,
    blankColumns: 8,
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const classes = grading.data.classes;
  const group = classes.find((item) => item.id === classId) ?? classes[0];
  const course = group?.courses.find((item) => item.id === courseId) ?? group?.courses[0];
  // Le tableau de la classe : direction des études, ou titulaire de la classe.
  const tableAllowed =
    can(me, ["grades.enter_any", "grades.validate"]) || Boolean(group?.is_homeroom);
  const current: SheetKind = kind === "class" && !tableAllowed ? "course" : kind;
  const labels = termLabels(grading.data.terms, t);
  const columns = [...(saved.matricule ? ["matricule"] : []), ...(saved.totals ? ["totals"] : [])];
  const options = {
    kind: current,
    layout: saved,
    course: course?.id,
    column,
    columns,
    blankColumns: saved.blankColumns,
  };
  const ready = group && (current === "class" || course);

  return (
    <>
      <PageHeader title={t("gradeSheets.title")} subtitle={t("gradeSheets.subtitle")} />
      {!group ? (
        <Banner tone="info">{t("gradeSheets.noClass")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex flex-col gap-4 min-[1000px]:order-2">
            <Card>
              <CardHeader>
                <CardTitle>{t("gradeSheets.document")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Segmented
                  label={t("gradeSheets.document")}
                  value={current}
                  onValueChange={setKind}
                  options={[
                    { value: "course" as const, label: t("gradeSheets.kind.course") },
                    { value: "blank" as const, label: t("gradeSheets.kind.blank") },
                    ...(tableAllowed
                      ? [{ value: "class" as const, label: t("gradeSheets.kind.class") }]
                      : []),
                  ]}
                />
                <Field id="sheet-class" label={t("gradeSheets.class")}>
                  {(control) => (
                    <Select
                      {...control}
                      value={group.id}
                      onChange={(event) => {
                        setClassId(event.target.value);
                        setCourseId("");
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
                {current === "class" ? (
                  <Field id="sheet-column" label={t("gradeSheets.column")}>
                    {(control) => (
                      <Select
                        {...control}
                        value={column}
                        onChange={(event) => setColumn(event.target.value)}
                      >
                        {columnChoices(grading.data.terms, labels, t("gradeSheets.year")).map(
                          (item) => (
                            <option key={item.id} value={item.id}>
                              {item.label}
                            </option>
                          ),
                        )}
                      </Select>
                    )}
                  </Field>
                ) : (
                  <Field id="sheet-course" label={t("gradeSheets.course")}>
                    {(control) => (
                      <Select
                        {...control}
                        value={course?.id ?? ""}
                        onChange={(event) => setCourseId(event.target.value)}
                      >
                        {group.courses.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                )}
                {current === "blank" && (
                  <Field
                    id="sheet-blank"
                    label={t("gradeSheets.blankColumns")}
                    help={t("gradeSheets.blankHelp")}
                  >
                    {(control) => (
                      <Select
                        {...control}
                        value={saved.blankColumns}
                        onChange={(event) => save({ blankColumns: Number(event.target.value) })}
                      >
                        {BLANK_COLUMNS.map((count) => (
                          <option key={count} value={count}>
                            {count}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                )}
                <fieldset className="flex flex-col gap-2.5">
                  <legend className="mb-1.5 text-sm font-bold text-ink-2">
                    {t("gradeSheets.columns")}
                  </legend>
                  <CheckboxField
                    id="sheet-matricule"
                    label={t("gradeSheets.matricule")}
                    checked={saved.matricule}
                    onCheckedChange={(checked) => save({ matricule: checked === true })}
                  />
                  {current === "course" && (
                    <CheckboxField
                      id="sheet-totals"
                      label={t("gradeSheets.totals")}
                      checked={saved.totals}
                      onCheckedChange={(checked) => save({ totals: checked === true })}
                    />
                  )}
                </fieldset>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>{t("gradeSheets.print")}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <PrintLayoutFields layout={saved} onChange={save} />
                {current === "class" && (
                  <p className="text-sm text-ink-3">{t("gradeSheets.classHelp")}</p>
                )}
                {ready && (
                  <>
                    <Button asChild>
                      <a
                        href={gradeSheetUrl(group.id, { ...options, output: "pdf" })}
                        target="_blank"
                        rel="noopener"
                      >
                        <Icon name="print" size={16} />
                        {t("gradeSheets.printButton")}
                      </a>
                    </Button>
                    <Button asChild variant="outline">
                      <a href={gradeSheetUrl(group.id, { ...options, output: "pdf" })} download>
                        <Icon name="download" size={16} />
                        {t("gradeSheets.pdf")}
                      </a>
                    </Button>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
          <div className="min-[1000px]:order-1">
            {ready ? (
              <DocumentPreview
                title={t("gradeSheets.preview")}
                src={gradeSheetUrl(group.id, { ...options, output: "html" })}
              />
            ) : (
              <Banner tone="info">{t("gradeSheets.noCourse")}</Banner>
            )}
          </div>
        </div>
      )}
    </>
  );
}
