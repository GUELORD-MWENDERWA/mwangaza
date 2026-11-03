// Dérogations de bulletin (8.4.6, maquette `derogations-bulletin`) : un élève ou une famille reçoit
// son bulletin sur le Portail malgré des frais échus impayés, jusqu'à la date fixée. Jamais
// modifiée : « Lever » est le seul changement. Droit `grades.waive_fees` (vérifié par le serveur).
import { formatDay, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  PageHeader,
  Segmented,
  Skeleton,
  StatusPill,
  Table,
  Tag,
} from "@mwangaza/ui";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { studentName } from "../../lib/people";
import { useSettled } from "../../lib/settled";
import { LoadError } from "../status/StatusPages";
import { familyName, useFamilySearch, useStudentSearch } from "../students/data";
import { useGrant, useLift, useWaivers, type Waiver } from "./data";

const SHOWN = 6;
type Target = { kind: "student" | "family"; id: string; name: string };

export function WaiversPage() {
  const { t } = useTranslation();
  const [onlyActive, setOnlyActive] = useState(true);
  const list = useWaivers(onlyActive);
  if (list.isError && !list.data) {
    return <LoadError error={list.error} onRetry={() => void list.refetch()} />;
  }
  return (
    <>
      <PageHeader
        title={t("waivers.title")}
        subtitle={t("waivers.subtitle")}
        actions={
          <Segmented
            label={t("waivers.filter")}
            value={onlyActive ? "active" : "all"}
            onValueChange={(next) => setOnlyActive(next === "active")}
            options={[
              { value: "active", label: t("waivers.active") },
              { value: "all", label: t("waivers.all") },
            ]}
          />
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          {!list.data ? (
            <CardContent>
              <Skeleton label={t("common.loading")} />
            </CardContent>
          ) : list.data.results.length === 0 ? (
            <CardContent className="text-ink-3">{t("waivers.empty")}</CardContent>
          ) : (
            <WaiverTable items={list.data.results} />
          )}
        </Card>
        <GrantForm />
      </div>
    </>
  );
}

function WaiverTable({ items }: { items: Waiver[] }) {
  const { t, i18n } = useTranslation();
  const lift = useLift();
  return (
    <>
      {lift.isError && <Banner tone="due">{errorMessage(lift.error, t)}</Banner>}
      <Table>
        <thead>
          <tr>
            <th>{t("waivers.columns.target")}</th>
            <th>{t("waivers.columns.reason")}</th>
            <th>{t("waivers.columns.until")}</th>
            <th>{t("waivers.columns.by")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((waiver) => (
            <tr key={waiver.id}>
              <td>
                <b>{waiver.target_name}</b>
                <span className="block text-sm text-ink-3">
                  {waiver.student ? t("waivers.student") : t("waivers.family")}
                </span>
              </td>
              <td className="text-sm">{waiver.reason}</td>
              <td className="text-sm tabular-nums">{formatDay(waiver.until, i18n.language)}</td>
              <td className="text-sm">
                {waiver.granted_by_name}
                <span className="block text-ink-3 tabular-nums">
                  {formatDay(waiver.created_at.slice(0, 10), i18n.language)}
                </span>
              </td>
              <td>
                {waiver.active ? (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={lift.isPending}
                    onClick={() => lift.mutate(waiver.id)}
                  >
                    {t("waivers.lift")}
                  </Button>
                ) : (
                  <StatusPill tone="gray">
                    {waiver.lifted_at ? t("waivers.lifted") : t("waivers.expired")}
                  </StatusPill>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </>
  );
}

function GrantForm() {
  const { t } = useTranslation();
  const [kind, setKind] = useState<Target["kind"]>("student");
  const [target, setTarget] = useState<Target | null>(null);
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");
  const [until, setUntil] = useState("");
  const settled = useSettled(search.trim());
  const students = useStudentSearch(target || kind !== "student" ? "" : settled);
  const families = useFamilySearch(target || kind !== "family" ? "" : settled);
  const grant = useGrant();

  const found: Target[] =
    settled.length < 2
      ? []
      : kind === "student"
        ? (students.data?.results ?? [])
            .slice(0, SHOWN)
            .map((s) => ({ kind, id: s.id, name: studentName(s) }))
        : (families.data?.results ?? [])
            .slice(0, SHOWN)
            .map((f) => ({ kind, id: f.id, name: familyName(f) }));

  const submit = () => {
    if (!target) return;
    grant.mutate(
      { [target.kind]: target.id, reason: reason.trim(), until },
      {
        onSuccess: () => {
          setTarget(null);
          setReason("");
          setUntil("");
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("waivers.grant")}</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          {grant.isError && <Banner tone="due">{errorMessage(grant.error, t)}</Banner>}
          <Segmented
            label={t("waivers.for")}
            value={kind}
            onValueChange={(next) => {
              setKind(next);
              setTarget(null);
              setSearch("");
            }}
            options={[
              { value: "student", label: t("waivers.student") },
              { value: "family", label: t("waivers.family") },
            ]}
          />
          <Field id="waiver-target" label={t(`waivers.pick_${kind}`)}>
            {(control) =>
              target ? (
                <Tag className="inline-flex w-fit items-center gap-1">
                  {target.name}
                  <button
                    type="button"
                    aria-label={t("waivers.clear")}
                    onClick={() => setTarget(null)}
                  >
                    ×
                  </button>
                </Tag>
              ) : (
                <>
                  <Input
                    {...control}
                    type="search"
                    placeholder={t("waivers.search")}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                  <ul className="flex flex-col rounded-field border border-line empty:hidden">
                    {found.map((item) => (
                      <li key={item.id} className="border-t border-line first:border-t-0">
                        <button
                          type="button"
                          className="min-h-11 w-full px-3 py-2 text-left font-bold hover:bg-surface"
                          onClick={() => {
                            setTarget(item);
                            setSearch("");
                          }}
                        >
                          {item.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )
            }
          </Field>
          <Field id="waiver-reason" label={t("waivers.columns.reason")}>
            {(control) => (
              <Input
                {...control}
                maxLength={300}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
          <Field id="waiver-until" label={t("waivers.columns.until")}>
            {(control) => (
              <Input
                {...control}
                type="date"
                value={until}
                onChange={(event) => setUntil(event.target.value)}
              />
            )}
          </Field>
          <Button type="submit" disabled={grant.isPending || !target || !reason.trim() || !until}>
            {t("waivers.submit")}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
