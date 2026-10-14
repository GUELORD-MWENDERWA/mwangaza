// Liste des élèves (D2) : recherche (noms, matricule, code famille, sans accents ni casse) et
// filtres année, classe, option, statut ; liste paginée par le serveur ; le nom ouvre la fiche.
// Import : 2.3 ; export et sélection : 2.4 ; « Échu non payé », « Paiements » et leur filtre
// (4.1.2), avec un droit de lecture des frais ; recherche hors-ligne (IndexedDB) : 3.x.
import { useTranslation } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import {
  Avatar,
  Button,
  Card,
  CardContent,
  Icon,
  Input,
  PageHeader,
  Select,
  Skeleton,
  StatusPill,
  Table,
  initials,
} from "@mwangaza/ui";
import { useState } from "react";
import { Link } from "react-router";

import { formatPhone, studentName } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe } from "../../lib/queries";
import { useSettled } from "../../lib/settled";
import { useClasses, useTracks, useYears } from "../organisation/data";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import {
  CHARGES_READ,
  type Situation,
  type StudentQuery,
  type StudentRow,
  type StudentStatus,
  useStudents,
} from "./data";

const PAGE_SIZE = 50;
const STATUSES: StudentStatus[] = ["active", "left", "not_enrolled"];
const SITUATIONS: Situation[] = ["up_to_date", "partial", "overdue"];
const SITUATION_TONES = { up_to_date: "ok", partial: "warn", overdue: "due" } as const;

type Filters = {
  search: string;
  year: string;
  classGroup: string;
  track: string;
  status: string;
  payment: string;
};
const NO_FILTERS: Filters = {
  search: "",
  year: "",
  classGroup: "",
  track: "",
  status: "active",
  payment: "",
};

export function StudentsPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const finance = can(me, CHARGES_READ);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [page, setPage] = useState(1);
  const years = useYears();
  const tracks = useTracks();
  const currentYear = years.data?.find((year) => year.is_current);
  const yearId = filters.year || currentYear?.id || "";
  const year = years.data?.find((candidate) => candidate.id === yearId);
  const classes = useClasses(yearId);
  const search = useSettled(filters.search.trim());
  const query: StudentQuery = {
    ...(search ? { search } : {}),
    ...(filters.year ? { academic_year: filters.year } : {}),
    ...(filters.classGroup ? { class_group: filters.classGroup } : {}),
    ...(filters.track ? { track: filters.track } : {}),
    ...(filters.status ? { status: filters.status as StudentStatus } : {}),
    ...(finance && filters.payment ? { payment: filters.payment as Situation } : {}),
  };
  const students = useStudents(query, page);
  const change = (field: keyof Filters) => (value: string) => {
    setFilters((current) => ({
      ...current,
      [field]: value,
      ...(field === "year" ? { classGroup: "" } : {}),
    }));
    setPage(1);
  };

  if (students.isError && !students.data) {
    return <LoadError error={students.error} onRetry={() => void students.refetch()} />;
  }
  const results = students.data?.results ?? [];
  const count = students.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const groups = classes.data ?? [];
  const enrolled = groups.reduce((total, group) => total + group.student_count, 0);
  const filtered = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS);

  return (
    <>
      <PageHeader
        title={t("students.list.title")}
        subtitle={
          year && classes.data
            ? `${t("students.list.enrolled", { count: enrolled, year: year.name })} · ${t("students.list.classes", { count: groups.length })}`
            : undefined
        }
        actions={
          <>
            <Button asChild variant="outline">
              <Link
                to={`/students/class-list${filters.classGroup ? `?class=${filters.classGroup}` : ""}`}
              >
                <Icon name="print" size={16} />
                {t("students.print.classList.title")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link
                to={`/students/invitations${filters.classGroup ? `?class=${filters.classGroup}` : ""}`}
              >
                <Icon name="qr" size={16} />
                {t("students.invitations.title")}
              </Link>
            </Button>
            {can(me, ["students.import"]) && (
              <Button asChild variant="outline">
                <Link to="/students/import">
                  <Icon name="upload" size={16} />
                  {t("students.list.importExcel")}
                </Link>
              </Button>
            )}
            {can(me, ["students.edit"]) && (
              <Button asChild>
                <Link to="/students/new">
                  <Icon name="plus" size={16} />
                  {t("students.list.newStudent")}
                </Link>
              </Button>
            )}
          </>
        }
      />
      <Card data-guide="students-search">
        <CardContent
          // Avec le filtre « Paiement », la recherche prend sa propre ligne : six filtres sur une
          // seule couperaient leurs libellés.
          className={`grid gap-2.5 min-[700px]:grid-cols-2 ${finance ? "min-[1200px]:grid-cols-[repeat(5,minmax(0,1fr))_auto]" : "min-[1200px]:grid-cols-[minmax(240px,1.6fr)_repeat(4,minmax(0,1fr))_auto]"}`}
        >
          <div
            className={`relative min-[700px]:col-span-2 ${finance ? "min-[1200px]:col-span-full" : "min-[1200px]:col-span-1"}`}
          >
            <Icon
              name="search"
              size={16}
              className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-ink-3"
            />
            <Input
              type="search"
              aria-label={t("students.list.search")}
              placeholder={t("students.list.search")}
              value={filters.search}
              onChange={(e) => change("search")(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select
            aria-label={t("students.filters.year")}
            value={yearId}
            onChange={(e) =>
              change("year")(e.target.value === currentYear?.id ? "" : e.target.value)
            }
          >
            {(years.data ?? []).map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {t("students.filters.yearOption", { name: candidate.name })}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("students.filters.class")}
            value={filters.classGroup}
            onChange={(e) => change("classGroup")(e.target.value)}
          >
            <option value="">{t("students.filters.allClasses")}</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("students.filters.track")}
            value={filters.track}
            onChange={(e) => change("track")(e.target.value)}
          >
            <option value="">{t("students.filters.allTracks")}</option>
            {(tracks.data ?? []).map((track) => (
              <option key={track.id} value={track.id}>
                {track.name}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("students.filters.status")}
            value={filters.status}
            onChange={(e) => change("status")(e.target.value)}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`students.filters.statuses.${status}`)}
              </option>
            ))}
            <option value="">{t("students.filters.statuses.all")}</option>
          </Select>
          {finance && (
            <Select
              aria-label={t("students.filters.payment")}
              value={filters.payment}
              onChange={(e) => change("payment")(e.target.value)}
            >
              <option value="">{t("students.filters.payments.all")}</option>
              {SITUATIONS.map((situation) => (
                <option key={situation} value={situation}>
                  {t(`students.filters.payments.${situation}`)}
                </option>
              ))}
            </Select>
          )}
          <Button
            variant="ghost"
            disabled={!filtered}
            onClick={() => {
              setFilters(NO_FILTERS);
              setPage(1);
            }}
          >
            {t("students.filters.clear")}
          </Button>
        </CardContent>
      </Card>
      <Card>
        {!students.data ? (
          <CardContent>
            <Skeleton label={t("common.loading")} />
          </CardContent>
        ) : results.length === 0 ? (
          <CardContent className="text-ink-3">
            {t(filtered ? "students.list.empty" : "students.list.emptySchool")}
          </CardContent>
        ) : (
          <StudentTable students={results} finance={finance} />
        )}
        <Pagination
          page={page}
          hasPrevious={Boolean(students.data?.previous)}
          hasNext={Boolean(students.data?.next)}
          onPage={setPage}
          summary={t("students.list.range", {
            from,
            to: from ? from + results.length - 1 : 0,
            count,
          })}
        />
      </Card>
    </>
  );
}

function StudentTable({ students, finance }: { students: StudentRow[]; finance: boolean }) {
  const { t } = useTranslation();
  return (
    <Table>
      <thead>
        <tr>
          <th>{t("students.list.columns.student")}</th>
          <th>{t("students.list.columns.class")}</th>
          <th>{t("students.list.columns.guardian")}</th>
          {finance && <th className="text-right">{t("students.list.columns.overdue")}</th>}
          {finance && <th>{t("students.list.columns.payments")}</th>}
        </tr>
      </thead>
      <tbody>
        {students.map((student) => {
          const { enrollment, primary_guardian: guardian } = student;
          return (
            <tr key={student.id}>
              <td>
                <span className="flex items-center gap-2.5">
                  <Avatar
                    text={initials(student.middle_name || student.first_name, student.last_name)}
                    className="size-8 text-xs"
                  />
                  <span className="flex flex-col">
                    <Link
                      to={`/students/${student.id}`}
                      className="text-md font-bold text-ink hover:text-lake hover:underline"
                    >
                      {studentName(student)}
                    </Link>
                    <small className="text-ink-3 tabular-nums">
                      {student.matricule || t("common.none")}
                    </small>
                  </span>
                </span>
              </td>
              <td className="whitespace-nowrap">
                {enrollment ? (
                  <span className="flex flex-wrap items-center gap-2">
                    {enrollment.class_group_name}
                    {enrollment.status !== "active" && (
                      <StatusPill tone="warn">
                        {t(`students.enrollmentStatus.${enrollment.status}`)}
                      </StatusPill>
                    )}
                  </span>
                ) : (
                  <span className="text-ink-3">{t("students.list.notEnrolled")}</span>
                )}
              </td>
              <td className="text-sm">
                {guardian
                  ? [guardian.full_name, guardian.phone && formatPhone(guardian.phone)]
                      .filter(Boolean)
                      .join(" · ")
                  : t("common.none")}
              </td>
              {finance && <FinanceCells balance={student.finance} />}
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

/** « Échu non payé » par devise, jamais additionné (« 20,00 $ + 30 000 FC »), et la situation. */
function FinanceCells({ balance }: { balance: StudentRow["finance"] }) {
  const { t } = useTranslation();
  if (!balance) return <td colSpan={2} />;
  const overdue = balance.currencies
    .filter((item) => item.overdue_minor > 0)
    .map((item) => formatAmount(item.overdue_minor, item.currency as Currency))
    .join(" + ");
  return (
    <>
      <td
        className={`text-right whitespace-nowrap tabular-nums ${overdue ? "font-bold text-due" : "text-ink-3"}`}
      >
        {overdue || "—"}
      </td>
      <td>
        <StatusPill tone={SITUATION_TONES[balance.situation]}>
          {t(`students.list.situations.${balance.situation}`)}
        </StatusPill>
      </td>
    </>
  );
}
