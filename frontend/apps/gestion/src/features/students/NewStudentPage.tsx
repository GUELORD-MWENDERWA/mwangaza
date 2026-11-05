// Inscrire un nouvel élève (D2-D4) : identité, adresse, classe de l'année en cours, famille
// existante ou nouvelle (tuteur principal + autres contacts). Élève puis inscription, chacun avec
// un identifiant donné par l'appareil : un nouvel envoi après une coupure ne crée pas de doublon.
// Même nom, prénom et date de naissance qu'un autre élève : avertissement avec le lien vers sa
// fiche, puis « Inscrire quand même ». Photo envoyée après l'inscription ; puis la fiche s'ouvre.
// Frais appliqués : 2.6. Appareil mémorisé sans réseau (HL.1, maquette `eleve-nouveau-hors-ligne`) :
// même formulaire, l'inscription part dans la file (`offline.ts`), numéros provisoires, puis
// « Inscrire et encaisser » ouvre la caisse sur l'élève ; doublon de l'appareil signalé avant.
import { zodResolver } from "@hookform/resolvers/zod";
import { type ApiError, api, call } from "@mwangaza/api";
import { formatDate, formatTime, type TFunction, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Field, Icon, Input, PageHeader, Segmented, Select } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { type Path, type UseFormReturn, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { uuidv7 } from "../../lib/ids";
import { useOnline } from "../../lib/online";
import { formatPhone, studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { hasCode, keys, useCurrentMe, useSchool } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useSettled } from "../../lib/settled";
import type { LocalEnrollment } from "../../lib/sync/db";
import type { Enrollment } from "../../lib/sync/engine";
import { useSyncStatus } from "../../lib/sync/session";
import type { Chosen } from "../cash/CollectPanel";
import { schoolDay } from "../cash/offline";
import { useClasses, useYears } from "../organisation/data";
import type { Created } from "./StudentPage";
import {
  birthDateRequired,
  IDENTITY_EMPTY,
  IDENTITY_PATHS,
  IdentitySections,
  PhotoSection,
  Section,
  TextField,
  identityShape,
} from "./StudentFields";
import {
  type Family,
  RELATIONSHIPS,
  type Relationship,
  uploadPhoto,
  useFamilySearch,
} from "./data";
import {
  type DeviceStudents,
  deviceCharges,
  enrollOffline,
  localDuplicates,
  type OfflineEnrollment,
  provisionalFamilyCode,
  provisionalMatricule,
  searchLocalFamilies,
  useDeviceStudents,
} from "./offline";

/** Élève qui a déjà les mêmes noms et date de naissance (réponse `possible_duplicate`). */
type Duplicate = {
  id: string;
  last_name: string;
  middle_name: string;
  first_name: string;
  matricule: string;
};

const MAX_GUARDIANS = 10;

function studentSchema(t: TFunction, birthDate: boolean) {
  const text = (max: number) => z.string().trim().max(max);
  const guardian = z.object({ full_name: text(150), relationship: z.string(), phone: text(20) });
  return z
    .object({
      ...identityShape(t, birthDate),
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
type Output = z.output<Schema>;
type Form = UseFormReturn<Values, unknown, Output>;

/** Ce que reçoivent « Inscrire un élève » et l'opération `student.enroll` (sans les identifiants),
 *  et la classe choisie. */
function studentBody({ class_group, family_mode, family, guardians, sex, ...fields }: Output) {
  const body = {
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
  };
  return { body, classGroup: class_group };
}

const newIds = () => ({ student: uuidv7(), enrollment: uuidv7(), family: uuidv7() });

const EMPTY_GUARDIAN = { full_name: "", relationship: "", phone: "" };
const EMPTY: Values = {
  ...IDENTITY_EMPTY,
  class_group: "",
  family_mode: "existing",
  family: "",
  guardians: [EMPTY_GUARDIAN],
};

/** Champs où placer un refus du serveur (tuteurs : chaque ligne possible). */
const SERVER_FIELDS = [
  ...(IDENTITY_PATHS as Path<Values>[]),
  ...(["class_group", "family"] as const),
  ...Array.from({ length: MAX_GUARDIANS }, (_, index) =>
    (["full_name", "relationship", "phone"] as const).map(
      (name) => `guardians.${index}.${name}` as Path<Values>,
    ),
  ).flat(),
];

export function NewStudentPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const school = useCurrentSchool();
  // Appareil mémorisé sans réseau, ou serveur injoignable au dernier essai : l'inscription passe
  // par la file (HL.1). Le formulaire reste le même si le réseau va et vient.
  const sync = useSyncStatus();
  const online = useOnline();
  const device = useDeviceStudents(sync.db);
  const offline = Boolean(sync.db) && (!online || sync.failed);
  const years = useYears();
  const serverYear = years.data?.find((candidate) => candidate.is_current);
  const year = offline ? device?.config?.academic_year : serverYear;
  const classes = useClasses(offline ? "" : (serverYear?.id ?? ""));
  // C5 : rien n'est annoncé si l'école n'attribue pas de matricule (il se saisit sur la fiche).
  const givesMatricule = useSchool().data?.auto_matricule !== false;
  // Un identifiant par écran ouvert : renvoyé tel quel si l'envoi est recommencé.
  const [ids, setIds] = useState(newIds);
  const [general, setGeneral] = useState<string | null>(null);
  const [duplicates, setDuplicates] = useState<Duplicate[] | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const me = useCurrentMe();
  const canCollect = can(me, ["finance.collect_payment"]) && Boolean(device?.config?.fee_rules);
  const schema = useMemo(() => studentSchema(t, birthDateRequired(me)), [t, me]);
  const form: Form = useForm({ resolver: zodResolver(schema), defaultValues: EMPTY });
  const [deviceDuplicates, setDeviceDuplicates] = useState<{
    found: LocalEnrollment[];
    collect: boolean;
  } | null>(null);
  const [enrolledHere, setEnrolledHere] = useState<{ name: string; matricule: string } | null>(
    null,
  );

  const save = useMutation({
    mutationFn: async ({ values, allowDuplicate }: { values: Output; allowDuplicate: boolean }) => {
      const { student, enrollment } = ids;
      await call(
        api.POST("/api/students/", {
          body: { id: student, ...studentBody(values).body, allow_duplicate: allowDuplicate },
        }),
      );
      await call(
        api.POST("/api/enrollments/", {
          body: { id: enrollment, student, class_group: values.class_group },
        }),
      );
      if (photo) return uploadPhoto(student, photo);
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
      void navigate(`/students/${student.id}`, { state: { created } });
    },
    onError: (error) => {
      if (hasCode(error, "possible_duplicate")) {
        setDuplicates(duplicatesOf(error));
        return;
      }
      setGeneral(applyServerErrors(error, SERVER_FIELDS, form.setError, t));
    },
  });
  const submit = (allowDuplicate: boolean) =>
    form.handleSubmit((values) => {
      setGeneral(null);
      setDuplicates(null);
      save.mutate({ values, allowDuplicate });
    });

  // Sur l'appareil : élève, famille, inscription et frais dus dans la file, numéros provisoires.
  const saveHere = useMutation({
    mutationFn: async ({
      values,
      collect,
      distinct,
    }: {
      values: Output;
      collect: boolean;
      distinct: boolean;
    }) => {
      const known = device;
      const config = known?.config;
      if (!sync.db || !known || !config?.academic_year) throw new Error("No device state");
      const { student, enrollment, family } = ids;
      const birthDate = values.birth_date || null;
      const found = localDuplicates(known.enrollments, { ...values, birth_date: birthDate });
      if (found.length && !distinct) return { kind: "duplicates", found, collect } as const;
      const day = schoolDay(school.timezone);
      const charges = deviceCharges(config, values.class_group, enrollment, uuidv7);
      const newFamily = values.family_mode === "new";
      const payload: OfflineEnrollment = {
        ...studentBody(values).body,
        birth_date: birthDate,
        id: student,
        enrollment_id: enrollment,
        class_group: values.class_group,
        enrolled_on: day,
        charges: charges.map(({ charge, template }) => ({
          id: charge.id,
          installment_template: template,
        })),
        distinct_from: found.map((other) => other.student.id),
        ...(newFamily && { family_id: family }),
      };
      const familyId = newFamily ? family : values.family;
      const finance = config.fee_rules !== null;
      const local: Enrollment = {
        id: enrollment,
        academic_year: config.academic_year.id,
        class_group: values.class_group,
        status: "active",
        enrolled_on: day,
        left_on: null,
        student: {
          id: student,
          family: familyId,
          matricule: givesMatricule ? provisionalMatricule(student) : "",
          last_name: values.last_name,
          middle_name: values.middle_name,
          first_name: values.first_name,
          sex: values.sex as "M" | "F",
          birth_date: birthDate,
          family_code: newFamily
            ? provisionalFamilyCode(family)
            : (known.enrollments.find((item) => item.student.family === familyId)?.student
                .family_code ?? ""),
        },
        charges: finance ? charges.map(({ charge }) => charge) : null,
        payments: finance ? [] : null,
        credits: finance ? [] : null,
        credit_uses: finance ? [] : null,
      };
      await enrollOffline(sync.db, payload, local);
      return { kind: "enrolled", local, collect } as const;
    },
    onSuccess: (result) => {
      if (result.kind === "duplicates") {
        setDeviceDuplicates({ found: result.found, collect: result.collect });
        return;
      }
      const { local, collect } = result;
      const name = studentName(local.student);
      if (collect) {
        void navigate("/cash", { state: { collect: collectOf(local, groups) } });
        return;
      }
      setEnrolledHere({ name, matricule: local.student.matricule });
      setIds(newIds());
      form.reset(EMPTY);
      window.scrollTo({ top: 0 });
    },
    onError: (error) => setGeneral(errorMessage(error, t)),
  });
  const submitHere = (collect: boolean, distinct = false) =>
    form.handleSubmit((values) => {
      setGeneral(null);
      setEnrolledHere(null);
      setDeviceDuplicates(null);
      saveHere.mutate({ values, collect, distinct });
    });

  const groups: { id: string; name: string }[] =
    (offline ? device?.config?.class_groups : classes.data) ?? [];
  const noYear = offline ? device && !year : years.data && !year;
  const blocked = noYear || ((offline ? device : classes.data) && groups.length === 0);
  const pending = save.isPending || saveHere.isPending;

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
        subtitle={offline ? t("students.offline.subtitle") : undefined}
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/students">{t("common.cancel")}</Link>
            </Button>
            {/* Sans réseau, au guichet : « Inscrire et encaisser » d'abord (maquette). */}
            <Button
              type="submit"
              form="new-student"
              variant={offline && canCollect ? "outline" : undefined}
              disabled={pending || Boolean(blocked)}
            >
              {offline && canCollect ? t("students.offline.enrollOnly") : t("students.new.submit")}
            </Button>
            {offline && canCollect && (
              <Button
                type="button"
                disabled={pending || Boolean(blocked)}
                onClick={() => void submitHere(true)()}
              >
                {t("students.offline.enrollAndCollect")}
              </Button>
            )}
          </>
        }
      />
      {offline && (
        <Banner tone="warn" icon="wifioff">
          <span>
            <b>{t("common.offline")}.</b> {t("students.offline.provisional")}
          </span>
        </Banner>
      )}
      {enrolledHere && (
        <Banner tone="ok" role="status">
          {t("students.offline.enrolled", {
            name: enrolledHere.name,
            matricule: enrolledHere.matricule || t("common.none"),
          })}
        </Banner>
      )}
      {noYear && <Banner tone="warn">{t("students.new.noYear")}</Banner>}
      {year && groups.length === 0 && (offline ? device : classes.data) && (
        <Banner tone="warn">{t("students.new.noClasses")}</Banner>
      )}
      {general && <Banner tone="due">{general}</Banner>}
      {deviceDuplicates && (
        <DeviceDuplicates
          found={deviceDuplicates.found}
          groups={groups}
          canCollect={canCollect}
          onDistinct={() => void submitHere(deviceDuplicates.collect, true)()}
          onCollect={(other) =>
            void navigate("/cash", { state: { collect: collectOf(other, groups) } })
          }
        />
      )}
      {duplicates && (
        <Banner tone="warn" role="alert">
          <span className="flex flex-col items-start gap-2">
            {t("students.new.duplicate")}
            {duplicates.map((other) => (
              <Link key={other.id} to={`/students/${other.id}`} className="text-lake underline">
                {t("students.new.duplicateOpen", {
                  name: studentName(other),
                  matricule: other.matricule || t("common.none"),
                })}
              </Link>
            ))}
            <Button type="button" size="sm" variant="outline" onClick={() => void submit(true)()}>
              {t("students.new.duplicateConfirm")}
            </Button>
          </span>
        </Banner>
      )}
      <form
        id="new-student"
        noValidate
        onSubmit={offline ? submitHere(false) : submit(false)}
        className="flex max-w-[1040px] flex-col gap-5"
      >
        <IdentitySections form={form} />
        <Section title={t("students.new.schooling", { year: year?.name ?? "" })}>
          <div className="grid gap-3 min-[700px]:grid-cols-3">
            <ClassField
              form={form}
              groups={groups}
              help={(id) => {
                if (offline) return device && seenAtSync(device, id, t, i18n.language, school);
                const group = classes.data?.find((item) => item.id === id);
                if (!group) return undefined;
                return group.capacity === null
                  ? t("students.new.enrolledCount", { count: group.student_count })
                  : t("students.new.places", {
                      count: group.student_count,
                      capacity: group.capacity,
                    });
              }}
            />
            <TextField
              form={form}
              name="previous_school"
              label={t("students.new.previousSchool")}
            />
            {givesMatricule && (
              <Field
                id="student-matricule"
                label={t("students.new.matricule")}
                help={offline ? undefined : t("students.new.matriculeHelp")}
              >
                {(control) => (
                  <Input
                    {...control}
                    readOnly
                    value={
                      offline
                        ? t("students.offline.provisionalValue", {
                            value: provisionalMatricule(ids.student),
                          })
                        : t("students.new.matriculeValue")
                    }
                    className="text-ink-3"
                  />
                )}
              </Field>
            )}
            {offline && <ProvisionalFamilyCode form={form} family={ids.family} device={device} />}
          </div>
        </Section>
        {/* La photo s'envoie au serveur : sans réseau, elle s'ajoute sur la fiche ensuite. */}
        {!offline && <PhotoSection form={form} photo={photo} onPhoto={setPhoto} />}
        <FamilySection form={form} device={offline ? device : undefined} />
      </form>
    </>
  );
}

/** Inscrits dans la classe d'après l'appareil, et l'heure de sa dernière synchronisation. */
function seenAtSync(
  device: DeviceStudents,
  classGroup: string,
  t: TFunction,
  language: string,
  school: { timezone: string },
) {
  const count = device.enrollments.filter(
    (item) => item.class_group === classGroup && item.status === "active",
  ).length;
  return device.lastSyncAt
    ? t("students.offline.seenAtSync", {
        count,
        time: formatTime(device.lastSyncAt, language, school.timezone),
      })
    : t("students.new.enrolledCount", { count });
}

/** Élève à encaisser, passé à la caisse de l'appareil (`CashDesk`). */
function collectOf(enrollment: Enrollment, groups: { id: string; name: string }[]): Chosen {
  return {
    enrollment: enrollment.id,
    name: studentName(enrollment.student),
    matricule: enrollment.student.matricule,
    classGroup: groups.find((group) => group.id === enrollment.class_group)?.name ?? "",
    guardian: null,
  };
}

/** Même nom, prénom et date de naissance qu'un élève de l'appareil : jamais fusionné ; « Ce sont
 *  deux élèves » inscrit et le dit au serveur (pas de signalement), « C'est le même » encaisse. */
function DeviceDuplicates({
  found,
  groups,
  canCollect,
  onDistinct,
  onCollect,
}: {
  found: LocalEnrollment[];
  groups: { id: string; name: string }[];
  canCollect: boolean;
  onDistinct: () => void;
  onCollect: (other: LocalEnrollment) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  return (
    <Banner tone="warn" role="alert">
      <span className="flex flex-col items-start gap-2">
        <span>
          <b>{t("students.offline.duplicateTitle")}</b> {t("students.offline.duplicateHelp")}
        </span>
        {found.map((other) => (
          <span key={other.id} className="flex flex-wrap items-center gap-2">
            {t("students.offline.duplicateOne", {
              name: studentName(other.student),
              born: other.student.birth_date
                ? formatDate(other.student.birth_date, i18n.language, school.timezone)
                : "",
              detail: [
                other.student.matricule,
                groups.find((group) => group.id === other.class_group)?.name,
              ]
                .filter(Boolean)
                .join(", "),
            })}
            {canCollect && (
              <Button type="button" size="sm" variant="ghost" onClick={() => onCollect(other)}>
                {t("students.offline.sameCollect")}
              </Button>
            )}
          </span>
        ))}
        <Button type="button" size="sm" variant="outline" onClick={onDistinct}>
          {t("students.offline.distinct")}
        </Button>
      </span>
    </Banner>
  );
}

/** Code famille : provisoire pour une nouvelle famille, celui de la famille choisie sinon. */
function ProvisionalFamilyCode({
  form,
  family,
  device,
}: {
  form: Form;
  family: string;
  device?: DeviceStudents;
}) {
  const { t } = useTranslation();
  const [mode, chosen] = useWatch({ control: form.control, name: ["family_mode", "family"] });
  const code =
    mode === "new"
      ? t("students.offline.provisionalValue", { value: provisionalFamilyCode(family) })
      : (device?.enrollments.find((item) => item.student.family === chosen)?.student.family_code ??
        "");
  return (
    <Field id="student-family-code" label={t("students.offline.familyCode")}>
      {(control) => <Input {...control} readOnly value={code} className="text-ink-3" />}
    </Field>
  );
}

/** Famille existante sans réseau : cherchée parmi les élèves de l'appareil (nom d'un enfant ou
 *  code famille). */
function DeviceFamily({ form, device }: { form: Form; device: DeviceStudents }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const chosen = useWatch({ control: form.control, name: "family" });
  const classes = new Map(device.config?.class_groups.map((item) => [item.id, item.name]));
  const all = searchLocalFamilies(device.enrollments, search.trim(), 6);
  const selected = chosen
    ? (all.find((family) => family.id === chosen) ??
      searchLocalFamilies(
        device.enrollments.filter((item) => item.student.family === chosen),
        device.enrollments.find((item) => item.student.family === chosen)?.student.family_code ??
          "",
        1,
      )[0])
    : undefined;
  const results = all.filter((family) => family.id !== chosen).slice(0, 5);
  const card = (family: (typeof all)[number], isChosen: boolean) => (
    <div
      key={family.id}
      className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line p-3.5"
    >
      <div className="text-md">
        <b>{t("students.new.familyCode", { code: family.code })}</b>
        <br />
        <span className="text-sm text-ink-3">
          {t("students.new.children", {
            count: family.children.length,
            names: family.children
              .map((child) =>
                [studentName(child.student), classes.get(child.class_group)]
                  .filter(Boolean)
                  .join(", "),
              )
              .join(" ; "),
          })}
        </span>
      </div>
      {isChosen ? (
        <span className="inline-flex items-center gap-1.5 rounded-field bg-lake px-3 py-1.5 text-sm font-bold text-white">
          <Icon name="check" size={14} />
          {t("students.new.chosen")}
        </span>
      ) : (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => form.setValue("family", family.id, { shouldValidate: true })}
        >
          {t("students.new.choose")}
        </Button>
      )}
    </div>
  );
  return (
    <div className="flex flex-col gap-3">
      <Field
        id="family-search"
        label={t("students.offline.familySearch")}
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
      {selected && card(selected, true)}
      {results.map((family) => card(family, false))}
      {search.trim().length >= 2 && all.length === 0 && (
        <p className="text-sm text-ink-3">{t("students.new.familyNone")}</p>
      )}
    </div>
  );
}

function duplicatesOf(error: ApiError): Duplicate[] {
  const found = error.body.duplicates;
  return Array.isArray(found) ? (found as Duplicate[]) : [];
}

function ClassField({
  form,
  groups,
  help,
}: {
  form: Form;
  groups: { id: string; name: string }[];
  help: (id: string) => string | undefined;
}) {
  const { t } = useTranslation();
  const value = useWatch({ control: form.control, name: "class_group" });
  return (
    <Field
      id="student-class"
      label={t("students.new.class")}
      required
      error={form.formState.errors.class_group?.message}
      help={value ? help(value) : undefined}
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

function FamilySection({ form, device }: { form: Form; device?: DeviceStudents }) {
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
      {mode === "new" ? (
        <NewFamily form={form} />
      ) : device ? (
        <DeviceFamily form={form} device={device} />
      ) : (
        <ExistingFamily form={form} />
      )}
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

export function FamilyCard({
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
      <div className="text-md">
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
          <legend className="mb-2 text-sm font-bold text-ink-2">
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
