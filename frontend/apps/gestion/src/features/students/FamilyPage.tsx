// Fiche famille (M10, D4) : code famille, enfants de cette école seulement (la famille appartient à
// l'école, Q10), tuteurs et contacts modifiables d'un seul envoi (un seul tuteur principal, son
// téléphone obligatoire). Modifier : `students.edit`. Réimprimer le code : 2.4 ; nouveau code et
// état du portail : 4.4.1 ; « Suspendre l'accès » : 4.4.2 ; « Échu non payé » : 2.7 ;
// lettre et message d'invitation au portail : 4.9.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call } from "@mwangaza/api";
import { formatDate, type TFunction, useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  Code,
  ConfirmDialog,
  Field,
  Icon,
  Input,
  Select,
  Skeleton,
  Table,
  Tag,
  initials,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Controller, type Path, useFieldArray, useForm } from "react-hook-form";
import { Link, useParams } from "react-router";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { GuardianTable } from "./StudentFamilyTab";
import { type Family, familyName, RELATIONSHIPS, type Relationship, useFamily } from "./data";
import { InvitationActions } from "./InvitationActions";

const MAX_GUARDIANS = 10;

export function FamilyPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const me = useCurrentMe();
  const family = useFamily(id);
  const [editing, setEditing] = useState(false);
  if (family.error) return <LoadError error={family.error} onRetry={() => void family.refetch()} />;
  if (!family.data) return <Skeleton label={t("common.loading")} />;
  const data = family.data;
  const name = familyName(data);
  return (
    <>
      <p className="text-sm text-ink-3">
        <Link to="/students" className="text-lake underline">
          {t("students.list.title")}
        </Link>{" "}
        / {t("students.family.crumb")}
      </p>
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4">
          <span className="grid size-16 place-items-center rounded-full bg-lamp-soft text-ink">
            <Icon name="users" size={28} />
          </span>
          <div className="min-w-[200px] flex-1">
            <h1 className="text-2xl font-bold">{t("students.family.title", { name })}</h1>
            <div className="mt-1.5 flex flex-wrap gap-2 text-sm">
              <Tag>{t("students.family.children", { count: data.students.length })}</Tag>
              <Tag>{t("students.family.contacts", { count: data.guardians.length })}</Tag>
            </div>
          </div>
          <div className="flex flex-col items-center gap-1.5">
            <div className="rounded-card border-2 border-lamp px-4 py-2.5 text-center">
              <div className="text-xs text-ink-3">{t("students.card.familyCode")}</div>
              <Code className="text-xl">{data.code}</Code>
            </div>
            <PortalStatus family={data} />
            {can(me, ["students.edit"]) && data.portal_status === "pending" && (
              <span className="flex flex-wrap justify-center gap-1.5">
                <InvitationActions familyId={data.id} name={name} long />
              </span>
            )}
            {can(me, ["students.edit"]) && <NewCodeButton family={data} />}
            {can(me, ["students.edit"]) && <PortalAccessButton family={data} />}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("students.family.childrenTitle")}</CardTitle>
        </CardHeader>
        <Table>
          <thead>
            <tr>
              <th>{t("students.family.student")}</th>
              <th>{t("students.family.class")}</th>
            </tr>
          </thead>
          <tbody>
            {data.students.map((child) => (
              <tr key={child.id}>
                <td>
                  <span className="flex items-center gap-2.5">
                    <Avatar
                      text={initials(child.middle_name || child.first_name, child.last_name)}
                      className="size-8 text-xs"
                    />
                    <span className="flex flex-col">
                      <Link
                        to={`/students/${child.id}`}
                        className="font-bold text-ink hover:text-lake hover:underline"
                      >
                        {studentName(child)}
                      </Link>
                      <small className="text-ink-3 tabular-nums">
                        {child.matricule || t("common.none")}
                      </small>
                    </span>
                  </span>
                </td>
                <td>{child.class_group_name || t("students.list.notEnrolled")}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <Card>
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
          <CardTitle>{t("students.family.contactsTitle")}</CardTitle>
          {can(me, ["students.edit"]) && !editing && (
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Icon name="edit" size={14} />
              {t("students.family.editContacts")}
            </Button>
          )}
        </CardHeader>
        {editing ? (
          <GuardiansForm family={data} onDone={() => setEditing(false)} />
        ) : (
          <GuardianTable guardians={data.guardians} withEmail />
        )}
      </Card>
    </>
  );
}

/** Portail activé ou pas ; date limite d'un nouveau code pas encore utilisé. */
function PortalStatus({ family }: { family: Family }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const date = (iso: string) => formatDate(iso, i18n.language, school.timezone);
  return (
    <small className="max-w-[220px] text-center text-ink-3">
      {family.activated_at
        ? t("students.family.portalActivated", { date: date(family.activated_at) })
        : t("students.family.portalNotActivated")}
      {family.portal_suspended_at && (
        <>
          <br />
          {t("students.family.portalSuspended", { date: date(family.portal_suspended_at) })}
        </>
      )}
      {family.code_expires_at && (
        <>
          <br />
          {t("students.family.codeValidUntil", { date: date(family.code_expires_at) })}
        </>
      )}
    </small>
  );
}

/** « Nouveau code » (M10) : l'ancien ne marche plus ; le nouveau sert une fois, 30 jours
 *  (activation ou mot de passe oublié du portail). */
function NewCodeButton({ family }: { family: Family }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const renew = useMutation({
    mutationFn: () =>
      call(api.POST("/api/families/{id}/new-code/", { params: { path: { id: family.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.families });
      setOpen(false);
    },
  });
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Icon name="refresh" size={14} />
        {t("students.family.newCode")}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t("students.family.newCodeTitle")}
        confirmLabel={t("students.family.newCode")}
        cancelLabel={t("common.cancel")}
        pending={renew.isPending}
        onConfirm={() => renew.mutate()}
      >
        <p>{t("students.family.newCodeHelp")}</p>
        {renew.isError && <Banner tone="due">{errorMessage(renew.error, t)}</Banner>}
      </ConfirmDialog>
    </>
  );
}

/** « Suspendre l'accès » / « Rétablir l'accès » (M10) : le portail ne montre plus rien de cette
 *  famille, sans supprimer le compte du parent. */
function PortalAccessButton({ family }: { family: Family }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const suspended = family.portal_suspended_at !== null;
  const change = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/families/{id}/portal-access/", {
          params: { path: { id: family.id } },
          body: { suspended: !suspended },
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.families });
      setOpen(false);
    },
  });
  const label = t(suspended ? "students.family.restoreAccess" : "students.family.suspendAccess");
  return (
    <>
      <Button
        size="sm"
        variant={suspended ? "outline" : "destructive-outline"}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t(suspended ? "students.family.restoreTitle" : "students.family.suspendTitle")}
        confirmLabel={label}
        cancelLabel={t("common.cancel")}
        pending={change.isPending}
        onConfirm={() => change.mutate()}
      >
        <p>{t(suspended ? "students.family.restoreHelp" : "students.family.suspendHelp")}</p>
        {change.isError && <Banner tone="due">{errorMessage(change.error, t)}</Banner>}
      </ConfirmDialog>
    </>
  );
}

function guardiansSchema(t: TFunction) {
  const text = (max: number) => z.string().trim().max(max);
  return z
    .object({
      primary: z.number(),
      guardians: z.array(
        z.object({
          id: z.string().optional(),
          full_name: text(150).min(1, t("students.validation.guardianNameRequired")),
          relationship: z.string().min(1, t("students.validation.relationshipRequired")),
          phone: text(20),
          email: z.union([z.literal(""), z.email(t("validation.emailInvalid"))]),
          is_emergency_contact: z.boolean(),
        }),
      ),
    })
    .superRefine((values, context) => {
      if (!values.guardians[values.primary]?.phone) {
        context.addIssue({
          code: "custom",
          path: ["guardians", values.primary, "phone"],
          message: t("students.validation.phoneRequired"),
        });
      }
    });
}

type Schema = ReturnType<typeof guardiansSchema>;
type Values = z.input<Schema>;
const EMPTY_GUARDIAN = {
  full_name: "",
  relationship: "",
  phone: "",
  email: "",
  is_emergency_contact: false,
};

function GuardiansForm({ family, onDone }: { family: Family; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(() => guardiansSchema(t), [t]);
  const form = useForm<Values, unknown, z.output<Schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      primary: Math.max(
        0,
        family.guardians.findIndex((guardian) => guardian.is_primary),
      ),
      guardians: family.guardians.map((guardian) => ({
        id: guardian.id,
        full_name: guardian.full_name,
        relationship: guardian.relationship,
        phone: guardian.phone ?? "",
        email: guardian.email,
        is_emergency_contact: guardian.is_emergency_contact,
      })),
    },
  });
  const rows = useFieldArray({ control: form.control, name: "guardians" });
  const errors = form.formState.errors.guardians;
  const save = useMutation({
    mutationFn: ({ primary, guardians }: z.output<Schema>) =>
      call(
        api.PATCH("/api/families/{id}/", {
          params: { path: { id: family.id } },
          body: {
            guardians: guardians.map((guardian, index) => ({
              ...guardian,
              relationship: guardian.relationship as Relationship,
              is_primary: index === primary,
            })),
          },
        }),
      ),
    onSuccess: async () => {
      await Promise.all(
        [keys.families, keys.students].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      );
      onDone();
    },
    onError: (error) => {
      const fields = Array.from({ length: MAX_GUARDIANS }, (_, index) =>
        (["full_name", "relationship", "phone", "email"] as const).map(
          (name) => `guardians.${index}.${name}` as Path<Values>,
        ),
      ).flat();
      setGeneral(applyServerErrors(error, fields, form.setError, t));
    },
  });
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        save.mutate(values);
      })}
    >
      <CardContent className="flex flex-col gap-4">
        {general && (
          <p role="alert" className="text-sm text-due">
            {general}
          </p>
        )}
        {rows.fields.map((row, index) => (
          <fieldset
            key={row.id}
            className="grid gap-3 border-b border-line-soft pb-4 min-[700px]:grid-cols-4"
          >
            <legend className="sr-only">{t("students.family.columns.contact")}</legend>
            <Field
              id={`guardian-${index}-name`}
              label={t("students.new.fullName")}
              required
              error={errors?.[index]?.full_name?.message}
            >
              {(control) => (
                <Input {...control} {...form.register(`guardians.${index}.full_name`)} />
              )}
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
              error={errors?.[index]?.phone?.message}
            >
              {(control) => (
                <Input
                  {...control}
                  inputMode="tel"
                  {...form.register(`guardians.${index}.phone`)}
                />
              )}
            </Field>
            <Field
              id={`guardian-${index}-email`}
              label={t("students.family.columns.email")}
              error={errors?.[index]?.email?.message}
            >
              {(control) => (
                <Input {...control} type="email" {...form.register(`guardians.${index}.email`)} />
              )}
            </Field>
            <div className="flex flex-wrap items-center gap-4 text-sm min-[700px]:col-span-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  value={index}
                  {...form.register("primary", { valueAsNumber: true })}
                />
                {t("students.family.primaryField")}
              </label>
              <Controller
                control={form.control}
                name={`guardians.${index}.is_emergency_contact`}
                render={({ field }) => (
                  <label className="flex items-center gap-2">
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => field.onChange(checked === true)}
                    />
                    {t("students.family.emergencyField")}
                  </label>
                )}
              />
              {rows.fields.length > 1 && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="ml-auto"
                  onClick={() => {
                    rows.remove(index);
                    const primary = form.getValues("primary");
                    if (primary >= index && primary > 0) form.setValue("primary", primary - 1);
                  }}
                >
                  <Icon name="x" size={14} />
                  {t("students.new.removeContact")}
                </Button>
              )}
            </div>
          </fieldset>
        ))}
      </CardContent>
      <CardFooter>
        {rows.fields.length < MAX_GUARDIANS ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => rows.append(EMPTY_GUARDIAN)}
          >
            <Icon name="plus" size={14} />
            {t("students.new.addContact")}
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onDone}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={save.isPending}>
            {t("students.family.saveContacts")}
          </Button>
        </div>
      </CardFooter>
    </form>
  );
}
