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
  Segmented,
  Skeleton,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { CHARGES_READ, type Paper, registrationFormUrl, useStudent } from "./data";
import { DocumentPreview } from "./DocumentPreview";

/** Fiche d'inscription de l'année en cours (D5, M11) : remise au parent avec le code famille,
 * ou à un tiers sans lui. Le code n'apparaît que sur le PDF, noté dans le journal. Frais de
 * l'année (2.7) : proposés avec un droit de lecture des frais, vérifié par le serveur. */
export function RegistrationFormPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const student = useStudent(id);
  const years = useYears();
  const [paper, setPaper] = useState<Paper>("a4");
  const [familyCode, setFamilyCode] = useState(true);
  const [fees, setFees] = useState(true);
  const canReadFees = can(useCurrentMe(), CHARGES_READ);

  if (student.error)
    return <LoadError error={student.error} onRetry={() => void student.refetch()} />;
  if (!student.data || !years.data) return <Skeleton label={t("common.loading")} />;
  const data = student.data;
  const year = years.data.find((candidate) => candidate.is_current);
  const enrollment = data.enrollments.find((item) => item.academic_year === year?.id);
  const options = { paper, familyCode, fees: canReadFees && fees };

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            /{" "}
            <Link to={`/students/${data.id}`} className="text-lake underline">
              {studentName(data)}
            </Link>{" "}
            / {t("students.print.form.title")}
          </>
        }
        title={t("students.print.form.title")}
        subtitle={t("students.print.form.subtitle")}
      />
      {!enrollment ? (
        <Banner tone="warn">{t("students.print.form.notEnrolled")}</Banner>
      ) : (
        <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_320px]">
          <Card className="min-[1000px]:order-2">
            <CardHeader>
              <CardTitle>{t("students.print.print")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <span className="text-[.87rem] font-bold text-ink-2">
                  {t("students.print.form.paper")}
                </span>
                <Segmented
                  label={t("students.print.form.paper")}
                  value={paper}
                  onValueChange={setPaper}
                  options={[
                    { value: "a4", label: "A4" },
                    { value: "a5", label: "A5" },
                  ]}
                />
              </div>
              <div className="flex flex-col gap-1">
                <CheckboxField
                  id="family-code"
                  label={t("students.print.form.familyCode")}
                  checked={familyCode}
                  onCheckedChange={(checked) => setFamilyCode(checked === true)}
                />
                <p className="text-[.82rem] text-ink-3">
                  {t("students.print.form.familyCodeHelp")}
                </p>
              </div>
              {canReadFees && (
                <div className="flex flex-col gap-1">
                  <CheckboxField
                    id="fees"
                    label={t("students.print.form.fees")}
                    checked={fees}
                    onCheckedChange={(checked) => setFees(checked === true)}
                  />
                  <p className="text-[.82rem] text-ink-3">{t("students.print.form.feesHelp")}</p>
                </div>
              )}
              <Button asChild>
                <a
                  href={registrationFormUrl(enrollment.id, { output: "pdf", ...options })}
                  target="_blank"
                  rel="noopener"
                >
                  <Icon name="print" size={16} />
                  {t("students.print.print")}
                </a>
              </Button>
              <Button asChild variant="outline">
                <a
                  href={registrationFormUrl(enrollment.id, { output: "pdf", ...options })}
                  download
                >
                  <Icon name="download" size={16} />
                  {t("students.print.pdf")}
                </a>
              </Button>
              <Button asChild variant="ghost">
                <Link to={`/students/${data.id}`}>{t("students.print.form.openStudent")}</Link>
              </Button>
            </CardContent>
          </Card>
          <div className="min-[1000px]:order-1">
            <DocumentPreview
              title={t("students.print.form.preview")}
              src={registrationFormUrl(enrollment.id, { output: "html", ...options })}
            />
          </div>
        </div>
      )}
    </>
  );
}
