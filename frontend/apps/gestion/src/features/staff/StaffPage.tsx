// Comptes du personnel (M3, B1-B3) : qui peut se connecter à l'école, avec quels rôles. Droit
// `roles.manage`. Un compte = un numéro de téléphone, valable dans toutes les écoles : l'école ne
// voit jamais les autres écoles d'une personne, et ne change le compte lui-même (noms, téléphone,
// mot de passe, double authentification) que s'il ne sert que chez elle.
import { api, call, type Schemas } from "@mwangaza/api";
import { formatDay, formatVisit, useTranslation } from "@mwangaza/i18n";
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
  Code,
  ConfirmDialog,
  DialogClose,
  DialogContent,
  DialogRoot,
  Field,
  Icon,
  Input,
  List,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tag,
  initials,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";

import { applyServerErrors, errorMessage } from "../../lib/errors";
import { formatPhone, fullName } from "../../lib/people";
import { keys, useRoles } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useSettled } from "../../lib/settled";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";

type Staff = Schemas["Staff"];
type Role = Schemas["Role"];
type Filters = { search: string; role: string; state: "" | "active" | "inactive"; page: number };

/** Valeur stable depuis `delay` ms (recherche : une requête par pause dans la frappe). */

function useStaff(filters: Filters) {
  return useQuery({
    queryKey: [...keys.staff, filters],
    queryFn: () =>
      call(
        api.GET("/api/staff/", {
          params: {
            query: {
              ...(filters.search ? { search: filters.search } : {}),
              ...(filters.role ? { role: filters.role } : {}),
              ...(filters.state ? { is_active: filters.state === "active" } : {}),
              ...(filters.page > 1 ? { page: filters.page } : {}),
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
  });
}

export function StaffPage() {
  const { t } = useTranslation();
  const roles = useRoles();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [state, setState] = useState<Filters["state"]>("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const settledSearch = useSettled(search.trim());
  const staff = useStaff({ search: settledSearch, role, state, page });
  const phone = useRef<HTMLInputElement>(null);

  if (roles.isError) return <LoadError error={roles.error} onRetry={() => void roles.refetch()} />;
  if (staff.isError) return <LoadError error={staff.error} onRetry={() => void staff.refetch()} />;

  const rolesById = new Map((roles.data ?? []).map((item) => [item.id, item]));
  const people = staff.data?.results ?? [];
  const current = people.find((person) => person.id === selected) ?? null;
  const filter = (apply: () => void) => {
    apply();
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title={t("staff.title")}
        subtitle={t("staff.subtitle")}
        actions={
          <>
            <Button asChild size="lg" variant="outline">
              <Link to="/staff/import">
                <Icon name="upload" />
                {t("staff.importButton")}
              </Link>
            </Button>
            <Button size="lg" onClick={() => phone.current?.focus()}>
              <Icon name="userplus" />
              {t("staff.new")}
            </Button>
          </>
        }
      />
      <Card>
        <CardContent className="grid gap-3 min-[700px]:grid-cols-[1fr_auto_auto]">
          <div className="relative">
            <Icon
              name="search"
              size={16}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3"
            />
            <Input
              type="search"
              aria-label={t("staff.search")}
              placeholder={t("staff.search")}
              value={search}
              onChange={(event) => filter(() => setSearch(event.target.value))}
              className="pl-9"
            />
          </div>
          <Select
            aria-label={t("staff.roleFilter")}
            value={role}
            onChange={(event) => filter(() => setRole(event.target.value))}
          >
            <option value="">{t("staff.allRoles")}</option>
            {(roles.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("staff.stateFilter")}
            value={state}
            onChange={(event) => filter(() => setState(event.target.value as Filters["state"]))}
          >
            <option value="">{t("staff.allStates")}</option>
            <option value="active">{t("staff.activeOnly")}</option>
            <option value="inactive">{t("staff.inactiveOnly")}</option>
          </Select>
        </CardContent>
      </Card>
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <Card>
          {!staff.data || !roles.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : (
            <StaffTable
              people={people}
              rolesById={rolesById}
              selected={selected}
              onSelect={setSelected}
            />
          )}
          <Pagination
            page={page}
            hasPrevious={Boolean(staff.data?.previous)}
            hasNext={Boolean(staff.data?.next)}
            onPage={setPage}
            summary={
              <span className="flex flex-wrap gap-x-4 gap-y-1">
                {t("staff.total", { count: staff.data?.count ?? 0 })}
                <Link to="/roles">{t("staff.manageRoles")}</Link>
              </span>
            }
          />
        </Card>
        <div className="flex flex-col gap-4">
          {current && roles.data ? (
            <PersonCard key={current.id} person={current} roles={roles.data} />
          ) : (
            <Card>
              <CardContent className="text-ink-3">{t("staff.pick")}</CardContent>
            </Card>
          )}
          {roles.data && (
            <NewAccountCard roles={roles.data} phoneRef={phone} onCreated={setSelected} />
          )}
        </div>
      </div>
    </>
  );
}

function stateOf(person: Staff): "active" | "invited" | "inactive" {
  if (!person.is_active) return "inactive";
  return person.last_login_at ? "active" : "invited";
}

const STATE_TONES = { active: "ok", invited: "info", inactive: "gray" } as const;

function StateBadge({ person }: { person: Staff }) {
  const { t } = useTranslation();
  const state = stateOf(person);
  return <StatusPill tone={STATE_TONES[state]}>{t(`staff.state.${state}`)}</StatusPill>;
}

function TotpBadge({ person }: { person: Staff }) {
  const { t } = useTranslation();
  if (person.totp === "enabled")
    return <StatusPill tone="ok">{t("staff.totp.enabled")}</StatusPill>;
  if (person.totp === "to_enable") {
    return <StatusPill tone="warn">{t("staff.totp.to_enable")}</StatusPill>;
  }
  return <span className="text-sm text-ink-3">{t("staff.totp.not_required")}</span>;
}

function StaffTable({
  people,
  rolesById,
  selected,
  onSelect,
}: {
  people: Staff[];
  rolesById: Map<string, Role>;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  if (people.length === 0)
    return <CardContent className="text-ink-3">{t("staff.empty")}</CardContent>;
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("staff.columns.person")}</th>
          <th>{t("staff.columns.roles")}</th>
          <th>{t("staff.columns.totp")}</th>
          <th>{t("staff.columns.lastLogin")}</th>
          <th>{t("staff.columns.state")}</th>
        </tr>
      </thead>
      <tbody>
        {people.map((person) => (
          <tr key={person.id} aria-selected={person.id === selected}>
            <td>
              <button
                type="button"
                onClick={() => onSelect(person.id)}
                className="flex cursor-pointer items-center gap-2.5 text-left focus-visible:ring-3 focus-visible:ring-lake-50 focus-visible:outline-none"
              >
                <Avatar
                  text={initials(
                    person.user.last_name,
                    person.user.first_name,
                    person.user.middle_name,
                  )}
                />
                <span>
                  <b className="block">{fullName(person.user)}</b>
                  <span className="text-xs whitespace-nowrap text-ink-3 tabular-nums">
                    {formatPhone(person.user.phone)}
                  </span>
                </span>
              </button>
            </td>
            <td>
              <div className="flex flex-wrap gap-1">
                {person.roles.map((id) => {
                  const role = rolesById.get(id);
                  return role ? <Tag key={id}>{role.name}</Tag> : null;
                })}
              </div>
            </td>
            <td>
              <TotpBadge person={person} />
            </td>
            <td className="text-sm whitespace-nowrap">
              {person.last_login_at
                ? formatVisit(person.last_login_at, i18n.language, school.timezone, (time) =>
                    t("common.today", { time }),
                  )
                : t("staff.never")}
            </td>
            <td>
              <StateBadge person={person} />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function RoleCheckboxes({
  roles,
  value,
  onChange,
  idPrefix,
}: {
  roles: Role[];
  value: string[];
  onChange: (value: string[]) => void;
  idPrefix: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {roles.map((role) => (
        <CheckboxField
          key={role.id}
          id={`${idPrefix}-${role.id}`}
          label={role.name}
          checked={value.includes(role.id)}
          onCheckedChange={(checked) =>
            onChange(checked ? [...value, role.id] : value.filter((id) => id !== role.id))
          }
        />
      ))}
    </div>
  );
}

function useRefreshStaff() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.staff }),
      queryClient.invalidateQueries({ queryKey: keys.roles }),
    ]);
}

function PersonCard({ person, roles }: { person: Staff; roles: Role[] }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const refresh = useRefreshStaff();
  const name = fullName(person.user);
  const [chosen, setChosen] = useState(person.roles);
  const [password, setPassword] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"totp" | "deactivate" | null>(null);
  const [editing, setEditing] = useState(false);
  const id = { params: { path: { id: person.id } } };

  const saveRoles = useMutation({
    mutationFn: () => call(api.PATCH("/api/staff/{id}/", { ...id, body: { roles: chosen } })),
    onSuccess: refresh,
  });
  const newPassword = useMutation({
    mutationFn: () => call(api.POST("/api/staff/{id}/new-password/", id)),
    onSuccess: (data) => setPassword(data.temporary_password),
  });
  const resetTotp = useMutation({
    mutationFn: () => call(api.POST("/api/staff/{id}/reset-totp/", id)),
    onSuccess: async () => {
      setConfirm(null);
      await refresh();
    },
  });
  const setActive = useMutation({
    mutationFn: (is_active: boolean) =>
      call(api.PATCH("/api/staff/{id}/", { ...id, body: { is_active } })),
    onSuccess: async () => {
      setConfirm(null);
      await refresh();
    },
  });
  const changed =
    chosen.length !== person.roles.length || chosen.some((role) => !person.roles.includes(role));
  const failure = saveRoles.error ?? newPassword.error ?? setActive.error;
  const managed = person.account_managed_here;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{name}</CardTitle>
        <StateBadge person={person} />
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <List>
          <div>
            <span className="text-ink-2">{t("staff.detail.phone")}</span>
            <b className="tabular-nums">{formatPhone(person.user.phone)}</b>
          </div>
          <div>
            <span className="text-ink-2">{t("staff.detail.added")}</span>
            <span>{formatDay(person.created_at.slice(0, 10), i18n.language)}</span>
          </div>
          <div>
            <span className="text-ink-2">{t("staff.columns.lastLogin")}</span>
            <span>
              {person.last_login_at
                ? formatVisit(person.last_login_at, i18n.language, school.timezone, (time) =>
                    t("common.today", { time }),
                  )
                : t("staff.never")}
            </span>
          </div>
        </List>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-sm font-bold text-ink-2">{t("staff.detail.roles")}</legend>
          <RoleCheckboxes
            roles={roles}
            value={chosen}
            onChange={(value) => {
              setChosen(value);
              saveRoles.reset();
            }}
            idPrefix={`roles-${person.id}`}
          />
        </fieldset>
        {failure && <Banner tone="due">{errorMessage(failure, t)}</Banner>}
        {saveRoles.isSuccess && (
          <Banner tone="ok" role="status">
            {t("staff.detail.rolesSaved")}
          </Banner>
        )}
        {resetTotp.isSuccess && (
          <Banner tone="ok" role="status">
            {t("staff.resetTotp.done")}
          </Banner>
        )}
        <Button
          variant="outline"
          className="self-start"
          disabled={!changed || chosen.length === 0 || saveRoles.isPending}
          onClick={() => saveRoles.mutate()}
        >
          {t("staff.detail.saveRoles")}
        </Button>
      </CardContent>
      <CardFooter className="justify-start">
        <Button
          variant="outline"
          size="sm"
          disabled={!managed || newPassword.isPending}
          onClick={() => newPassword.mutate()}
        >
          <Icon name="key" size={14} />
          {t("staff.detail.newPassword")}
        </Button>
        <Button variant="outline" size="sm" disabled={!managed} onClick={() => setConfirm("totp")}>
          {t("staff.detail.resetTotp")}
        </Button>
        <Button variant="outline" size="sm" disabled={!managed} onClick={() => setEditing(true)}>
          {t("staff.detail.editAccount")}
        </Button>
        {person.is_active ? (
          <Button variant="destructive-outline" size="sm" onClick={() => setConfirm("deactivate")}>
            {t("staff.detail.deactivate")}
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            disabled={setActive.isPending}
            onClick={() => setActive.mutate(true)}
          >
            {t("staff.detail.reactivate")}
          </Button>
        )}
        {!managed && <p className="w-full text-xs text-ink-3">{t("staff.detail.elsewhere")}</p>}
      </CardFooter>
      <PasswordDialog name={name} password={password} onClose={() => setPassword(null)} />
      <ConfirmDialog
        open={confirm === "totp"}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={t("staff.resetTotp.title", { name })}
        confirmLabel={t("staff.detail.resetTotp")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => resetTotp.mutate()}
        pending={resetTotp.isPending}
      >
        <p className="text-sm text-ink-2">{t("staff.resetTotp.text", { name })}</p>
        {resetTotp.isError && <Banner tone="due">{errorMessage(resetTotp.error, t)}</Banner>}
      </ConfirmDialog>
      <ConfirmDialog
        open={confirm === "deactivate"}
        onOpenChange={(open) => !open && setConfirm(null)}
        title={t("staff.deactivate.title", { name })}
        confirmLabel={t("staff.detail.deactivate")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => setActive.mutate(false)}
        pending={setActive.isPending}
        destructive
      >
        <p className="text-sm text-ink-2">{t("staff.deactivate.text", { name })}</p>
        {setActive.isError && <Banner tone="due">{errorMessage(setActive.error, t)}</Banner>}
      </ConfirmDialog>
      {editing && <AccountDialog person={person} onClose={() => setEditing(false)} />}
    </Card>
  );
}

function PasswordDialog({
  name,
  password,
  onClose,
}: {
  name: string;
  password: string | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <DialogRoot open={password !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("staff.password.title")}
        description={t("staff.password.text", { name })}
        footer={
          <DialogClose asChild>
            <Button>{t("staff.password.done")}</Button>
          </DialogClose>
        }
      >
        <Code className="rounded-box bg-surface px-4 py-3 text-center text-xl">{password}</Code>
      </DialogContent>
    </DialogRoot>
  );
}

function useAccountSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z.object({
        phone: z.string().trim().min(1, t("validation.phoneRequired")),
        last_name: z.string().trim().min(1, t("validation.nameRequired")).max(100),
        middle_name: z.string().trim().max(100),
        first_name: z.string().trim().max(100),
      }),
    [t],
  );
}

const ACCOUNT_FIELDS = ["phone", "last_name", "middle_name", "first_name"] as const;

function AccountDialog({ person, onClose }: { person: Staff; onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefreshStaff();
  const schema = useAccountSchema();
  const [general, setGeneral] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      phone: person.user.phone,
      last_name: person.user.last_name,
      middle_name: person.user.middle_name,
      first_name: person.user.first_name,
    },
  });
  const save = useMutation({
    mutationFn: (body: z.output<typeof schema>) =>
      call(api.PATCH("/api/staff/{id}/", { params: { path: { id: person.id } }, body })),
    onSuccess: async () => {
      await refresh();
      onClose();
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...ACCOUNT_FIELDS], form.setError, t)),
  });
  const { errors } = form.formState;
  return (
    <DialogRoot open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={t("staff.account.title")}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="outline">{t("common.cancel")}</Button>
            </DialogClose>
            <Button type="submit" form="account-form" disabled={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form
          id="account-form"
          noValidate
          className="grid gap-3 min-[600px]:grid-cols-3"
          onSubmit={form.handleSubmit((values) => {
            setGeneral(null);
            save.mutate(values);
          })}
        >
          {general && (
            <Banner tone="due" className="min-[600px]:col-span-3">
              {general}
            </Banner>
          )}
          <Field
            id="account-phone"
            label={t("staff.create.phone")}
            required
            error={errors.phone?.message}
            className="min-[600px]:col-span-3"
          >
            {(control) => <Input {...control} inputMode="tel" {...form.register("phone")} />}
          </Field>
          <Field
            id="account-last-name"
            label={t("staff.create.lastName")}
            required
            error={errors.last_name?.message}
          >
            {(control) => <Input {...control} {...form.register("last_name")} />}
          </Field>
          <Field
            id="account-middle-name"
            label={t("staff.create.middleName")}
            error={errors.middle_name?.message}
          >
            {(control) => <Input {...control} {...form.register("middle_name")} />}
          </Field>
          <Field
            id="account-first-name"
            label={t("staff.create.firstName")}
            error={errors.first_name?.message}
          >
            {(control) => <Input {...control} {...form.register("first_name")} />}
          </Field>
        </form>
      </DialogContent>
    </DialogRoot>
  );
}

function NewAccountCard({
  roles,
  phoneRef,
  onCreated,
}: {
  roles: Role[];
  phoneRef: React.RefObject<HTMLInputElement | null>;
  onCreated: (id: string) => void;
}) {
  const { t } = useTranslation();
  const refresh = useRefreshStaff();
  const schema = useMemo(
    () =>
      z.object({
        phone: z.string().trim().min(1, t("validation.phoneRequired")),
        last_name: z.string().trim().max(100),
        middle_name: z.string().trim().max(100),
        first_name: z.string().trim().max(100),
        roles: z.array(z.string()).min(1, t("validation.rolesRequired")),
      }),
    [t],
  );
  const [general, setGeneral] = useState<string | null>(null);
  const [password, setPassword] = useState<{ name: string; value: string } | null>(null);
  const [known, setKnown] = useState<string | null>(null);
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      phone: "",
      last_name: "",
      middle_name: "",
      first_name: "",
      roles: [] as string[],
    },
  });
  const create = useMutation({
    mutationFn: (body: z.output<typeof schema>) => call(api.POST("/api/staff/", { body })),
    onSuccess: async (created) => {
      form.reset();
      await refresh();
      onCreated(created.id);
      const name = fullName(created.user);
      if (created.temporary_password) setPassword({ name, value: created.temporary_password });
      else setKnown(name);
    },
    onError: (error) =>
      setGeneral(applyServerErrors(error, [...ACCOUNT_FIELDS, "roles"], form.setError, t)),
  });
  const { errors } = form.formState;
  const { ref: phoneFieldRef, ...phoneField } = form.register("phone");

  return (
    <Card>
      <form
        noValidate
        onSubmit={form.handleSubmit((values) => {
          setGeneral(null);
          setKnown(null);
          create.mutate(values);
        })}
      >
        <CardHeader>
          <CardTitle>{t("staff.create.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {general && <Banner tone="due">{general}</Banner>}
          {known && (
            <Banner tone="ok" role="status">
              {t("staff.create.added", { name: known })}
            </Banner>
          )}
          <Field
            id="new-phone"
            label={t("staff.create.phone")}
            required
            error={errors.phone?.message}
          >
            {(control) => (
              <Input
                {...control}
                inputMode="tel"
                placeholder={t("staff.create.phonePlaceholder")}
                {...phoneField}
                ref={(element) => {
                  phoneFieldRef(element);
                  phoneRef.current = element;
                }}
              />
            )}
          </Field>
          <Banner tone="info">{t("staff.create.known")}</Banner>
          <p className="text-xs text-ink-3">{t("staff.create.unknown")}</p>
          <div className="grid gap-3 min-[600px]:grid-cols-3 min-[1200px]:grid-cols-1">
            <Field
              id="new-last-name"
              label={t("staff.create.lastName")}
              error={errors.last_name?.message}
            >
              {(control) => <Input {...control} {...form.register("last_name")} />}
            </Field>
            <Field
              id="new-middle-name"
              label={t("staff.create.middleName")}
              error={errors.middle_name?.message}
            >
              {(control) => <Input {...control} {...form.register("middle_name")} />}
            </Field>
            <Field
              id="new-first-name"
              label={t("staff.create.firstName")}
              error={errors.first_name?.message}
            >
              {(control) => <Input {...control} {...form.register("first_name")} />}
            </Field>
          </div>
          <fieldset>
            <legend className="mb-2 text-sm font-bold text-ink-2">{t("staff.create.roles")}</legend>
            <Controller
              control={form.control}
              name="roles"
              render={({ field }) => (
                <RoleCheckboxes
                  roles={roles}
                  value={field.value}
                  onChange={field.onChange}
                  idPrefix="new-roles"
                />
              )}
            />
            {errors.roles && (
              <p role="alert" className="mt-1.5 text-xs text-due">
                {errors.roles.message}
              </p>
            )}
          </fieldset>
        </CardContent>
        <CardFooter className="justify-end">
          <Button type="submit" disabled={create.isPending}>
            {t("staff.create.submit")}
          </Button>
        </CardFooter>
      </form>
      <PasswordDialog
        name={password?.name ?? ""}
        password={password?.value ?? null}
        onClose={() => setPassword(null)}
      />
    </Card>
  );
}
