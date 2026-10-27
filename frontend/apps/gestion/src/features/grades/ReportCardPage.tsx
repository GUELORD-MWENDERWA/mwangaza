// Bulletin d'un élève (8.3.2, maquettes `bulletin` et `bulletin-education-de-base`) : le document
// que le serveur met en PDF, avec les places de la classe et un QR code d'authenticité. Droit
// `grades.enter_any` ou `grades.validate` ; 8.3.5 : notes seules sur le formulaire pré-imprimé et toute la classe en un PDF.
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CheckboxField,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
} from "@mwangaza/ui";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { DocumentPreview } from "../students/DocumentPreview";
import { usePrintOptions } from "../printing/printOptions";
import { DEFAULT_CARD_PRINT, reportCardUrl, useGrading, useReportStatus } from "./data";

export function ReportCardPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const grading = useGrading();
  // `?class=…` : une classe complète, depuis le suivi des notes (NB.2).
  const [params] = useSearchParams();
  const [classId, setClassId] = useState(params.get("class") ?? "");
  const [search, setSearch] = useState("");
  const [enrollmentId, setEnrollmentId] = useState("");
  const [print, setPrint] = usePrintOptions("report-card", DEFAULT_CARD_PRINT);
  // Le titulaire et le cotitulaire (NB.8) : les bulletins de leur classe seulement.
  const everyClass = can(me, ["grades.enter_any", "grades.validate"]);
  const classes = (grading.data?.classes ?? []).filter((item) => everyClass || item.is_homeroom);
  const groupId = classes.find((item) => item.id === classId)?.id ?? classes[0]?.id ?? "";
  const status = useReportStatus(groupId);

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  // Élèves de la classe, donnés avec l'état du bulletin (sans le droit de lire tous les élèves).
  const wanted = search.trim().toLocaleLowerCase();
  const rows = (status.data?.students ?? []).filter(
    (row) => !wanted || row.name.toLocaleLowerCase().includes(wanted),
  );
  const chosen = rows.find((row) => row.enrollment === enrollmentId) ?? rows[0];
  const enrollment = chosen?.enrollment ?? "";
  const missing = status.data?.missing_count ?? 0;
  const pdf = enrollment ? reportCardUrl(groupId, enrollment, "pdf", print) : "";

  return (
    <>
      <PageHeader title={t("reportCard.title")} subtitle={t("reportCard.subtitle")} />
      {classes.length === 0 ? (
        <Banner tone="info">{t("reportCard.noClass")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="min-[1000px]:order-2">
            <CardHeader>
              <CardTitle>{t("reportCard.choose")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Select
                aria-label={t("reportCard.classChoice")}
                value={groupId}
                onChange={(event) => {
                  setClassId(event.target.value);
                  setEnrollmentId("");
                }}
              >
                {classes.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </Select>
              <Input
                type="search"
                aria-label={t("reportCard.search")}
                placeholder={t("reportCard.search")}
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setEnrollmentId("");
                }}
              />
              <Select
                aria-label={t("reportCard.studentChoice")}
                value={enrollment}
                onChange={(event) => setEnrollmentId(event.target.value)}
              >
                {rows.map((row) => (
                  <option key={row.enrollment} value={row.enrollment}>
                    {row.name}
                  </option>
                ))}
              </Select>
              <p className="text-sm text-ink-3">{t("reportCard.help")}</p>
              {missing > 0 && (
                <Banner tone="warn">
                  {t("reportCard.missing", { count: missing })}
                  <ul className="mt-1 list-disc pl-5">
                    {(status.data?.missing ?? []).slice(0, 6).map((item) => (
                      <li key={`${item.course}-${item.term}`}>
                        {item.course} · {item.term}
                      </li>
                    ))}
                  </ul>
                </Banner>
              )}
              <CheckboxField
                id="grades-only"
                label={t("reportCard.gradesOnly")}
                checked={print.gradesOnly}
                onCheckedChange={(checked) => setPrint({ gradesOnly: checked === true })}
              />
              <p className="-mt-2 text-sm text-ink-3">{t("reportCard.gradesOnlyHelp")}</p>
              <div className="grid grid-cols-2 gap-2">
                {(["dx", "dy"] as const).map((axis) => (
                  <label key={axis} className="flex flex-col gap-1 text-sm">
                    {t(`reportCard.${axis}`)}
                    <Input
                      type="number"
                      inputMode="decimal"
                      step="0.5"
                      min={-10}
                      max={10}
                      value={print[axis]}
                      onChange={(event) => {
                        const value = Number(event.target.value);
                        setPrint({ [axis]: Math.min(10, Math.max(-10, value || 0)) });
                      }}
                    />
                  </label>
                ))}
              </div>
              {missing === 0 && classes.length > 0 && (
                <Button asChild variant="outline">
                  <a
                    href={reportCardUrl(groupId, null, "pdf", print)}
                    target="_blank"
                    rel="noopener"
                  >
                    <Icon name="print" size={16} />
                    {t("reportCard.printClass")}
                  </a>
                </Button>
              )}
              {enrollment && missing === 0 && (
                <>
                  <Button asChild>
                    <a href={pdf} target="_blank" rel="noopener">
                      <Icon name="print" size={16} />
                      {t("reportCard.print")}
                    </a>
                  </Button>
                  <Button asChild variant="outline">
                    <a href={pdf} download>
                      <Icon name="download" size={16} />
                      {t("reportCard.pdf")}
                    </a>
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
          <div className="min-[1000px]:order-1">
            {enrollment ? (
              <DocumentPreview
                title={t("reportCard.preview")}
                src={reportCardUrl(groupId, enrollment, "html", print)}
              />
            ) : (
              <Banner tone="info">{t("reportCard.noStudent")}</Banner>
            )}
          </div>
        </div>
      )}
    </>
  );
}
