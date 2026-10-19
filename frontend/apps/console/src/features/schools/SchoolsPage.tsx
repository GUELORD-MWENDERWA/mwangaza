// Écoles de la plateforme (5.3, 4.15, maquette `console/ecoles`) : un onglet par type d'espace
// (réels, essai, démonstration), chiffres du tableau de bord (espaces réels seulement),
// recherche, filtre par état, liste paginée par le serveur (élèves, abonnement, dernière
// activité), « Ouvrir en tant qu'école » (session support à l'adresse de l'école, A3).
import { api, call } from "@mwangaza/api";
import { errorMessage, formatDateTime, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  Input,
  Kpi,
  PageHeader,
  Select,
  Skeleton,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  buttonVariants,
} from "@mwangaza/ui";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { keys } from "../../lib/queries";
import { RIGHTS, spaceRight, useCan } from "../../lib/rights";
import { KINDS, type School, type SchoolKind, SubscriptionPill, isClosed } from "./schoolForm";

const FILTERS = ["all", "active", "trial", "suspended", "stopped"] as const;
type Filter = (typeof FILTERS)[number];

/** Session support : connexion à l'adresse de l'école, puis motif (jamais dans une école
 *  suspendue ou arrêtée : le serveur la refuse). */
export function SupportLink({ school, className }: { school: School; className?: string }) {
  const { t } = useTranslation();
  if (isClosed(school)) return null;
  return (
    <a
      href={`${school.url}/app/support`}
      target="_blank"
      rel="noopener"
      className={className ?? buttonVariants({ variant: "outline", size: "sm" })}
    >
      {t("console.schools.openAsSchool")}
    </a>
  );
}

export function SchoolsPage() {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const can = useCan();
  // Sans « voir les écoles » (commercial), pas d'onglet « Réels » : le serveur les cache (EQ.1).
  const kinds = KINDS.filter((item) => item !== "live" || can(RIGHTS.schoolsView));
  // `?type=` : onglet d'arrivée (retour d'une fiche d'essai ou de démonstration supprimée).
  const [kind, setKind] = useState<SchoolKind>(
    kinds.find((item) => item === params.get("type")) ?? kinds[0] ?? "test",
  );
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const query = useDeferredValue(search.trim());
  const schools = useQuery({
    queryKey: [...keys.schools, { kind, query, filter, page }],
    queryFn: () =>
      call(
        api.GET("/api/console/schools/", {
          params: {
            query: {
              environment: kind,
              search: query || undefined,
              status: filter === "all" ? undefined : filter,
              page,
            },
          },
        }),
      ),
    placeholderData: keepPreviousData,
    // Suppression en cours (4.16) : la liste se relit jusqu'à ce que l'espace ait disparu.
    refetchInterval: (state) =>
      state.state.data?.results.some((school) => school.status === "deleting") ? 3000 : false,
  });
  const dashboard = useQuery({
    queryKey: keys.dashboard,
    queryFn: () => call(api.GET("/api/console/dashboard/")),
    enabled: can(RIGHTS.schoolsView),
  });
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const counts = dashboard.data?.schools;

  const list = (
    <>
      {kind === "live" && dashboard.data && counts && (
        <div className="grid grid-cols-2 gap-3.5 min-[820px]:grid-cols-4">
          <Kpi
            label={t("console.dashboard.activeSchools")}
            value={counts.active}
            sub={t("console.schools.suspendedSub", { count: counts.suspended })}
          />
          <Kpi
            label={t("console.schools.inTrial")}
            value={counts.trial}
            sub={t("console.schools.trialEndingSub", { count: counts.trial_ending })}
          />
          <Kpi
            label={t("console.dashboard.students")}
            value={dashboard.data.students.toLocaleString(i18n.language)}
          />
          <Kpi label={t("console.dashboard.payments")} value={dashboard.data.payments_today} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          aria-label={t("console.schools.search")}
          placeholder={t("console.schools.search")}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          className="max-w-xs"
        />
        <Select
          aria-label={t("console.schools.filter")}
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value as Filter);
            setPage(1);
          }}
          className="w-auto"
        >
          {FILTERS.map((value) => (
            <option key={value} value={value}>
              {t(`console.schools.filters.${value}`)}
            </option>
          ))}
        </Select>
      </div>
      {schools.isPending ? (
        <Skeleton label={t("common.loading")} />
      ) : schools.isError ? (
        <>
          <Banner tone="due">{errorMessage(schools.error, t)}</Banner>
          <Button variant="outline" className="w-fit" onClick={() => void schools.refetch()}>
            {t("common.retry")}
          </Button>
        </>
      ) : (
        <Card>
          {schools.data.results.length === 0 ? (
            <p className="px-4 py-5 text-ink-3">{t("console.schools.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>{t("console.schools.school")}</th>
                  <th className="text-right">{t("console.schools.students")}</th>
                  <th>{t("console.schools.subscription")}</th>
                  <th>{t("console.schools.lastActivity")}</th>
                  {/* `relative` : le titre invisible reste dans le tableau qui défile, sans
                      élargir la page sur téléphone. */}
                  <th className="relative">
                    <span className="sr-only">{t("console.schools.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {schools.data.results.map((school) => (
                  <tr key={school.id}>
                    <td>
                      <Link to={`/schools/${school.id}`} className="font-bold hover:underline">
                        {school.name}
                      </Link>
                      <br />
                      <span className="text-sm text-ink-3">
                        {school.url.replace(/^\w+:\/\//, "")}
                      </span>
                    </td>
                    <td className="text-right tabular-nums">
                      {school.student_count.toLocaleString(i18n.language)}
                    </td>
                    <td>
                      <SubscriptionPill school={school} />
                    </td>
                    <td className="text-sm whitespace-nowrap text-ink-3">
                      {school.last_activity_at
                        ? formatDateTime(school.last_activity_at, i18n.language, timeZone)
                        : "—"}
                    </td>
                    <td>
                      <div className="flex justify-end gap-1.5">
                        {can(RIGHTS.accountsSupport) && <SupportLink school={school} />}
                        <Link
                          to={`/schools/${school.id}`}
                          className={buttonVariants({ variant: "ghost", size: "sm" })}
                        >
                          {t("console.schools.manage")}
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {(schools.data.previous || schools.data.next) && (
            <div className="flex justify-end gap-2 border-t border-line px-4 py-2.5">
              <Button
                variant="outline"
                size="sm"
                disabled={!schools.data.previous}
                onClick={() => setPage(page - 1)}
              >
                {t("console.schools.previous")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!schools.data.next}
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

  return (
    <>
      <PageHeader
        title={t("console.schools.title")}
        subtitle={t("console.schools.subtitle")}
        actions={
          can(spaceRight(kind, RIGHTS.schoolsManage)) && (
            <Link to={`/schools/new?type=${kind}`} className={buttonVariants({ size: "lg" })}>
              {t("console.schools.new")}
            </Link>
          )
        }
      />
      <Tabs
        value={kind}
        onValueChange={(value) => {
          setKind(value as SchoolKind);
          setPage(1);
        }}
      >
        <TabsList aria-label={t("console.schools.kindLabel")}>
          {kinds.map((value) => (
            <TabsTrigger key={value} value={value}>
              {t(`console.schools.kinds.${value}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={kind}>{list}</TabsContent>
      </Tabs>
    </>
  );
}
