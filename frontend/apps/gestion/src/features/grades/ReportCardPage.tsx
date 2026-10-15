// Bulletin d'un élève (8.3.2, maquettes `bulletin` et `bulletin-education-de-base`) : le document
// que le serveur met en PDF, avec les places de la classe et un QR code d'authenticité. Droit
// `grades.enter_any` ou `grades.validate` ; l'impression de toute la classe suivra (8.3.3).
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
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

import { studentName } from "../../lib/people";
import { LoadError } from "../status/StatusPages";
import { DocumentPreview } from "../students/DocumentPreview";
import { useStudents } from "../students/data";
import { reportCardUrl, useGrading } from "./data";

export function ReportCardPage() {
  const { t } = useTranslation();
  const grading = useGrading();
  const [classId, setClassId] = useState("");
  const [search, setSearch] = useState("");
  const [enrollmentId, setEnrollmentId] = useState("");
  const classes = grading.data?.classes ?? [];
  const groupId = classId || classes[0]?.id || "";
  const students = useStudents({ class_group: groupId, search: search || undefined }, 1);

  if (grading.isPending) return <Skeleton label={t("common.loading")} />;
  if (grading.isError) {
    return <LoadError error={grading.error} onRetry={() => void grading.refetch()} />;
  }

  const rows = (students.data?.results ?? []).filter((row) => row.enrollment);
  const chosen = rows.find((row) => row.enrollment?.id === enrollmentId) ?? rows[0];
  const enrollment = chosen?.enrollment?.id ?? "";
  const pdf = enrollment ? reportCardUrl(groupId, enrollment, "pdf") : "";

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
                  <option key={row.id} value={row.enrollment?.id}>
                    {studentName(row)}
                  </option>
                ))}
              </Select>
              <p className="text-sm text-ink-3">{t("reportCard.help")}</p>
              {enrollment && (
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
                src={reportCardUrl(groupId, enrollment, "html")}
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
