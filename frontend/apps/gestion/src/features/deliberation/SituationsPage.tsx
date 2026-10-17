// Situations de fin d'année (8.4.4, maquette `situations`) : la situation d'une classe (résultats,
// par cours, palmarès) et celle de toute l'école (lauréat, taux par classe, par niveau et global,
// écarts de délibération), au critère choisi à chaque édition. Le serveur fait le document ;
// papier et sens : options d'impression (8.3.4).
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

import { useGrading } from "../grades/data";
import { PrintLayoutFields } from "../printing/PrintLayoutFields";
import { DEFAULT_LAYOUT, usePrintOptions } from "../printing/printOptions";
import { LoadError } from "../status/StatusPages";
import { DocumentPreview } from "../students/DocumentPreview";
import { type Criterion, situationUrl, type SituationKind } from "./data";

export function SituationsPage() {
  const { t } = useTranslation();
  const grading = useGrading();
  const [kind, setKind] = useState<SituationKind>("class");
  const [criterion, setCriterion] = useState<Criterion>("rules");
  const [classId, setClassId] = useState("");
  const [saved, save] = usePrintOptions("situations", {
    ...DEFAULT_LAYOUT,
    courses: true,
    ranking: true,
    matricule: false,
    deviations: true,
  });

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const classes = grading.data.classes;
  const group = classes.find((item) => item.id === classId) ?? classes[0];
  const columns =
    kind === "class"
      ? [
          ...(saved.courses ? ["courses"] : []),
          ...(saved.ranking ? ["ranking"] : []),
          ...(saved.ranking && saved.matricule ? ["matricule"] : []),
        ]
      : saved.deviations
        ? ["deviations"]
        : [];
  const ready = kind === "school" || Boolean(group);
  const url = (output: "html" | "pdf") =>
    situationUrl({ kind, classId: group?.id, criterion, columns, output, layout: saved });

  return (
    <>
      <PageHeader title={t("situations.title")} subtitle={t("situations.subtitle")} />
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-4 min-[1000px]:order-2">
          <Card>
            <CardHeader>
              <CardTitle>{t("situations.document")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Segmented
                label={t("situations.document")}
                value={kind}
                onValueChange={setKind}
                options={[
                  { value: "class" as const, label: t("situations.kind.class") },
                  { value: "school" as const, label: t("situations.kind.school") },
                ]}
              />
              {kind === "class" && group && (
                <Field id="situation-class" label={t("situations.class")}>
                  {(control) => (
                    <Select
                      {...control}
                      value={group.id}
                      onChange={(event) => setClassId(event.target.value)}
                    >
                      {classes.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              <div className="flex flex-col gap-2">
                <Segmented
                  label={t("situations.criterion")}
                  value={criterion}
                  onValueChange={setCriterion}
                  options={[
                    { value: "rules" as const, label: t("situations.criteria.rules") },
                    { value: "average" as const, label: t("situations.criteria.average") },
                  ]}
                />
                <p className="text-sm text-ink-3">{t("situations.criterionHelp")}</p>
              </div>
              <fieldset className="flex flex-col gap-2.5">
                <legend className="mb-1.5 text-sm font-bold text-ink-2">
                  {t("situations.parts")}
                </legend>
                {kind === "class" ? (
                  <>
                    <CheckboxField
                      id="situation-courses"
                      label={t("situations.courses")}
                      checked={saved.courses}
                      onCheckedChange={(checked) => save({ courses: checked === true })}
                    />
                    <CheckboxField
                      id="situation-ranking"
                      label={t("situations.ranking")}
                      checked={saved.ranking}
                      onCheckedChange={(checked) => save({ ranking: checked === true })}
                    />
                    {saved.ranking && (
                      <CheckboxField
                        id="situation-matricule"
                        label={t("situations.matricule")}
                        checked={saved.matricule}
                        onCheckedChange={(checked) => save({ matricule: checked === true })}
                      />
                    )}
                  </>
                ) : (
                  <CheckboxField
                    id="situation-deviations"
                    label={t("situations.deviations")}
                    checked={saved.deviations}
                    onCheckedChange={(checked) => save({ deviations: checked === true })}
                  />
                )}
              </fieldset>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("situations.print")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <PrintLayoutFields layout={saved} onChange={save} />
              <p className="text-sm text-ink-3">{t("situations.printHelp")}</p>
              {ready && (
                <>
                  <Button asChild>
                    <a href={url("pdf")} target="_blank" rel="noopener">
                      <Icon name="print" size={16} />
                      {t("situations.printButton")}
                    </a>
                  </Button>
                  <Button asChild variant="outline">
                    <a href={url("pdf")} download>
                      <Icon name="download" size={16} />
                      {t("situations.pdf")}
                    </a>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="min-[1000px]:order-1">
          {ready ? (
            <DocumentPreview title={t("situations.preview")} src={url("html")} />
          ) : (
            <Banner tone="info">{t("situations.noClass")}</Banner>
          )}
        </div>
      </div>
    </>
  );
}
