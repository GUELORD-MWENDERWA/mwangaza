import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Icon,
  PageHeader,
  Skeleton,
} from "@mwangaza/ui";
import { type ReactNode, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { CHARGES_READ, type StatementOptions, statementUrl, useStudent } from "./data";
import { DocumentPreview } from "./DocumentPreview";

/** Situation financière imprimable (G2, M17, maquette `situation-financiere`) : document produit
 * par le serveur (PDF et son aperçu), même calcul que l'onglet Finances ; chaque PDF est noté
 * dans le journal d'audit et porte un QR code de vérification. */
function Statement({
  enrollments,
  crumbs,
  title,
  subtitle,
}: {
  enrollments: string[];
  crumbs: ReactNode;
  title: string;
  subtitle: string;
}) {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const [options, setOptions] = useState<StatementOptions>({
    upcoming: true,
    payments: true,
    hidePaid: false,
  });
  const option = (name: keyof StatementOptions, id: string) => (
    <CheckboxField
      id={id}
      label={t(`students.print.statement.${name}`)}
      checked={options[name]}
      onCheckedChange={(checked) => setOptions({ ...options, [name]: checked === true })}
    />
  );
  const pdf = statementUrl(enrollments, { output: "pdf", ...options });

  return (
    <>
      <PageHeader crumbs={crumbs} title={title} subtitle={subtitle} />
      {!can(me, CHARGES_READ) ? (
        <Banner tone="warn">{t("students.print.statement.right")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="min-[1000px]:order-2">
            <CardHeader>
              <CardTitle>{t("students.print.print")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {option("upcoming", "statement-upcoming")}
              {option("payments", "statement-payments")}
              {option("hidePaid", "statement-hide-paid")}
              <p className="text-[.82rem] text-ink-3">{t("students.print.statement.help")}</p>
              <Button asChild>
                <a href={pdf} target="_blank" rel="noopener">
                  <Icon name="print" size={16} />
                  {t("students.print.print")}
                </a>
              </Button>
              <Button asChild variant="outline">
                <a href={pdf} download>
                  <Icon name="download" size={16} />
                  {t("students.print.pdf")}
                </a>
              </Button>
            </CardContent>
          </Card>
          <div className="min-[1000px]:order-1">
            <DocumentPreview
              title={t("students.print.statement.preview")}
              src={statementUrl(enrollments, { output: "html", ...options })}
            />
          </div>
        </div>
      )}
    </>
  );
}

/** Depuis la fiche de l'élève : inscription de l'année en cours. */
export function StudentStatementPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const student = useStudent(id);
  const years = useYears();

  if (student.error)
    return <LoadError error={student.error} onRetry={() => void student.refetch()} />;
  if (!student.data || !years.data) return <Skeleton label={t("common.loading")} />;
  const data = student.data;
  const year = years.data.find((candidate) => candidate.is_current);
  const enrollment = data.enrollments.find((item) => item.academic_year === year?.id);
  const crumbs = (
    <>
      <Link to="/students" className="text-lake underline">
        {t("students.list.title")}
      </Link>{" "}
      /{" "}
      <Link to={`/students/${data.id}/finances`} className="text-lake underline">
        {studentName(data)}
      </Link>{" "}
      / {t("students.print.statement.title")}
    </>
  );
  if (!enrollment)
    return (
      <>
        <PageHeader crumbs={crumbs} title={t("students.print.statement.title")} />
        <Banner tone="warn">{t("students.print.statement.notEnrolled")}</Banner>
      </>
    );
  return (
    <Statement
      enrollments={[enrollment.id]}
      crumbs={crumbs}
      title={t("students.print.statement.title")}
      subtitle={t("students.print.statement.subtitle")}
    />
  );
}

/** Depuis les Impayés : les élèves cochés (`?enrollment=…` répété), une page par élève. */
export function UnpaidStatementsPage() {
  const { t } = useTranslation();
  const enrollments = useSearchParams()[0].getAll("enrollment");
  const crumbs = (
    <>
      <Link to="/unpaid" className="text-lake underline">
        {t("unpaid.title")}
      </Link>{" "}
      / {t("students.print.statement.groupTitle")}
    </>
  );
  if (enrollments.length === 0)
    return (
      <>
        <PageHeader crumbs={crumbs} title={t("students.print.statement.groupTitle")} />
        <Banner tone="warn">{t("students.print.statement.noSelection")}</Banner>
      </>
    );
  return (
    <Statement
      enrollments={enrollments}
      crumbs={crumbs}
      title={t("students.print.statement.groupTitle")}
      subtitle={t("students.print.statement.groupSubtitle", { count: enrollments.length })}
    />
  );
}
