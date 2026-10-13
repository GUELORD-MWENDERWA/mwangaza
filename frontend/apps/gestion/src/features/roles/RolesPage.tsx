// Rôles et permissions (B1-B2) : rôles prédéfinis (renommables, permissions modifiables, jamais
// supprimés) et rôles créés par l'école. Droit `roles.manage`. La double authentification n'est
// pas un réglage : elle est exigée dès qu'un droit touche à l'argent, aux réglages, aux comptes ou
// au journal (`04` § 8), et l'écran le montre.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CheckboxField,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
  cn,
  initials,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { fullName } from "../../lib/people";
import type { Permission } from "../../lib/permissions";
import { keys, useRoles } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";

type Role = Schemas["Role"];

const GROUPS: { key: "students" | "finance" | "administration"; permissions: Permission[] }[] = [
  { key: "students", permissions: ["students.view", "students.edit", "students.import"] },
  {
    key: "finance",
    permissions: [
      "finance.collect_payment",
      "finance.request_cancellation",
      "finance.approve_cancellation",
      "finance.close_register",
      "finance.configure_fees",
      "finance.set_exchange_rate",
      "finance.grant_discount",
      "finance.view_reports",
    ],
  },
  {
    key: "administration",
    permissions: [
      "school.configure",
      "classes.manage",
      "roles.manage",
      "announcements.publish",
      "audit.view",
    ],
  },
];

/** Même liste que `TOTP_PERMISSIONS` du serveur (`backend/apps/accounts/roles.py`). */
export function requiresTotp(permissions: readonly string[]) {
  return permissions.some(
    (code) =>
      code === "school.configure" ||
      code === "roles.manage" ||
      code === "audit.view" ||
      code.startsWith("finance."),
  );
}

export function RolesPage() {
  const { t } = useTranslation();
  const roles = useRoles();
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (roles.isPending) return <Skeleton label={t("common.loading")} />;
  if (roles.isError) return <LoadError error={roles.error} onRetry={() => void roles.refetch()} />;
  const current = roles.data.find((role) => role.id === selected) ?? roles.data[0];

  return (
    <>
      <PageHeader
        title={t("rolesPage.title")}
        subtitle={t("rolesPage.subtitle")}
        actions={
          <Button size="lg" onClick={() => setCreating(true)}>
            <Icon name="plus" />
            {t("rolesPage.new")}
          </Button>
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1000px]:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="p-3">
          <nav aria-label={t("rolesPage.title")} className="flex flex-col gap-1">
            {roles.data.map((role) => (
              <button
                key={role.id}
                type="button"
                aria-current={role.id === current?.id ? "true" : undefined}
                onClick={() => setSelected(role.id)}
                className={cn(
                  "cursor-pointer rounded-box border border-transparent px-3 py-2.5 text-left hover:bg-surface focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none",
                  role.id === current?.id && "border-[#c5dde1] bg-lake-50",
                )}
              >
                <b className="block">{role.name}</b>
                <span className="text-[.8rem] text-ink-3">
                  {t("rolesPage.members", { count: role.member_count })}
                </span>
              </button>
            ))}
          </nav>
        </Card>
        {current && (
          <RoleEditor key={current.id} role={current} onDeleted={() => setSelected(null)} />
        )}
      </div>
      <NewRoleDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(role) => setSelected(role.id)}
      />
    </>
  );
}

function RoleEditor({ role, onDeleted }: { role: Role; onDeleted: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState(role.name);
  const [permissions, setPermissions] = useState<string[]>(role.permissions);
  const [deleting, setDeleting] = useState(false);
  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.roles }),
      queryClient.invalidateQueries({ queryKey: keys.staff }),
      // Mes propres droits ont pu changer : menu.
      queryClient.invalidateQueries({ queryKey: keys.me }),
    ]);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/roles/{id}/", {
          params: { path: { id: role.id } },
          body: { name: name.trim(), permissions: permissions as Permission[] },
        }),
      ),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/roles/{id}/", { params: { path: { id: role.id } } })),
    onSuccess: async () => {
      setDeleting(false);
      onDeleted();
      await refresh();
    },
  });
  const totp = requiresTotp(permissions);
  const title = name.trim() || role.name;
  const toggle = (code: string, on: boolean) => {
    save.reset();
    setPermissions((list) => (on ? [...list, code] : list.filter((item) => item !== code)));
  };

  return (
    <Card>
      <CardHeader className="flex-wrap">
        <CardTitle>{title}</CardTitle>
        <StatusPill tone={totp ? "info" : "gray"} title={t("rolesPage.totpHelp")}>
          {totp ? t("rolesPage.totpRequired") : t("rolesPage.totpNotRequired")}
        </StatusPill>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {permissions.length === 0 && <Banner tone="info">{t("rolesPage.noPermissionNote")}</Banner>}
        <Field id="role-name" label={t("rolesPage.name")} required>
          {(control) => (
            <Input
              {...control}
              value={name}
              onChange={(event) => {
                save.reset();
                setName(event.target.value);
              }}
            />
          )}
        </Field>
        {GROUPS.map((group) => (
          <fieldset key={group.key} className="rounded-card border border-line">
            <legend className="sr-only">{t(`permissions.groups.${group.key}`)}</legend>
            <h3 aria-hidden="true" className="border-b border-line px-4 py-3">
              {t(`permissions.groups.${group.key}`)}
            </h3>
            <div className="grid gap-x-6 gap-y-3 px-4 py-3.5 min-[700px]:grid-cols-2">
              {group.permissions.map((code) => (
                <CheckboxField
                  key={code}
                  id={`permission-${code}`}
                  label={t(`permissions.codes.${code}`)}
                  checked={permissions.includes(code)}
                  onCheckedChange={(checked) => toggle(code, checked === true)}
                />
              ))}
            </div>
          </fieldset>
        ))}
        <Members role={role} />
        {(save.error ?? remove.error) && (
          <Banner tone="due">{errorMessage(save.error ?? remove.error, t)}</Banner>
        )}
        {save.isSuccess && (
          <Banner tone="ok" role="status">
            {t("rolesPage.saved")}
          </Banner>
        )}
      </CardContent>
      <CardFooter>
        <div className="flex flex-col gap-1">
          <Button
            variant="destructive-outline"
            size="sm"
            className="self-start"
            disabled={role.member_count > 0}
            onClick={() => setDeleting(true)}
          >
            {t("rolesPage.delete")}
          </Button>
          {role.member_count > 0 && (
            <span className="text-[.8rem] text-ink-3">{t("rolesPage.deleteHelp")}</span>
          )}
        </div>
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {t("rolesPage.save")}
        </Button>
      </CardFooter>
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t("rolesPage.deleteTitle", { name: title })}
        confirmLabel={t("rolesPage.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => remove.mutate()}
        pending={remove.isPending}
        destructive
      >
        <p className="text-sm text-ink-2">{t("rolesPage.deleteText")}</p>
      </ConfirmDialog>
    </Card>
  );
}

/** « Utilisateurs avec ce rôle » : comptes actifs qui l'ont ; en donner le rôle à quelqu'un. */
function Members({ role }: { role: Role }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const members = useQuery({
    queryKey: [...keys.staff, { role: role.id }],
    queryFn: () =>
      call(api.GET("/api/staff/", { params: { query: { role: role.id, is_active: true } } })),
  });
  const candidates = useQuery({
    queryKey: [...keys.staff, { search, active: true }],
    queryFn: () =>
      call(
        api.GET("/api/staff/", {
          params: { query: { is_active: true, ...(search ? { search } : {}) } },
        }),
      ),
    enabled: adding,
  });
  const add = useMutation({
    mutationFn: (person: Schemas["Staff"]) =>
      call(
        api.PATCH("/api/staff/{id}/", {
          params: { path: { id: person.id } },
          body: { roles: [...person.roles, role.id] },
        }),
      ),
    onSuccess: async () => {
      setAdding(false);
      setSearch("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.staff }),
        queryClient.invalidateQueries({ queryKey: keys.roles }),
      ]);
    },
  });
  const others = (candidates.data?.results ?? []).filter(
    (person) => !person.roles.includes(role.id),
  );

  return (
    <section className="rounded-card border border-line">
      <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <h3>{t("rolesPage.members")}</h3>
        <Button variant="outline" size="sm" onClick={() => setAdding((open) => !open)}>
          {t("rolesPage.addMember")}
        </Button>
      </div>
      <div className="flex flex-col gap-2 px-4 py-3">
        {adding && (
          <div className="flex flex-col gap-2 rounded-box bg-surface p-3">
            <Input
              type="search"
              aria-label={t("rolesPage.addMemberLabel")}
              placeholder={t("staff.search")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {others.slice(0, 8).map((person) => (
              <button
                key={person.id}
                type="button"
                disabled={add.isPending}
                onClick={() => add.mutate(person)}
                className="flex cursor-pointer items-center gap-2.5 rounded-field px-2 py-1.5 text-left hover:bg-lake-50"
              >
                <Icon name="plus" size={14} />
                {fullName(person.user)}
              </button>
            ))}
            {add.isError && <Banner tone="due">{errorMessage(add.error, t)}</Banner>}
          </div>
        )}
        {members.isPending ? (
          <Skeleton label={t("common.loading")} />
        ) : members.data?.results.length ? (
          members.data.results.map((person) => (
            <div key={person.id} className="flex items-center gap-2.5 py-1.5">
              <Avatar
                text={initials(
                  person.user.last_name,
                  person.user.first_name,
                  person.user.middle_name,
                )}
              />
              <b>{fullName(person.user)}</b>
            </div>
          ))
        ) : (
          <p className="text-sm text-ink-3">{t("rolesPage.noMembers")}</p>
        )}
      </div>
    </section>
  );
}

function NewRoleDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (role: Role) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () =>
      call(api.POST("/api/roles/", { body: { name: name.trim(), permissions: [] } })),
    onSuccess: async (role) => {
      await queryClient.invalidateQueries({ queryKey: keys.roles });
      onCreated(role);
      onOpenChange(false);
      setName("");
    },
  });
  return (
    <DialogRoot
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        create.reset();
      }}
    >
      <DialogContent
        title={t("rolesPage.newTitle")}
        description={t("rolesPage.newText")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="new-role" disabled={create.isPending}>
              {t("rolesPage.create")}
            </Button>
          </>
        }
      >
        <form
          id="new-role"
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          {create.isError && <Banner tone="due">{errorMessage(create.error, t)}</Banner>}
          <Field id="new-role-name" label={t("rolesPage.name")} required>
            {(control) => (
              <Input
                {...control}
                value={name}
                placeholder={t("rolesPage.namePlaceholder")}
                onChange={(event) => setName(event.target.value)}
              />
            )}
          </Field>
        </form>
      </DialogContent>
    </DialogRoot>
  );
}
