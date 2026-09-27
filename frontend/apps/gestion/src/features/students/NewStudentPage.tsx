// Inscrire un nouvel élève (D2-D4) : identité, adresse, classe de l'année en cours, famille
// existante ou nouvelle (tuteur principal + autres contacts). Élève puis inscription, chacun avec
// un identifiant donné par l'appareil : un nouvel envoi après une coupure ne crée pas de doublon.
// Même nom, prénom et date de naissance qu'un autre élève : avertissement, puis « Inscrire quand
// même ». Photo : 2.2.2 ; frais appliqués : 2.6 ; hors-ligne : 3.x.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call } from "@mwangaza/api";
import { type TFunction, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  Segmented,
  Select,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useMemo, useRef, useState } from "react";
import {
  Controller,
  type Path,
  type UseFormReturn,
  useFieldArray,
  useForm,
  useWatch,
} from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";

import { applyServerErrors } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { formatPhone, studentName } from "../../lib/people";
import { hasCode, keys } from "../../lib/queries";
import { useSettled } from "../../lib/settled";
import { type ClassGroup, useClasses, useYears } from "../organisation/data";
import type { Created } from "./StudentsPage";
import { type Family, RELATIONSHIPS, type Relationship, useFamilySearch } from "./data";

const MAX_GUARDIANS = 10;

function studentSchema(t: TFunction) {
  const text = (max: number) => z.string().trim().max(max);
  const guardian = z.object({ full_name: text(150), relationship: z.string(), phone: text(20) });
  return z
    .object({
      last_name: text(80).min(1, t("validation.nameRequired")),
      middle_name: text(80).min(1, t("students.validation.middleNameRequired")),
      first_name: text(80),
      sex: z.string().min(1, t("students.validation.sexRequired")),
      birth_date: z.string().min(1, t("validation.dateRequired")),
      birth_place: text(120),
      nationality: text(60),
      origin_province: text(60),
      origin_territory: text(80),
      address: z.object({
        commune: text(80),
        quartier: text(80),
        avenue: text(120),
        number: text(20),
      }),
      previous_school: text(200),
      class_group: z.string().min(1, t("students.validation.classRequired")),
      family_mode: z.enum(["existing", "new"]),
      family: z.string(),
      guardians: z.array(guardian),
    })
    .superRefine((values, context) => {
      const issue = (path: (string | number)[], message: string) =>
        context.addIssue({ code: "custom", path, message });
      if (values.family_mode === "existing") {
        if (!values.family) issue(["family"], t("students.validation.familyRequired"));
        return;
      }
      values.guardians.forEach((guardian, index) => {
        if (!guardian.full_name) {
          issue(["guardians", index, "full_name"], t("students.validation.guardianNameRequired"));
        }
        if (!guardian.relationship) {
          issue(
            ["guardians", index, "relationship"],
            t("students.validation.relationshipRequired"),
          );
        }
      });
      if (!values.guardians[0]?.phone) {
        issue(["guardians", 0, "phone"], t("students.validation.phoneRequired"));
      }
    });
}

type Schema = ReturnType<typeof studentSchema>;
type Values = z.input<Schema>;
type Form = UseFormReturn<Values, unknown, z.output<Schema>>;

const EMPTY_GUARDIAN = { full_name: "", relationship: "", phone: "" };
const EMPTY: Values = {
  last_name: "",
  middle_name: "",
  first_name: "",
  sex: "",
  birth_date: "",
  birth_place: "",
  nationality: "",
  origin_province: "",
  origin_territory: "",
  address: { commune: "", quartier: "", avenue: "", number: "" },
  previous_school: "",
  class_group: "",
  family_mode: "existing",
  family: "",
  guardians: [EMPTY_GUARDIAN],
};

/** Champs où placer un refus du serveur (tuteurs : chaque ligne possible). */
const SERVER_FIELDS = [
  ...(Object.keys(EMPTY) as Path<Values>[]),
  ...(Object.keys(EMPTY.address).map((name) => `address.${name}`) as Path<Values>[]),
  ...Array.from({ length: MAX_GUARDIANS }, (_, index) =>
    (["full_name", "relationship", "phone"] as const).map(
      (name) => `guardians.${index}.${name}` as Path<Values>,
    ),
  ).flat(),
];

export function NewStudentPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const years = useYears();
  const year = years.data?.find((candidate) => candidate.is_current);
  const classes = useClasses(year?.id ?? "");
  // Un identifiant par écran ouvert : renvoyé tel quel si l'envoi est recommencé.
  const ids = useRef({ student: uuidv7(), enrollment: uuidv7() });
  const [general, setGeneral] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState(false);
  const schema = useMemo(() => studentSchema(t), [t]);
  const form: Form = useForm({ resolver: zodResolver(schema), defaultValues: EMPTY });

  const save = useMutation({
    mutationFn: async ({
      values,
      allowDuplicate,
    }: {
      values: z.output<Schema>;
      allowDuplicate: boolean;
    }) => {
      const { class_group, family_mode, family, guardians, sex, ...fields } = values;
      const { student, enrollment } = ids.current;
      await call(
        api.POST("/api/students/", {
          body: {
            id: student,
            ...fields,
            sex: sex as "M" | "F",
            ...(family_mode === "existing"
              ? { family }
              : {
                  guardians: guardians.map((guardian, index) => ({
                    ...guardian,
                    relationship: guardian.relationship as Relationship,
                    is_primary: index === 0,
                  })),
                }),
            allow_duplicate: allowDuplicate,
          },
        }),
      );
      await call(api.POST("/api/enrollments/", { body: { id: enrollment, student, class_group } }));
      return call(api.GET("/api/students/{id}/", { params: { path: { id: student } } }));
    },
    onSuccess: async (student) => {
      await Promise.all(
        [keys.students, keys.families, keys.classes].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      const created: Created = {
        name: studentName(student),
        className:
          student.enrollments.find((item) => item.status === "active")?.class_group_name ?? "",
        matricule: student.matricule,
        familyCode: student.family.code,
      };
      void navigate("/students", { state: { created } });
    },
    onError: (error) => {
      if (hasCode(error, "possible_duplicate")) {
        setDuplicate(true);
        return;
      }
      setGeneral(applyServerErrors(error, SERVER_FIELDS, form.setError, t));
    },
  });
  const submit = (allowDuplicate: boolean) =>
    form.handleSubmit((values) => {
      setGeneral(null);
      setDuplicate(false);
      save.mutate({ values, allowDuplicate });
    });

  const groups = classes.data ?? [];
  const noYear = years.data && !year;
  const blocked = noYear || (classes.data && groups.length === 0);
  const { errors } = form.formState;
  const input = (name: Path<Values>, label: string, required = false, type = "text") => (
    <Field
      id={`student-${name}`}
      label={label}
      required={required}
      error={fieldError(errors, name)}
    >
      {(control) => <Input {...control} type={type} {...form.register(name)} />}
    </Field>
  );

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            / {t("students.new.crumb")}
          </>
        }
        title={t("students.new.title")}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/students">{t("common.cancel")}</Link>
            </Button>
            <Button type="submit" form="new-student" disabled={save.isPending || Boolean(blocked)}>
              {t("students.new.submit")}
            </Button>
          </>
        }
      />
      {noYear && <Banner tone="warn">{t("students.new.noYear")}</Banner>}
      {year && classes.data && groups.length === 0 && (
        <Banner tone="warn">{t("students.new.noClasses")}</Banner>
      )}
      {general && <Banner tone="due">{general}</Banner>}
      {duplicate && (
        <Banner tone="warn" role="alert">
          <span className="flex flex-col items-start gap-2">
            {t("students.new.duplicate")}
            <Button type="button" size="sm" variant="outline" onClick={() => void submit(true)()}>
              {t("students.new.duplicateConfirm")}
            </Button>
          </span>
        </Banner>
      )}
      <form
        id="new-student"
        noValidate
        onSubmit={submit(false)}
        className="flex max-w-[1040px] flex-col gap-5"
      >
        <Section title={t("students.new.identity")}>
          <div className="grid gap-3 min-[700px]:grid-cols-3">
            {input("last_name", t("students.new.lastName"), true)}
            {input("middle_name", t("students.new.middleName"), true)}
            {input("first_name", t("students.new.firstName"))}
            <div className="flex flex-col gap-1.5">
              <span className="text-[.87rem] font-bold text-ink-2">
                {t("students.new.sex")}
                <span className="text-due" aria-hidden="true">
                  {" "}
                  *
                </span>
              </span>
              <Controller
                control={form.control}
                name="sex"
                render={({ field }) => (
                  <Segmented
                    label={t("students.new.sex")}
                    value={field.value as "M" | "F"}
                    onValueChange={field.onChange}
                    options={[
                      { value: "M", label: t("students.new.male") },
                      { value: "F", label: t("students.new.female") },
                    ]}
                    className="self-start"
                  />
                )}
              />
              {errors.sex && (
                <p role="alert" className="text-[.8rem] text-due">
                  {errors.sex.message}
                </p>
              )}
            </div>
            {input("birth_date", t("students.new.birthDate"), true, "date")}
            {input("birth_place", t("students.new.birthPlace"))}
            {input("nationality", t("students.new.nationality"))}
            {input("origin_province", t("students.new.originProvince"))}
            {input("origin_territory", t("students.new.originTerritory"))}
          </div>
        </Section>
        <Section title={t("students.new.address")}>
          <div className="grid gap-3 min-[700px]:grid-cols-4">
            {input("address.commune", t("students.new.commune"))}
            {input("address.quartier", t("students.new.quartier"))}
            {input("address.avenue", t("students.new.avenue"))}
            {input("address.number", t("students.new.number"))}
          </div>
        </Section>
        <Section title={t("students.new.schooling", { year: year?.name ?? "" })}>
          <div className="grid gap-3 min-[700px]:grid-cols-3">
            <ClassField form={form} groups={groups} />
            {input("previous_school", t("students.new.previousSchool"))}
            <Field
              id="student-matricule"
              label={t("students.new.matricule")}
              help={t("students.new.matriculeHelp")}
            >
              {(control) => (
                <Input
                  {...control}
                  readOnly
                  value={t("students.new.matriculeValue")}
                  className="text-ink-3"
                />
              )}
            </Field>
          </div>
        </Section>
        <FamilySection form={form} />
      </form>
    </>
  );
}

function fieldError(errors: Form["formState"]["errors"], name: string): string | undefined {
  const found = name
    .split(".")
    .reduce<unknown>(
      (node, key) => (node as Record<string, unknown> | undefined)?.[key],
      errors,
    ) as { message?: string } | undefined;
  return found?.message;
}

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function ClassField({ form, groups }: { form: Form; groups: ClassGroup[] }) {
  const { t } = useTranslation();
  const value = useWatch({ control: form.control, name: "class_group" });
  const chosen = groups.find((group) => group.id === value);
  return (
    <Field
      id="student-class"
      label={t("students.new.class")}
      required
      error={form.formState.errors.class_group?.message}
      help={
        chosen &&
        (chosen.capacity === null
          ? t("students.new.enrolledCount", { count: chosen.student_count })
          : t("students.new.places", { count: chosen.student_count, capacity: chosen.capacity }))
      }
    >
      {(control) => (
        <Select {...control} {...form.register("class_group")}>
          <option value="">{t("students.new.chooseClass")}</option>
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}

function FamilySection({ form }: { form: Form }) {
  const { t } = useTranslation();
  const mode = useWatch({ control: form.control, name: "family_mode" });
  return (
    <Section
      title={t("students.new.family")}
      action={
        <Segmented
          label={t("students.new.family")}
          value={mode}
          onValueChange={(value) => form.setValue("family_mode", value, { shouldValidate: false })}
          options={[
            { value: "existing", label: t("students.new.existingFamily") },
            { value: "new", label: t("students.new.newFamily") },
          ]}
        />
      }
    >
      {mode === "existing" ? <ExistingFamily form={form} /> : <NewFamily form={form} />}
    </Section>
  );
}

function ExistingFamily({ form }: { form: Form }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [chosen, setChosen] = useState<Family | null>(null);
  const settled = useSettled(search.trim());
  const families = useFamilySearch(settled);
  const results = (families.data?.results ?? []).filter((family) => family.id !== chosen?.id);
  const choose = (family: Family) => {
    setChosen(family);
    form.setValue("family", family.id, { shouldValidate: true });
  };
  return (
    <div className="flex flex-col gap-3">
      <Field
        id="family-search"
        label={t("students.new.familySearch")}
        error={form.formState.errors.family?.message}
      >
        {(control) => (
          <Input
            {...control}
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        )}
      </Field>
      {chosen && <FamilyCard family={chosen} chosen />}
      {results.slice(0, 5).map((family) => (
        <FamilyCard key={family.id} family={family} onChoose={() => choose(family)} />
      ))}
      {families.data && families.data.count === 0 && (
        <p className="text-sm text-ink-3">{t("students.new.familyNone")}</p>
      )}
    </div>
  );
}

function FamilyCard({
  family,
  chosen,
  onChoose,
}: {
  family: Family;
  chosen?: boolean;
  onChoose?: () => void;
}) {
  const { t } = useTranslation();
  const [main] = family.guardians;
  const children = family.students
    .map((child) => [studentName(child), child.class_group_name].filter(Boolean).join(", "))
    .join(" ; ");
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line p-3.5">
      <div className="text-[.92rem]">
        <b>{main ? main.full_name : t("students.new.familyCode", { code: family.code })}</b>
        {main && (
          <>
            {" "}
            ({t(`students.relationships.${main.relationship}`)})
            {main.phone && ` · ${formatPhone(main.phone)}`}
            {` · ${t("students.new.familyCode", { code: family.code })}`}
          </>
        )}
        <br />
        <span className="text-sm text-ink-3">
          {family.students.length
            ? t("students.new.children", { count: family.students.length, names: children })
            : t("students.new.noChildren")}
        </span>
      </div>
      {chosen ? (
        <span className="inline-flex items-center gap-1.5 rounded-field bg-lake px-3 py-1.5 text-sm font-bold text-white">
          <Icon name="check" size={14} />
          {t("students.new.chosen")}
        </span>
      ) : (
        <Button type="button" size="sm" variant="outline" onClick={onChoose}>
          {t("students.new.choose")}
        </Button>
      )}
    </div>
  );
}

function NewFamily({ form }: { form: Form }) {
  const { t } = useTranslation();
  const guardians = useFieldArray({ control: form.control, name: "guardians" });
  const errors = form.formState.errors.guardians;
  return (
    <div className="flex flex-col gap-4">
      {guardians.fields.map((row, index) => (
        <fieldset key={row.id} className="grid gap-3 min-[700px]:grid-cols-[1.4fr_1fr_1fr_auto]">
          <legend className="mb-2 text-[.87rem] font-bold text-ink-2">
            {index === 0 ? t("students.new.primaryGuardian") : t("students.new.otherContact")}
          </legend>
          <Field
            id={`guardian-${index}-name`}
            label={t("students.new.fullName")}
            required
            error={errors?.[index]?.full_name?.message}
          >
            {(control) => <Input {...control} {...form.register(`guardians.${index}.full_name`)} />}
          </Field>
          <Field
            id={`guardian-${index}-relationship`}
            label={t("students.new.relationship")}
            required
            error={errors?.[index]?.relationship?.message}
          >
            {(control) => (
              <Select {...control} {...form.register(`guardians.${index}.relationship`)}>
                <option value="">{t("students.new.chooseRelationship")}</option>
                {RELATIONSHIPS.map((relationship) => (
                  <option key={relationship} value={relationship}>
                    {t(`students.relationships.${relationship}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field
            id={`guardian-${index}-phone`}
            label={t("students.new.phone")}
            required={index === 0}
            error={errors?.[index]?.phone?.message}
          >
            {(control) => (
              <Input {...control} inputMode="tel" {...form.register(`guardians.${index}.phone`)} />
            )}
          </Field>
          <div className="flex items-end">
            {index > 0 && (
              <Button
                type="button"
                variant="ghost"
                aria-label={t("students.new.removeContact")}
                onClick={() => guardians.remove(index)}
              >
                <Icon name="x" size={16} />
              </Button>
            )}
          </div>
        </fieldset>
      ))}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-3">{t("students.new.newFamilyHelp")}</p>
        {guardians.fields.length < MAX_GUARDIANS && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => guardians.append(EMPTY_GUARDIAN)}
          >
            <Icon name="plus" size={14} />
            {t("students.new.addContact")}
          </Button>
        )}
      </div>
    </div>
  );
}
