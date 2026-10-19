// Équipe de la plateforme (EQ.2, maquette `console/equipe`) : membres, rôles, double
// authentification, dernière connexion ; inviter (mot de passe provisoire montré une seule fois),
// changer les rôles, retirer. Propriétaire seulement (`platform.team.manage`, vérifié par le
// serveur) ; chaque changement va au journal de la plateforme sous le nom de son auteur.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import {
  applyServerErrors,
  errorMessage,
  formatDateTime,
  formatPhone,
  useTranslation,
} from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  Tag,
  cn,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { keys, useMe } from "../../lib/queries";
import { ALL_RIGHTS, type Right } from "../../lib/rights";
import { fullName } from "../accounts/AccountsPage";

type Member = Schemas["TeamMember"];
type Role = Schemas["PlatformRoleEnum"];

// Ordre des cases : « Propriétaire », qui donne tout, en dernier.
const ROLES: Role[] = ["technical", "support", "commercial", "communication", "finance", "owner"];
const FIELDS = ["last_name", "middle_name", "first_name", "phone", "roles"] as const;

type InviteValues = {
  last_name: string;
  middle_name: string;
  first_name: string;
  phone: string;
  roles: Role[];
};
const EMPTY: InviteValues = {
  last_name: "",
  middle_name: "",
  first_name: "",
  phone: "",
  roles: [],
};

/** Libellé d'un droit : `platform.schools.view` → `console.team.rights.schools_view`. */
const rightKey = (code: string) =>
  `console.team.rights.${code.replace(/^platform\./, "").replace(".", "_")}` as "console.team.rights.schools_view";

function RoleChoice({
  value,
  onChange,
  error,
}: {
  value: Role[];
  onChange: (roles: Role[]) => void;
  error?: string;
}) {
  const { t } = useTranslation();
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 text-sm font-bold">{t("console.team.fields.roles")}</legend>
      {ROLES.map((role) => {
        const on = value.includes(role);
        return (
          <CheckboxField
            key={role}
            id={`role-${role}`}
            className={cn(
              "rounded-md border px-3 py-2.5",
              on ? "border-lake bg-lake-50" : "border-line",
            )}
            checked={on}
            onCheckedChange={(checked) =>
              onChange(checked === true ? [...value, role] : value.filter((r) => r !== role))
            }
            label={
              <>
                <b>{t(`console.team.roleNames.${role}`)}</b>
                <span className="block text-sm text-ink-3">
                  {t(`console.team.roleHints.${role}`)}
                </span>
              </>
            }
          />
        );
      })}
      {error && (
        <p role="alert" className="text-sm text-due">
          {error}
        </p>
      )}
    </fieldset>
  );
}

function InviteDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const required = t("fieldErrors.required");
  const form = useForm<InviteValues>({
    resolver: zodResolver(
      z.object({
        last_name: z.string().trim().min(1, required),
        middle_name: z.string().trim(),
        first_name: z.string().trim(),
        phone: z.string().trim().min(1, required),
        roles: z.array(z.custom<Role>()).min(1, t("console.team.noRole")),
      }),
    ),
    defaultValues: EMPTY,
  });
  const [general, setGeneral] = useState<string | null>(null);
  const [invited, setInvited] = useState<{ name: string; password: string } | null>(null);
  const invite = useMutation({
    mutationFn: (body: InviteValues) => call(api.POST("/api/console/team/", { body })),
    onSuccess: (data) => {
      setInvited({ name: fullName(data.member), password: data.temporary_password });
      void queryClient.invalidateQueries({ queryKey: keys.team });
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });
  const errors = form.formState.errors;
  const roles = useWatch({ control: form.control, name: "roles" });

  if (invited) {
    return (
      <DialogRoot open onOpenChange={onClose}>
        <DialogContent
          title={t("console.team.invitedTitle", { name: invited.name })}
          footer={
            <DialogClose asChild>
              <Button>{t("console.team.invitedDone")}</Button>
            </DialogClose>
          }
        >
          <div className="flex flex-col gap-3">
            <p className="flex flex-wrap items-center gap-2">
              {t("console.team.invitedPassword")}
              <code className="rounded-md border border-line bg-white px-2.5 py-1 font-mono text-lg">
                {invited.password}
              </code>
            </p>
            <p className="text-sm text-ink-3">{t("console.team.invitedHelp")}</p>
          </div>
        </DialogContent>
      </DialogRoot>
    );
  }
  const field = (name: Exclude<(typeof FIELDS)[number], "roles">, help?: string) => (
    <Field
      id={`invite-${name}`}
      label={t(`console.team.fields.${name}`)}
      help={help}
      error={errors[name]?.message}
    >
      {(control) => (
        <Input
          {...control}
          autoComplete="off"
          inputMode={name === "phone" ? "tel" : undefined}
          maxLength={name === "phone" ? 20 : 100}
          {...form.register(name)}
        />
      )}
    </Field>
  );
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.team.invite")}
      confirmLabel={t("console.team.inviteSubmit")}
      cancelLabel={t("common.cancel")}
      onConfirm={() =>
        void form.handleSubmit((values) => {
          setGeneral(null);
          invite.mutate(values);
        })()
      }
      pending={invite.isPending}
    >
      <div className="flex flex-col gap-4">
        {general && <Banner tone="due">{general}</Banner>}
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          {field("last_name")}
          {field("middle_name")}
          {field("first_name")}
          {field("phone", t("console.team.phoneHelp"))}
        </div>
        <RoleChoice
          value={roles}
          onChange={(next) =>
            form.setValue("roles", next, { shouldValidate: form.formState.isSubmitted })
          }
          error={errors.roles?.message}
        />
      </div>
    </ConfirmDialog>
  );
}

function RolesDialog({ member, onClose }: { member: Member; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [roles, setRoles] = useState<Role[]>(member.roles);
  const [missing, setMissing] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/console/team/{id}/", {
          params: { path: { id: member.id } },
          body: { roles },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.team });
      // Ses propres rôles : le menu change tout de suite.
      void queryClient.invalidateQueries({ queryKey: keys.me });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.team.rolesOf", { name: fullName(member) })}
      confirmLabel={t("console.team.save")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => (roles.length ? save.mutate() : setMissing(true))}
      pending={save.isPending}
    >
      <div className="flex flex-col gap-4">
        <RoleChoice
          value={roles}
          onChange={(next) => {
            setRoles(next);
            setMissing(false);
          }}
          error={missing ? t("console.team.noRole") : undefined}
        />
        {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

function RemoveDialog({ member, onClose }: { member: Member; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: () =>
      call(api.POST("/api/console/team/{id}/remove/", { params: { path: { id: member.id } } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.team });
      onClose();
    },
  });
  return (
    <ConfirmDialog
      open
      onOpenChange={onClose}
      title={t("console.team.removeTitle", { name: fullName(member) })}
      confirmLabel={t("console.team.remove")}
      cancelLabel={t("common.cancel")}
      onConfirm={() => remove.mutate()}
      pending={remove.isPending}
      destructive
    >
      <div className="flex flex-col gap-4">
        <p>{t("console.team.removeText")}</p>
        {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
      </div>
    </ConfirmDialog>
  );
}

function RolesCard() {
  const { t } = useTranslation();
  const roles = useQuery({
    queryKey: [...keys.team, "roles"],
    queryFn: () => call(api.GET("/api/console/team/roles/")),
    staleTime: Infinity,
  });
  if (!roles.data) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.team.rolesTitle")}</CardTitle>
      </CardHeader>
      <ul>
        {roles.data.map((role) => (
          <li
            key={role.code}
            className="flex flex-wrap justify-between gap-x-4 gap-y-1 border-t border-line px-5 py-2.5 first:border-t-0"
          >
            <b>{t(`console.team.roleNames.${role.code}`)}</b>
            <span className="text-sm text-ink-3">
              {role.code === "owner"
                ? t("console.team.allRights")
                : [...role.permissions]
                    .sort((a, b) => ALL_RIGHTS.indexOf(a as Right) - ALL_RIGHTS.indexOf(b as Right))
                    .map((code) => t(rightKey(code)))
                    .join(" · ")}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function TeamPage() {
  const { t, i18n } = useTranslation();
  const { data: me } = useMe();
  const [inviting, setInviting] = useState(false);
  const [editing, setEditing] = useState<Member | null>(null);
  const [removing, setRemoving] = useState<Member | null>(null);
  const team = useQuery({
    queryKey: keys.team,
    queryFn: () => call(api.GET("/api/console/team/")),
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <>
      <PageHeader
        title={t("console.team.title")}
        subtitle={t("console.team.subtitle")}
        actions={<Button onClick={() => setInviting(true)}>{t("console.team.invite")}</Button>}
      />
      {team.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : team.isError ? (
        <>
          <Banner tone="due">{errorMessage(team.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void team.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          <Table>
            <thead>
              <tr>
                <th>{t("console.team.member")}</th>
                <th>{t("console.team.roles")}</th>
                <th>{t("console.team.totp")}</th>
                <th>{t("console.team.lastLogin")}</th>
                <th className="relative">
                  <span className="sr-only">{t("console.team.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {team.data.results.map((member) => {
                const self = member.id === me?.id;
                return (
                  <tr key={member.id}>
                    <td>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <b>{fullName(member)}</b>
                        {self && <StatusPill tone="info">{t("console.team.you")}</StatusPill>}
                      </div>
                      <span className="text-sm text-ink-3 tabular-nums">
                        {formatPhone(member.phone)}
                      </span>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {member.roles.map((role) => (
                          <Tag key={role}>{t(`console.team.roleNames.${role}`)}</Tag>
                        ))}
                      </div>
                    </td>
                    <td>
                      <StatusPill tone={member.totp_enabled ? "ok" : "warn"}>
                        {t(member.totp_enabled ? "console.team.totpOn" : "console.team.totpOff")}
                      </StatusPill>
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {member.must_change_password ? (
                        <StatusPill tone="warn">{t("console.team.pending")}</StatusPill>
                      ) : member.last_login ? (
                        formatDateTime(member.last_login, i18n.language, timeZone)
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(member)}>
                          {t("console.team.roles")}
                        </Button>
                        {/* Pas de « Retirer » sur sa propre ligne : un autre propriétaire le fait. */}
                        {!self && (
                          <Button
                            variant="destructive-outline"
                            size="sm"
                            onClick={() => setRemoving(member)}
                          >
                            {t("console.team.remove")}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>
      )}
      <RolesCard />
      {inviting && <InviteDialog onClose={() => setInviting(false)} />}
      {editing && <RolesDialog member={editing} onClose={() => setEditing(null)} />}
      {removing && <RemoveDialog member={removing} onClose={() => setRemoving(null)} />}
    </>
  );
}
