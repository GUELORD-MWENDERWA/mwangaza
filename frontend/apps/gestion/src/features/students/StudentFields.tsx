// Champs communs à « Inscrire un nouvel élève » et « Modifier l'élève » (M9) : identité, adresse,
// école de provenance, photo et consentement du parent (la photo peut servir sur la carte et le
// portail seulement avec lui : H3).
import { type TFunction, useTranslation } from "@mwangaza/i18n";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Icon,
  Input,
  Segmented,
} from "@mwangaza/ui";
import { type ReactNode, useEffect, useMemo } from "react";
import { Controller, type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { shrinkPhoto } from "./photo";

export function identityShape(t: TFunction) {
  const text = (max: number) => z.string().trim().max(max);
  return {
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
    photo_consent: z.boolean(),
  };
}

export type IdentityValues = {
  last_name: string;
  middle_name: string;
  first_name: string;
  sex: string;
  birth_date: string;
  birth_place: string;
  nationality: string;
  origin_province: string;
  origin_territory: string;
  address: { commune: string; quartier: string; avenue: string; number: string };
  previous_school: string;
  photo_consent: boolean;
};

export const IDENTITY_EMPTY: IdentityValues = {
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
  photo_consent: false,
};

/** Champs où placer un refus du serveur. */
export const IDENTITY_PATHS = [
  ...Object.keys(IDENTITY_EMPTY),
  ...Object.keys(IDENTITY_EMPTY.address).map((name) => `address.${name}`),
];

type IdentityForm = UseFormReturn<IdentityValues>;

export function fieldError(errors: object, name: string): string | undefined {
  const found = name
    .split(".")
    .reduce<unknown>(
      (node, key) => (node as Record<string, unknown> | undefined)?.[key],
      errors,
    ) as { message?: string } | undefined;
  return found?.message;
}

export function Section({
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

export function TextField<T extends FieldValues>({
  form,
  name,
  label,
  required = false,
  type = "text",
  help,
}: {
  form: UseFormReturn<T, unknown, unknown>;
  name: Path<T>;
  label: string;
  required?: boolean;
  type?: string;
  help?: string;
}) {
  const loose = form as unknown as UseFormReturn<FieldValues>;
  return (
    <Field
      id={`student-${name}`}
      label={label}
      required={required}
      help={help}
      error={fieldError(loose.formState.errors, name)}
    >
      {(control) => <Input {...control} type={type} {...loose.register(name)} />}
    </Field>
  );
}

/** Cartes « Identité » et « Adresse ». */
export function IdentitySections<T extends IdentityValues>({
  form,
}: {
  form: UseFormReturn<T, unknown, unknown>;
}) {
  const { t } = useTranslation();
  const identity = form as unknown as IdentityForm;
  const sexError = identity.formState.errors.sex?.message;
  const field = (name: Path<IdentityValues>, label: string, required = false, type = "text") => (
    <TextField form={identity} name={name} label={label} required={required} type={type} />
  );
  return (
    <>
      <Section title={t("students.new.identity")}>
        <div className="grid gap-3 min-[700px]:grid-cols-3">
          {field("last_name", t("students.new.lastName"), true)}
          {field("middle_name", t("students.new.middleName"), true)}
          {field("first_name", t("students.new.firstName"))}
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-bold text-ink-2">
              {t("students.new.sex")}
              <span className="text-due" aria-hidden="true">
                {" "}
                *
              </span>
            </span>
            <Controller
              control={identity.control}
              name="sex"
              render={({ field: sex }) => (
                <Segmented
                  label={t("students.new.sex")}
                  value={sex.value as "M" | "F"}
                  onValueChange={sex.onChange}
                  options={[
                    { value: "M", label: t("students.new.male") },
                    { value: "F", label: t("students.new.female") },
                  ]}
                  className="self-start"
                />
              )}
            />
            {sexError && (
              <p role="alert" className="text-xs text-due">
                {sexError}
              </p>
            )}
          </div>
          {field("birth_date", t("students.new.birthDate"), true, "date")}
          {field("birth_place", t("students.new.birthPlace"))}
          {field("nationality", t("students.new.nationality"))}
          {field("origin_province", t("students.new.originProvince"))}
          {field("origin_territory", t("students.new.originTerritory"))}
        </div>
      </Section>
      <Section title={t("students.new.address")}>
        <div className="grid gap-3 min-[700px]:grid-cols-4">
          {field("address.commune", t("students.new.commune"))}
          {field("address.quartier", t("students.new.quartier"))}
          {field("address.avenue", t("students.new.avenue"))}
          {field("address.number", t("students.new.number"))}
        </div>
      </Section>
    </>
  );
}

/** Carte « Photo » : l'image choisie (si `onPhoto`) et le consentement du parent. */
export function PhotoSection<T extends IdentityValues>({
  form,
  photo,
  onPhoto,
}: {
  form: UseFormReturn<T, unknown, unknown>;
  photo?: File | null;
  onPhoto?: (photo: File) => void;
}) {
  const { t } = useTranslation();
  const identity = form as unknown as IdentityForm;
  return (
    <Section title={t("students.photo.title")}>
      <div className="flex flex-wrap items-center gap-4">
        {onPhoto && <PhotoPicker photo={photo ?? null} onPhoto={onPhoto} />}
        <Controller
          control={identity.control}
          name="photo_consent"
          render={({ field }) => (
            <CheckboxField
              id="student-photo-consent"
              label={t("students.photo.consent")}
              checked={field.value}
              onCheckedChange={(checked) => field.onChange(checked === true)}
              className="max-w-[420px]"
            />
          )}
        />
      </div>
    </Section>
  );
}

function PhotoPicker({ photo, onPhoto }: { photo: File | null; onPhoto: (photo: File) => void }) {
  const { t } = useTranslation();
  const preview = useObjectUrl(photo);
  return (
    <label className="grid h-[180px] w-[150px] cursor-pointer place-items-center overflow-hidden rounded-card border-2 border-dashed border-line text-center text-sm text-ink-3 focus-within:outline-2 focus-within:outline-lake">
      {preview ? (
        <img src={preview} alt={t("students.photo.chosen")} className="size-full object-cover" />
      ) : (
        <span className="flex flex-col items-center gap-1.5 px-3">
          <Icon name="user" size={32} />
          {t("students.photo.pick")}
        </span>
      )}
      <input
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void shrinkPhoto(file).then(onPhoto);
        }}
      />
    </label>
  );
}

/** Adresse locale d'un fichier choisi, libérée quand il change. */
export function useObjectUrl(file: File | null): string | null {
  const url = useMemo(
    () => (file && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null),
    [file],
  );
  useEffect(() => () => (url ? URL.revokeObjectURL(url) : undefined), [url]);
  return url;
}
