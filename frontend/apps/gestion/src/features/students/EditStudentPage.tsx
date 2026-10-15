// Modifier l'élève (M9, D2) : les champs d'« Inscrire un nouvel élève », pré-remplis, sans la
// classe ni la famille (onglet Famille). L'identité appartient à l'école (Q10) ; chaque changement
// va dans le journal (onglet Historique). Matricule : corrigé à la main seulement en cas d'erreur.
// Droit `students.edit` (vérifié avant l'écran et par le serveur). Hors-ligne : 3.x.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call } from "@mwangaza/api";
import { type TFunction, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, PageHeader, Skeleton } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { type Path, type UseFormReturn, useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import {
  IDENTITY_PATHS,
  IdentitySections,
  PhotoSection,
  Section,
  TextField,
  identityShape,
} from "./StudentFields";
import { type Student, useStudent } from "./data";

function editSchema(t: TFunction) {
  return z.object({ ...identityShape(t), matricule: z.string().trim().max(40) });
}

type Schema = ReturnType<typeof editSchema>;
type Values = z.input<Schema>;
type Form = UseFormReturn<Values, unknown, z.output<Schema>>;

function valuesOf(student: Student): Values {
  const { address } = student;
  return {
    last_name: student.last_name,
    middle_name: student.middle_name,
    first_name: student.first_name,
    sex: student.sex,
    birth_date: student.birth_date ?? "",
    birth_place: student.birth_place,
    national_id: student.national_id,
    permanent_number: student.permanent_number,
    nationality: student.nationality,
    origin_province: student.origin_province,
    origin_territory: student.origin_territory,
    address: {
      commune: address.commune ?? "",
      quartier: address.quartier ?? "",
      avenue: address.avenue ?? "",
      number: address.number ?? "",
    },
    previous_school: student.previous_school,
    photo_consent: student.photo_consent,
    matricule: student.matricule,
  };
}

export function EditStudentPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const student = useStudent(id);
  if (student.error)
    return <LoadError error={student.error} onRetry={() => void student.refetch()} />;
  if (!student.data) return <Skeleton label={t("common.loading")} />;
  return <EditForm student={student.data} />;
}

function EditForm({ student }: { student: Student }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(() => editSchema(t), [t]);
  const form: Form = useForm({ resolver: zodResolver(schema), defaultValues: valuesOf(student) });
  const back = `/students/${student.id}`;

  const save = useMutation({
    mutationFn: ({ sex, ...values }: z.output<Schema>) =>
      call(
        api.PATCH("/api/students/{id}/", {
          params: { path: { id: student.id } },
          body: { ...values, sex: sex as "M" | "F", allow_duplicate: false },
        }),
      ),
    onSuccess: async (updated) => {
      queryClient.setQueryData([...keys.students, "detail", student.id], updated);
      await queryClient.invalidateQueries({ queryKey: keys.students });
      void navigate(back);
    },
    onError: (error) =>
      setGeneral(
        applyServerErrors(
          error,
          [...IDENTITY_PATHS, "matricule"] as Path<Values>[],
          form.setError,
          t,
        ),
      ),
  });

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            /{" "}
            <Link to={back} className="text-lake underline">
              {studentName(student)}
            </Link>{" "}
            / {t("students.edit.crumb")}
          </>
        }
        title={t("students.edit.title")}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to={back}>{t("common.cancel")}</Link>
            </Button>
            <Button type="submit" form="edit-student" disabled={save.isPending}>
              {t("students.edit.submit")}
            </Button>
          </>
        }
      />
      {general && <Banner tone="due">{general}</Banner>}
      <form
        id="edit-student"
        noValidate
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          save.mutate(values);
        })}
        className="flex max-w-[1040px] flex-col gap-5"
      >
        <IdentitySections form={form} />
        <Section title={t("students.edit.schooling")}>
          <div className="grid gap-3 min-[700px]:grid-cols-2">
            <TextField
              form={form}
              name="previous_school"
              label={t("students.new.previousSchool")}
            />
            <TextField
              form={form}
              name="matricule"
              label={t("students.new.matricule")}
              help={t("students.edit.matriculeHelp")}
            />
          </div>
        </Section>
        <PhotoSection form={form} />
      </form>
    </>
  );
}
