// Invitations au portail (H7, maquette `gestion/invitations-portail`) : familles activées par
// classe de l'année en cours, puis familles de la classe choisie avec l'état de leur portail ;
// lettres de la classe (deux par A4), lettre et message par famille avec `students.edit`.
import { useTranslation } from "@mwangaza/i18n";
import { formatDate } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Icon,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { formatPhone, studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { LoadError } from "../status/StatusPages";
import { Pagination } from "../shell/Pagination";
import { type Family, familyName } from "./data";
import { InvitationActions } from "./InvitationActions";
import {
  invitationLettersUrl,
  type PortalFilter,
  useActivation,
  useClassFamilies,
} from "./invitations";

type ClassRow = {
  id: string;
  name: string;
  families: number;
  activated: number;
  invitable: number;
};

const TONES = {
  pending: "warn",
  activated: "ok",
  no_phone: "due",
  code_expired: "due",
  suspended: "gray",
} as const;
const PAGE_SIZE = 50;

export function InvitationsPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const summary = useActivation();
  const [chosen, setChosen] = useState(params.get("class") ?? "");
  if (summary.error) {
    return <LoadError error={summary.error} onRetry={() => void summary.refetch()} />;
  }
  const classes = summary.data?.classes ?? [];
  const group = classes.find((row) => row.id === chosen) ?? classes[0];
  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/students" className="text-lake underline">
              {t("students.list.title")}
            </Link>{" "}
            / {t("students.invitations.title")}
          </>
        }
        title={t("students.invitations.title")}
        subtitle={t("students.invitations.subtitle")}
      />
      {!summary.data ? (
        <Skeleton label={t("common.loading")} />
      ) : !group ? (
        <Banner tone="warn">{t("students.invitations.noClasses")}</Banner>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1000px]:grid-cols-[330px_minmax(0,1fr)]">
          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle>{t("students.invitations.byClass")}</CardTitle>
              <small className="text-ink-3">
                {t("students.invitations.school", {
                  activated: summary.data.activated,
                  families: summary.data.families,
                })}
              </small>
            </CardHeader>
            {/* Sur téléphone, la liste des classes défile : le détail reste à portée. */}
            <div className="max-[999px]:max-h-[320px] max-[999px]:overflow-y-auto">
              <Table>
                <thead>
                  <tr>
                    <th>{t("students.invitations.class")}</th>
                    <th className="text-right">{t("students.invitations.activated")}</th>
                    <th aria-hidden />
                  </tr>
                </thead>
                <tbody>
                  {classes.map((row) => (
                    <tr key={row.id} className={row.id === group.id ? "bg-lamp-soft" : undefined}>
                      <td>
                        <button
                          type="button"
                          className="font-bold text-ink hover:text-lake hover:underline"
                          aria-pressed={row.id === group.id}
                          onClick={() => setChosen(row.id)}
                        >
                          {row.name}
                        </button>
                      </td>
                      <td className="text-right tabular-nums">
                        {row.activated} / {row.families}
                      </td>
                      <td className="w-[90px]">
                        <Progress value={row.activated} total={row.families} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </Card>
          <ClassFamilies key={group.id} group={group} />
        </div>
      )}
    </>
  );
}

function Progress({ value, total }: { value: number; total: number }) {
  const share = total ? value / total : 0;
  return (
    <div className="h-2 overflow-hidden rounded-full bg-gray-50">
      <div
        className={`h-full rounded-full ${share >= 0.7 ? "bg-ok" : "bg-warn"}`}
        style={{ width: `${Math.round(share * 100)}%` }}
      />
    </div>
  );
}

function ClassFamilies({ group }: { group: ClassRow }) {
  const { t } = useTranslation();
  const editor = can(useCurrentMe(), ["students.edit"]);
  const [portal, setPortal] = useState<PortalFilter>("not_activated");
  const [page, setPage] = useState(1);
  const families = useClassFamilies(group.id, portal, page);
  const results = families.data?.results ?? [];
  const count = families.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>{group.name}</CardTitle>
          <small className="text-ink-3">
            {t("students.invitations.classSummary", {
              activated: group.activated,
              families: group.families,
            })}
          </small>
        </div>
        {editor &&
          (group.invitable ? (
            <Button asChild>
              <a href={invitationLettersUrl(group.id)} target="_blank" rel="noopener">
                <Icon name="print" size={16} />
                {t("students.invitations.printLetters", { count: group.invitable })}
              </a>
            </Button>
          ) : (
            <Button disabled>
              <Icon name="print" size={16} />
              {t("students.invitations.printLetters", { count: 0 })}
            </Button>
          ))}
      </CardHeader>
      <CardContent>
        <Segmented
          label={t("students.invitations.filter")}
          value={portal}
          onValueChange={(value) => {
            setPortal(value);
            setPage(1);
          }}
          options={[
            {
              value: "not_activated",
              label: t("students.invitations.notActivated", {
                count: group.families - group.activated,
              }),
            },
            { value: "all", label: t("students.invitations.all", { count: group.families }) },
          ]}
        />
      </CardContent>
      {families.error ? (
        <CardContent>
          <Banner tone="due">{t("students.invitations.loadError")}</Banner>
        </CardContent>
      ) : !families.data ? (
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      ) : results.length === 0 ? (
        <CardContent className="text-ink-3">{t("students.invitations.empty")}</CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("students.invitations.columns.student")}</th>
              <th>{t("students.invitations.columns.guardian")}</th>
              <th>{t("students.invitations.columns.portal")}</th>
              {editor && <th aria-hidden />}
            </tr>
          </thead>
          <tbody>
            {results.map((family) => (
              <FamilyRow key={family.id} family={family} group={group} editor={editor} />
            ))}
          </tbody>
        </Table>
      )}
      <Pagination
        page={page}
        hasPrevious={Boolean(families.data?.previous)}
        hasNext={Boolean(families.data?.next)}
        onPage={setPage}
        summary={t("students.invitations.range", {
          from,
          to: from ? from + results.length - 1 : 0,
          count,
        })}
      />
    </Card>
  );
}

function FamilyRow({
  family,
  group,
  editor,
}: {
  family: Family;
  group: ClassRow;
  editor: boolean;
}) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const date = (iso: string) => formatDate(iso, i18n.language, school.timezone);
  const primary = family.guardians.find((guardian) => guardian.is_primary);
  const here = family.students.filter((child) => child.class_group_name === group.name);
  const others = family.students.filter(
    (child) => child.class_group_name && child.class_group_name !== group.name,
  );
  const status = family.portal_status;
  return (
    <tr>
      <td>
        <span className="flex flex-col">
          {here.map((child) => (
            <Link
              key={child.id}
              to={`/families/${family.id}`}
              className="font-bold text-ink hover:text-lake hover:underline"
            >
              {studentName(child)}
            </Link>
          ))}
          {others.map((child) => (
            <small key={child.id} className="text-ink-3">
              {t("students.invitations.otherClass", {
                name: studentName(child),
                class: child.class_group_name,
              })}
            </small>
          ))}
        </span>
      </td>
      <td>
        <span className="flex flex-col">
          {primary?.full_name ?? t("common.none")}
          {primary?.phone ? (
            <small className="whitespace-nowrap text-ink-3 tabular-nums">
              {formatPhone(primary.phone)}
            </small>
          ) : (
            <small className="text-due">{t("students.invitations.noPhone")}</small>
          )}
        </span>
      </td>
      <td>
        <StatusPill tone={TONES[status]}>
          {status === "activated" && family.activated_at
            ? t("students.invitations.status.activated", { date: date(family.activated_at) })
            : status === "code_expired" && family.code_expires_at
              ? t("students.invitations.status.code_expired", {
                  date: date(family.code_expires_at),
                })
              : t(`students.invitations.status.${status}`)}
        </StatusPill>
      </td>
      {editor && (
        <td>
          {status === "pending" && (
            <span className="flex flex-wrap justify-end gap-1.5">
              <InvitationActions familyId={family.id} name={familyName(family)} />
            </span>
          )}
        </td>
      )}
    </tr>
  );
}
