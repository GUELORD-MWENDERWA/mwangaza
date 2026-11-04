// Recherche de la barre du haut (lot 5, ②bis) : écoles et comptes du mode affiché, selon les
// droits du membre ; Ctrl K l'ouvre de n'importe quelle page.
import { api, call } from "@mwangaza/api";
import { formatPhone, useTranslation } from "@mwangaza/i18n";
import { DialogContent, DialogRoot, Icon, Input } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { RIGHTS, useCan } from "../../lib/rights";
import { fullName } from "../accounts/AccountsPage";

const SHOWN = 5;

export function ConsoleSearch() {
  const { t } = useTranslation();
  const can = useCan();
  const [open, setOpen] = useState(false);
  const allowed = can(RIGHTS.schoolsView, RIGHTS.demosManage, RIGHTS.accountsSupport);
  useEffect(() => {
    if (!allowed) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [allowed]);
  if (!allowed) return <span className="flex-1" />;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("console.shell.search.title")}
        className="flex min-h-11 min-w-11 cursor-pointer items-center justify-center gap-2 rounded-field border border-line bg-surface px-3 text-ink-3 min-[900px]:w-[460px] min-[900px]:justify-start"
      >
        <Icon name="search" size={18} />
        <span className="hidden truncate min-[900px]:inline">{t("console.shell.search.open")}</span>
        <kbd className="ml-auto hidden shrink-0 rounded-[5px] border border-b-2 border-line bg-card px-1.5 text-xs whitespace-nowrap text-ink-2 min-[900px]:inline">
          {t("shell.search.shortcut")}
        </kbd>
      </button>
      <span className="flex-1" />
      <DialogRoot open={open} onOpenChange={setOpen}>
        {open && <SearchDialog onClose={() => setOpen(false)} />}
      </DialogRoot>
    </>
  );
}

function SearchDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const can = useCan();
  const [search, setSearch] = useState("");
  const query = useDeferredValue(search.trim());
  const ready = query.length >= 2;
  const schools = useQuery({
    queryKey: [...keys.schools, "search", query],
    queryFn: () => call(api.GET("/api/console/schools/", { params: { query: { search: query } } })),
    enabled: ready && can(RIGHTS.schoolsView, RIGHTS.demosManage),
  });
  const accounts = useQuery({
    queryKey: [...keys.accounts, "search", query],
    queryFn: () =>
      call(api.GET("/api/console/accounts/", { params: { query: { search: query } } })),
    enabled: ready && can(RIGHTS.accountsSupport),
  });
  const foundSchools = (schools.data?.results ?? []).slice(0, SHOWN);
  const foundAccounts = (accounts.data?.results ?? []).slice(0, SHOWN);
  const loading = schools.isFetching || accounts.isFetching;
  const row =
    "flex min-h-11 flex-wrap items-center justify-between gap-2 rounded-field px-2 py-2 text-ink no-underline hover:bg-surface focus:bg-surface";
  return (
    <DialogContent title={t("console.shell.search.title")} className="top-[15vh] translate-y-0">
      <Input
        autoFocus
        type="search"
        aria-label={t("console.shell.search.label")}
        placeholder={t("console.shell.search.label")}
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {!ready ? (
        <p className="text-sm text-ink-3">{t("console.shell.search.hint")}</p>
      ) : !loading && foundSchools.length + foundAccounts.length === 0 ? (
        <p className="text-sm text-ink-3">{t("console.shell.search.none")}</p>
      ) : (
        <div className="flex flex-col gap-2">
          {foundSchools.length > 0 && (
            <section>
              <h3 className="px-2 text-xs font-semibold tracking-wider text-ink-3 uppercase">
                {t("console.shell.search.schools")}
              </h3>
              <ul>
                {foundSchools.map((school) => (
                  <li key={school.id}>
                    <Link to={`/schools/${school.id}`} onClick={onClose} className={row}>
                      <b>{school.name}</b>
                      <span className="text-sm text-ink-3">{school.code}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {foundAccounts.length > 0 && (
            <section>
              <h3 className="px-2 text-xs font-semibold tracking-wider text-ink-3 uppercase">
                {t("console.shell.search.accounts")}
              </h3>
              <ul>
                {foundAccounts.map((account) => (
                  <li key={account.id}>
                    <Link to={`/accounts/${account.id}`} onClick={onClose} className={row}>
                      <b>{fullName(account)}</b>
                      <span className="text-sm text-ink-3 tabular-nums">
                        {formatPhone(account.phone)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </DialogContent>
  );
}
