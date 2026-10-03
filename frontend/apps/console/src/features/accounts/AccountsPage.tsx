// Comptes de la plateforme (5.4.1, maquette `console/comptes`) : recherche par noms ou chiffres
// du téléphone dans toutes les écoles, liste paginée par le serveur (écoles et rôles, familles du
// portail, double authentification, dernière connexion).
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDateTime, formatPhone, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  Input,
  PageHeader,
  Skeleton,
  StatusPill,
  Table,
  Tag,
  buttonVariants,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";

export type Account = Schemas["ConsoleAccount"];

export function fullName(account: Pick<Account, "last_name" | "middle_name" | "first_name">) {
  return [account.last_name, account.middle_name, account.first_name].filter(Boolean).join(" ");
}

/** Désactivé, ou compte de la plateforme (super-admin). */
export function AccountPills({ account }: { account: Account }) {
  const { t } = useTranslation();
  return (
    <>
      {!account.is_active && <StatusPill tone="due">{t("console.accounts.inactive")}</StatusPill>}
      {account.is_platform_admin && (
        <StatusPill tone="info">{t("console.accounts.platform")}</StatusPill>
      )}
    </>
  );
}

export function AccountsPage() {
  const { t, i18n } = useTranslation();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const query = useDeferredValue(search.trim());
  const accounts = useQuery({
    queryKey: [...keys.accounts, { query, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/accounts/", {
          params: { query: { search: query || undefined, page } },
        }),
      ),
    placeholderData: keepPreviousData,
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  return (
    <>
      <PageHeader title={t("console.accounts.title")} subtitle={t("console.accounts.subtitle")} />
      <Input
        type="search"
        aria-label={t("console.accounts.search")}
        placeholder={t("console.accounts.search")}
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        className="max-w-sm"
      />
      {accounts.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : accounts.isError ? (
        <>
          <Banner tone="due">{errorMessage(accounts.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void accounts.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          {accounts.data.results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.accounts.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.accounts.person")}</th>
                  <th>{t("console.accounts.schools")}</th>
                  <th>{t("console.accounts.totp")}</th>
                  <th>{t("console.accounts.lastLogin")}</th>
                  <th className="relative">
                    <span className="sr-only">{t("console.schools.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {accounts.data.results.map((account) => (
                  <tr key={account.id}>
                    <td>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Link to={`/accounts/${account.id}`} className="font-bold hover:underline">
                          {fullName(account)}
                        </Link>
                        <AccountPills account={account} />
                      </div>
                      <span className="text-sm text-ink-3 tabular-nums">
                        {formatPhone(account.phone)}
                      </span>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {account.memberships.map((membership) => (
                          <Tag
                            key={membership.id}
                            className={membership.is_active ? undefined : "line-through"}
                          >
                            {[membership.school.name, membership.roles.join(", ")]
                              .filter(Boolean)
                              .join(" · ")}
                          </Tag>
                        ))}
                        {account.families.map((family) => (
                          <Tag key={family.id} lot>
                            {t("console.accounts.parentOf", { school: family.school.name })}
                          </Tag>
                        ))}
                        {account.memberships.length + account.families.length === 0 && "—"}
                      </div>
                    </td>
                    <td>
                      {account.totp_enabled ? (
                        <StatusPill tone="ok">{t("console.accounts.totpOn")}</StatusPill>
                      ) : (
                        <span className="text-ink-3">—</span>
                      )}
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {account.last_login
                        ? formatDateTime(account.last_login, i18n.language, timeZone)
                        : "—"}
                    </td>
                    <td>
                      <Link
                        to={`/accounts/${account.id}`}
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        {t("console.schools.manage")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {(accounts.data.previous || accounts.data.next) && (
            <div className="flex justify-end gap-2 border-t border-line px-4 py-2.5">
              <Button
                variant="outline"
                size="sm"
                disabled={!accounts.data.previous}
                onClick={() => setPage(page - 1)}
              >
                {t("console.schools.previous")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!accounts.data.next}
                onClick={() => setPage(page + 1)}
              >
                {t("console.schools.next")}
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
