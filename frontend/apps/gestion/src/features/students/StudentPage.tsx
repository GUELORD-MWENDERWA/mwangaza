// Fiche élève (M9, D2-D4) : en-tête (matricule, classe, sexe et âge, statut de l'année) et onglets
// Identité, Famille, Finances (avec les frais : 2.7), Historique ; une adresse par onglet. Changer :
// `students.edit`, sinon lecture seule : changer de classe, départ, inscrire pour l'année (2.6.1,
// `EnrollmentActions`) ; impressions : 2.4 ; encaisser : 3.x ; documents : V1.1 ; scolarité : V1.2.
import { ApiError, api, call } from "@mwangaza/api";
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Code,
  ConfirmDialog,
  Icon,
  Skeleton,
  StatusPill,
  Tabs,
  TabsList,
  TabsTrigger,
  Tag,
  initials,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { errorMessage, fieldMessage } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useYears } from "../organisation/data";
import { LoadError, NotFound } from "../status/StatusPages";
import { EnrollmentActions } from "./EnrollmentActions";
import { SchedulePanel } from "./SchedulePanel";
import { StudentFamilyTab } from "./StudentFamilyTab";
import { StudentFinancesTab } from "./StudentFinancesTab";
import { StudentHistoryTab } from "./StudentHistoryTab";
import { type Student, age, uploadPhoto, useStudent } from "./data";
import { shrinkPhoto } from "./photo";

/** Élève que l'écran « Inscrire un élève » vient d'enregistrer (état de la navigation). */
export type Created = { name: string; className: string; matricule: string; familyCode: string };

const TABS = ["identity", "family", "finances", "history"] as const;
type Tab = (typeof TABS)[number];

/** `schedule` : l'onglet « Finances » ouvert sur l'échéancier particulier (E4). */
export function StudentPage({ schedule = false }: { schedule?: boolean }) {
  const { t } = useTranslation();
  const { id = "", tab = schedule ? "finances" : undefined } = useParams();
  const navigate = useNavigate();
  const me = useCurrentMe();
  const created = (useLocation().state as { created?: Created } | null)?.created;
  const student = useStudent(id);
  const years = useYears();
  const current: Tab | undefined = tab === undefined ? "identity" : TABS.find((x) => x === tab);

  if (!current) return <NotFound />;
  if (student.error)
    return <LoadError error={student.error} onRetry={() => void student.refetch()} />;
  if (!student.data) return <Skeleton label={t("common.loading")} />;
  const data = student.data;
  const year = years.data?.find((candidate) => candidate.is_current);
  const enrollment = data.enrollments.find((item) => item.academic_year === year?.id);
  const canEdit = can(me, ["students.edit"]);

  return (
    <>
      <p className="text-sm text-ink-3">
        <Link to="/students" className="text-lake underline">
          {t("students.list.title")}
        </Link>{" "}
        / {studentName(data)}
      </p>
      {created && (
        <Banner tone="ok" role="status">
          {t(created.matricule ? "students.card.created" : "students.card.createdNoMatricule", {
            name: created.name,
            className: created.className,
            matricule: created.matricule,
            code: created.familyCode,
          })}{" "}
          <Link to={`/students/${data.id}/form`} className="font-bold underline">
            {t("students.print.form.printIt")}
          </Link>
        </Banner>
      )}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4">
          <Avatar
            text={initials(data.middle_name || data.first_name, data.last_name)}
            className="size-16 text-xl"
          />
          <div className="min-w-[220px] flex-1">
            <h1 className="text-2xl font-bold">{studentName(data)}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm">
              {data.matricule && <Tag className="tabular-nums">{data.matricule}</Tag>}
              {enrollment && <Tag>{enrollment.class_group_name}</Tag>}
              <Tag>
                {[
                  t(data.sex === "F" ? "students.new.female" : "students.new.male"),
                  data.birth_date && t("students.card.age", { count: age(data.birth_date) }),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </Tag>
              {enrollment ? (
                <StatusPill tone={enrollment.status === "active" ? "ok" : "warn"}>
                  {t(`students.enrollmentStatus.${enrollment.status}`)}
                </StatusPill>
              ) : (
                <StatusPill>{t("students.list.notEnrolled")}</StatusPill>
              )}
            </div>
          </div>
          {enrollment && (
            <Button asChild variant="outline">
              <Link to={`/students/${data.id}/form`}>
                <Icon name="print" size={16} />
                {t("students.print.form.title")}
              </Link>
            </Button>
          )}
          {canEdit && (
            <Button asChild variant="outline">
              <Link to={`/students/${data.id}/edit`}>
                <Icon name="edit" size={16} />
                {t("students.card.edit")}
              </Link>
            </Button>
          )}
        </CardContent>
        <Tabs
          value={current}
          onValueChange={(value) =>
            void navigate(`/students/${data.id}${value === "identity" ? "" : `/${value}`}`)
          }
        >
          <TabsList className="px-4">
            {TABS.map((name) => (
              <TabsTrigger key={name} value={name}>
                {t(`students.card.tabs.${name}`)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </Card>
      {current === "identity" && (
        <IdentityTab student={data} enrollment={enrollment} year={year} canEdit={canEdit} />
      )}
      {current === "family" && <StudentFamilyTab student={data} canEdit={canEdit} />}
      {current === "finances" &&
        (schedule ? (
          <SchedulePanel student={data} enrollment={enrollment} />
        ) : (
          <StudentFinancesTab student={data} enrollment={enrollment} />
        ))}
      {current === "history" && <StudentHistoryTab student={data} />}
    </>
  );
}

type Enrollment = Student["enrollments"][number];

function Info({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-xs text-ink-3">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

function IdentityTab({
  student,
  enrollment,
  year,
  canEdit,
}: {
  student: Student;
  enrollment: Enrollment | undefined;
  year: { id: string; name: string } | undefined;
  canEdit: boolean;
}) {
  const { t, i18n } = useTranslation();
  const none = t("common.none");
  const text = (value: string) => value || none;
  const { address } = student;
  return (
    <div className="grid items-start gap-4 min-[1100px]:grid-cols-[2fr_1fr]">
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("students.new.identity")}</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 min-[600px]:grid-cols-3">
            <Info label={t("students.new.lastName")}>
              <b>{student.last_name}</b>
            </Info>
            <Info label={t("students.new.middleName")}>
              <b>{text(student.middle_name)}</b>
            </Info>
            <Info label={t("students.new.firstName")}>
              <b>{text(student.first_name)}</b>
            </Info>
            <Info label={t("students.new.sex")}>
              {t(student.sex === "F" ? "students.new.female" : "students.new.male")}
            </Info>
            <Info label={t("students.new.birthDate")}>
              {student.birth_date ? (
                <>
                  {formatDay(student.birth_date, i18n.language)}{" "}
                  <span className="text-sm text-ink-3">
                    ({t("students.card.age", { count: age(student.birth_date) })})
                  </span>
                </>
              ) : (
                none
              )}
            </Info>
            <Info label={t("students.new.birthPlace")}>{text(student.birth_place)}</Info>
            <Info label={t("students.new.nationalId")}>{text(student.national_id)}</Info>
            <Info label={t("students.new.permanentNumber")}>{text(student.permanent_number)}</Info>
            <Info label={t("students.new.nationality")}>{text(student.nationality)}</Info>
            <Info label={t("students.new.originProvince")}>{text(student.origin_province)}</Info>
            <Info label={t("students.new.originTerritory")}>{text(student.origin_territory)}</Info>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("students.new.address")}</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 min-[600px]:grid-cols-4">
            <Info label={t("students.new.commune")}>{text(address.commune ?? "")}</Info>
            <Info label={t("students.new.quartier")}>{text(address.quartier ?? "")}</Info>
            <Info label={t("students.new.avenue")}>{text(address.avenue ?? "")}</Info>
            <Info label={t("students.new.number")}>{text(address.number ?? "")}</Info>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
            <CardTitle>{t("students.card.enrollment", { year: year?.name ?? "" })}</CardTitle>
            {enrollment && (
              <StatusPill tone={enrollment.status === "active" ? "ok" : "warn"}>
                {t(`students.enrollmentStatus.${enrollment.status}`)}
              </StatusPill>
            )}
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 min-[600px]:grid-cols-3">
            <Info label={t("students.new.class")}>
              {enrollment ? <b>{enrollment.class_group_name}</b> : t("students.list.notEnrolled")}
            </Info>
            <Info label={t("students.new.matricule")}>{text(student.matricule)}</Info>
            <Info label={t("students.card.enrolledOn")}>
              {enrollment?.enrolled_on ? formatDay(enrollment.enrolled_on, i18n.language) : none}
            </Info>
            <Info label={t("students.new.previousSchool")}>{text(student.previous_school)}</Info>
            <Info label={t("students.card.familyCode")}>
              <Code>{student.family.code}</Code>
            </Info>
          </CardContent>
          {canEdit && year && (
            <EnrollmentActions student={student} enrollment={enrollment} year={year} />
          )}
        </Card>
      </div>
      <PhotoCard student={student} />
    </div>
  );
}

function PhotoCard({ student }: { student: Student }) {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const canEdit = can(me, ["students.edit"]);
  const done = (updated: Student) => {
    queryClient.setQueryData([...keys.students, "detail", student.id], updated);
    setConfirm(false);
  };
  const upload = useMutation({
    mutationFn: async (file: File) => uploadPhoto(student.id, await shrinkPhoto(file)),
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: () =>
      call(api.DELETE("/api/students/{id}/photo/", { params: { path: { id: student.id } } })),
    onSuccess: done,
  });
  const failed = upload.error ?? remove.error;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("students.photo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-3">
        <div className="grid h-[180px] w-[150px] place-items-center overflow-hidden rounded-card bg-lake-50 text-lake">
          {student.photo ? (
            <img
              src={student.photo}
              alt={t("students.photo.alt", { name: studentName(student) })}
              className="size-full object-cover"
            />
          ) : (
            <Icon name="user" size={64} />
          )}
        </div>
        <StatusPill tone={student.photo_consent ? "ok" : "gray"}>
          {t(student.photo_consent ? "students.photo.consentYes" : "students.photo.consentNo")}
        </StatusPill>
        {failed && (
          <p role="alert" className="text-sm text-due">
            {failed instanceof ApiError && failed.fields.photo?.[0]
              ? fieldMessage(failed.fields.photo[0].code, t)
              : errorMessage(failed, t)}
          </p>
        )}
        {canEdit && (
          <div className="flex flex-wrap justify-center gap-2">
            <Button asChild size="sm" variant="outline" disabled={upload.isPending}>
              <label>
                <Icon name="upload" size={14} />
                {t(student.photo ? "students.photo.change" : "students.photo.add")}
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) upload.mutate(file);
                    event.target.value = "";
                  }}
                />
              </label>
            </Button>
            {student.photo && (
              <Button size="sm" variant="ghost" onClick={() => setConfirm(true)}>
                {t("students.photo.remove")}
              </Button>
            )}
          </div>
        )}
      </CardContent>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={t("students.photo.removeTitle")}
        confirmLabel={t("students.photo.remove")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      />
    </Card>
  );
}
