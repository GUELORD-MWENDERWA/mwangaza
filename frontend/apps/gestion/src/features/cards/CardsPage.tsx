// Cartes des élèves et du personnel (lot 10, 6.1 · A.5, maquette `cartes.html`) : qui a une carte,
// qui n'en a pas, qui doit la réimprimer ; émission (le PDF s'ouvre aussitôt : le jeton du QR n'est
// jamais gardé), carte perdue ou départ (révoquée à tous les pointages), modèle de la carte.
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardFooter,
  CardHeader,
  CardTitle,
  Checkbox,
  ConfirmDialog,
  Icon,
  Input,
  Kpi,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@mwangaza/ui";
import type { Schemas } from "@mwangaza/api";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { useSettled } from "../../lib/settled";
import { useClasses, useYears } from "../organisation/data";
import { Pagination } from "../shell/Pagination";
import { LoadError } from "../status/StatusPages";
import { CardModelTab } from "./CardModelTab";
import {
  type CardFilter,
  type CardLayout,
  type CardListQuery,
  type CardStaff,
  type CardStudent,
  useCardStaff,
  useCardStudents,
  useCardSummary,
  usePrintCards,
  useRevokeCard,
} from "./data";

const PAGE_SIZE = 50;
const NO_FILTER: CardListQuery = { search: "", classGroup: "", card: "" };

type Row = {
  /** Identifiant à envoyer à l'impression (`student` ou `member`). */
  id: string;
  name: string;
  detail: string;
  card: CardStudent["card"];
  lastRevoked: CardStudent["last_revoked"];
  photo: string | null;
  needsReprint: boolean;
};

const studentRow = (item: CardStudent): Row => ({
  id: item.student,
  name: item.name,
  detail: `${item.class_name} · ${item.matricule}`,
  card: item.card,
  lastRevoked: item.last_revoked,
  photo: item.photo,
  needsReprint: item.needs_reprint,
});

const staffRow = (item: CardStaff): Row => ({
  id: item.member,
  name: item.name,
  detail: item.title || item.roles.join(", "),
  card: item.card,
  lastRevoked: item.last_revoked,
  photo: item.photo,
  needsReprint: item.needs_reprint,
});

export function CardsPage() {
  const { t } = useTranslation();
  const summary = useCardSummary();
  const [tab, setTab] = useState("students");
  const data = summary.data;
  return (
    <>
      <PageHeader title={t("cards.title")} subtitle={t("cards.subtitle")} />
      <div className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(min(100%,180px),1fr))] gap-4">
        <Kpi
          label={t("cards.kpi.active")}
          value={data?.active ?? "–"}
          sub={data ? t("cards.kpi.activeSub", { count: data.students }) : undefined}
        />
        <Kpi
          label={t("cards.kpi.missing")}
          value={data?.missing ?? "–"}
          tone={data && data.missing > 0 ? "due" : undefined}
          sub={t("cards.kpi.missingSub")}
        />
        <Kpi
          label={t("cards.kpi.lost")}
          value={data?.lost_this_year ?? "–"}
          sub={t("cards.kpi.lostSub")}
        />
        <Kpi
          label={t("cards.kpi.reprint")}
          value={data?.to_reprint ?? "–"}
          tone={data && data.to_reprint > 0 ? "warn" : undefined}
          sub={t("cards.kpi.reprintSub")}
        />
      </div>
      <Tabs value={tab} onValueChange={setTab} className="mt-4">
        <TabsList>
          <TabsTrigger value="students">{t("cards.tabs.students")}</TabsTrigger>
          <TabsTrigger value="staff">{t("cards.tabs.staff")}</TabsTrigger>
          <TabsTrigger value="model">{t("cards.tabs.model")}</TabsTrigger>
        </TabsList>
        <TabsContent value="students">
          <CardList kind="students" toReprint={data?.to_reprint ?? 0} />
        </TabsContent>
        <TabsContent value="staff">
          <CardList kind="staff" toReprint={data?.to_reprint ?? 0} />
        </TabsContent>
        <TabsContent value="model">
          <CardModelTab />
        </TabsContent>
      </Tabs>
    </>
  );
}

function CardList({ kind, toReprint }: { kind: "students" | "staff"; toReprint: number }) {
  const { t } = useTranslation();
  const students = kind === "students";
  const [filter, setFilter] = useState<CardListQuery>(NO_FILTER);
  const [page, setPage] = useState(1);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [layout, setLayout] = useState<CardLayout>("sheet");
  const [pending, setPending] = useState<Schemas["CardPrintRequest"] | null>(null);
  const [revoking, setRevoking] = useState<Row | null>(null);
  const [reason, setReason] = useState<Schemas["ReasonEnum"]>("lost");
  const settled = { ...filter, search: useSettled(filter.search.trim()) };
  const studentList = useCardStudents(settled, page);
  const staffList = useCardStaff(settled, page);
  const list = students ? studentList : staffList;
  const years = useYears();
  const year = years.data?.find((candidate) => candidate.is_current)?.id ?? "";
  const classes = useClasses(students ? year : "");
  const print = usePrintCards();
  const revoke = useRevokeCard();

  const rows: Row[] = students
    ? (studentList.data?.results ?? []).map(studentRow)
    : (staffList.data?.results ?? []).map(staffRow);
  const count = list.data?.count ?? 0;
  const from = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const change = (patch: Partial<CardListQuery>) => {
    setFilter((current) => ({ ...current, ...patch }));
    setPage(1);
  };
  const pageIds = rows.map((row) => row.id);
  const allChosen = pageIds.length > 0 && pageIds.every((id) => chosen.has(id));
  const toggle = (id: string, on: boolean) =>
    setChosen((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  const className = classes.data?.find((group) => group.id === filter.classGroup)?.name;

  const selection = (): Schemas["CardPrintRequest"] => ({
    ...(students ? { students: [...chosen] } : { members: [...chosen] }),
    missing_only: false,
    layout,
  });
  const whole = (): Schemas["CardPrintRequest"] => ({
    class_group: filter.classGroup,
    missing_only: false,
    layout,
  });
  const missing = (): Schemas["CardPrintRequest"] => ({
    missing: students ? "students" : "staff",
    missing_only: false,
    layout,
  });
  const reprint = (): Schemas["CardPrintRequest"] => ({
    missing: "reprint",
    missing_only: false,
    layout,
  });

  const emit = () => {
    if (!pending) return;
    print.mutate(pending, {
      onSuccess: (result) => {
        setChosen(new Set());
        // Le PDF contient les jetons : on l'ouvre tout de suite (le lien reste dans le message).
        window.open(result.url, "_blank", "noopener");
      },
      onSettled: () => setPending(null),
    });
  };

  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          label={t("cards.layout.label")}
          value={layout}
          onValueChange={setLayout}
          options={[
            { value: "sheet", label: t("cards.layout.sheet") },
            { value: "card", label: t("cards.layout.card") },
          ]}
        />
        <Button
          variant="outline"
          disabled={chosen.size === 0}
          onClick={() => setPending(selection())}
        >
          <Icon name="print" size={16} />
          {t("cards.actions.printSelection", { count: chosen.size })}
        </Button>
        <Button onClick={() => setPending(missing())}>
          <Icon name="plus" size={16} />
          {t("cards.actions.issueMissing")}
        </Button>
        {toReprint > 0 && (
          <Button variant="outline" onClick={() => setPending(reprint())}>
            {t("cards.actions.reprint", { count: toReprint })}
          </Button>
        )}
      </div>
      {print.isError && <Banner tone="due">{errorMessage(print.error, t)}</Banner>}
      {print.isSuccess && (
        <Banner tone="info">
          <span>
            {t("cards.printed.done", { count: print.data.issued })}{" "}
            <a
              className="font-bold underline"
              href={print.data.url}
              target="_blank"
              rel="noreferrer"
            >
              {t("cards.printed.open")}
            </a>
            {print.data.without_photo > 0 && (
              <> {t("cards.printed.withoutPhoto", { count: print.data.without_photo })}</>
            )}
            {print.data.remaining > 0 && (
              <> {t("cards.printed.remaining", { count: print.data.remaining })}</>
            )}
          </span>
        </Banner>
      )}
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <CardTitle>
            {t(students ? "cards.list.students" : "cards.list.staff", { count })}
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            <Input
              aria-label={t("cards.filter.search")}
              placeholder={t("cards.filter.search")}
              value={filter.search}
              onChange={(event) => change({ search: event.target.value })}
            />
            {students && (
              <Select
                aria-label={t("cards.filter.class")}
                value={filter.classGroup}
                onChange={(event) => change({ classGroup: event.target.value })}
              >
                <option value="">{t("cards.filter.allClasses")}</option>
                {(classes.data ?? []).map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </Select>
            )}
            <Select
              aria-label={t("cards.filter.card")}
              value={filter.card}
              onChange={(event) => change({ card: event.target.value as CardFilter })}
            >
              <option value="">{t("cards.filter.anyCard")}</option>
              <option value="active">{t("cards.filter.active")}</option>
              <option value="none">{t("cards.filter.none")}</option>
            </Select>
          </div>
        </CardHeader>
        {list.isPending ? (
          <Skeleton label={t("common.loading")} />
        ) : rows.length === 0 ? (
          <p className="px-[18px] py-6 text-ink-3">{t("cards.list.empty")}</p>
        ) : (
          <Table stacked>
            <thead>
              <tr>
                <th>
                  <Checkbox
                    aria-label={t("cards.list.selectPage")}
                    checked={allChosen}
                    onCheckedChange={(on) =>
                      setChosen((current) => {
                        const next = new Set(current);
                        for (const id of pageIds) {
                          if (on === true) next.add(id);
                          else next.delete(id);
                        }
                        return next;
                      })
                    }
                  />
                </th>
                <th>{t(students ? "cards.columns.student" : "cards.columns.member")}</th>
                <th>{t("cards.columns.photo")}</th>
                <th>{t("cards.columns.card")}</th>
                <th>{t("cards.columns.token")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} aria-selected={chosen.has(row.id)}>
                  <td>
                    <Checkbox
                      aria-label={t("cards.list.select", { name: row.name })}
                      checked={chosen.has(row.id)}
                      onCheckedChange={(on) => toggle(row.id, on === true)}
                    />
                  </td>
                  <td data-label={t(students ? "cards.columns.student" : "cards.columns.member")}>
                    <b>{row.name}</b>
                    <br />
                    <span className="text-sm text-ink-3">{row.detail}</span>
                  </td>
                  <td data-label={t("cards.columns.photo")}>
                    {row.photo ? (
                      <img
                        src={row.photo}
                        alt=""
                        loading="lazy"
                        className="h-10 w-8 rounded object-cover"
                      />
                    ) : (
                      <StatusPill tone="warn">{t("cards.photo.missing")}</StatusPill>
                    )}
                  </td>
                  <td data-label={t("cards.columns.card")}>
                    <CardState row={row} />
                  </td>
                  <td data-label={t("cards.columns.token")} className="text-ink-3">
                    {row.card ? `•••• ${row.card.last4}` : "—"}
                  </td>
                  <td>
                    {row.card && (
                      <Button
                        variant="destructive-outline"
                        size="sm"
                        onClick={() => {
                          setReason("lost");
                          setRevoking(row);
                        }}
                      >
                        {t("cards.actions.revoke")}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
        <CardFooter className="flex-wrap gap-2 p-0">
          <div className="flex w-full flex-wrap items-center gap-3 px-[18px] pt-3 text-sm">
            <span>{t("cards.list.chosen", { count: chosen.size })}</span>
            {students && filter.classGroup && className && (
              <Button variant="ghost" size="sm" onClick={() => setPending(whole())}>
                {t("cards.actions.wholeClass", { name: className })}
              </Button>
            )}
            {chosen.size > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setChosen(new Set())}>
                {t("cards.list.clear")}
              </Button>
            )}
          </div>
          <Pagination
            summary={t("cards.list.range", {
              from,
              to: from + rows.length - (rows.length ? 1 : 0),
              count,
            })}
            page={page}
            hasPrevious={Boolean(list.data?.previous)}
            hasNext={Boolean(list.data?.next)}
            onPage={setPage}
          />
        </CardFooter>
      </Card>
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title={t("cards.confirm.title")}
        confirmLabel={t("cards.confirm.issue")}
        cancelLabel={t("common.cancel")}
        pending={print.isPending}
        onConfirm={emit}
      >
        <p className="text-sm text-ink-2">{t("cards.confirm.text")}</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={revoking !== null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title={t("cards.revoke.title", { name: revoking?.name ?? "" })}
        confirmLabel={t("cards.revoke.confirm")}
        cancelLabel={t("common.cancel")}
        destructive
        pending={revoke.isPending}
        onConfirm={() =>
          revoking?.card &&
          revoke.mutate({ id: revoking.card.id, reason }, { onSuccess: () => setRevoking(null) })
        }
      >
        <p className="text-sm text-ink-2">{t("cards.revoke.text")}</p>
        <Select
          aria-label={t("cards.revoke.reason")}
          value={reason}
          onChange={(event) => setReason(event.target.value as Schemas["ReasonEnum"])}
        >
          <option value="lost">{t("cards.revoke.lost")}</option>
          <option value="left">{t("cards.revoke.left")}</option>
        </Select>
        {revoke.isError && <Banner tone="due">{errorMessage(revoke.error, t)}</Banner>}
      </ConfirmDialog>
    </div>
  );
}

function CardState({ row }: { row: Row }) {
  const { t } = useTranslation();
  if (row.card) {
    return row.needsReprint ? (
      <StatusPill tone="warn">{t("cards.state.reprint")}</StatusPill>
    ) : (
      <StatusPill tone="ok">{t("cards.state.active")}</StatusPill>
    );
  }
  if (row.lastRevoked) {
    return (
      <StatusPill tone="warn">
        {t(row.lastRevoked.revoke_reason === "left" ? "cards.state.left" : "cards.state.lost")}
      </StatusPill>
    );
  }
  return <StatusPill tone="due">{t("cards.state.none")}</StatusPill>;
}
