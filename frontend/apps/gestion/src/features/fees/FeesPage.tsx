// Frais et barèmes (E1, E2, E5, maquette `frais-baremes`) : types de frais, barèmes de l'année
// pour le type choisi, éditeur de barème, taux de l'année. Écriture : `finance.configure_fees`
// (types, barèmes) et `finance.set_exchange_rate` (taux) ; le serveur vérifie de son côté.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { formatAmount, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  cn,
  Icon,
  PageHeader,
  Select,
  Skeleton,
  Switch,
  Table,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { useLevels, useRefresh, useYears, type Year } from "../organisation/data";
import { LoadError } from "../status/StatusPages";
import { useFeeRules, useFeeTypes, type FeeRule, type FeeType } from "./data";
import { FeeTypeDialog } from "./FeeTypeDialog";
import { RateCard } from "./RateCard";
import { RuleEditor } from "./RuleEditor";

export function FeesPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const canConfigure = can(me, ["finance.configure_fees"]);
  const years = useYears();
  const types = useFeeTypes();
  const [chosenYear, setChosenYear] = useState<string | null>(null);
  const [chosenType, setChosenType] = useState<string | null>(null);
  const [typeDialog, setTypeDialog] = useState<FeeType | "new" | null>(null);
  const [editing, setEditing] = useState<FeeRule | "new" | null>(null);

  if (years.isPending || types.isPending) return <Skeleton label={t("common.loading")} />;
  if (years.isError) return <LoadError error={years.error} onRetry={() => void years.refetch()} />;
  if (types.isError) return <LoadError error={types.error} onRetry={() => void types.refetch()} />;

  const year =
    years.data.find((item) => item.id === chosenYear) ??
    years.data.find((item) => item.is_current) ??
    years.data[0];
  const type = types.data.find((item) => item.id === chosenType) ?? types.data[0];

  return (
    <>
      <PageHeader
        title={t("fees.title")}
        subtitle={year && t("fees.subtitle", { year: year.name })}
        actions={
          <>
            {years.data.length > 1 && year && (
              <Select
                aria-label={t("organisation.yearChoice")}
                value={year.id}
                onChange={(event) => {
                  setChosenYear(event.target.value);
                  setEditing(null);
                }}
                className="w-auto min-w-[200px]"
              >
                {years.data.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.is_current
                      ? t("organisation.yearOptionCurrent", { name: item.name })
                      : t("organisation.yearOption", { name: item.name })}
                  </option>
                ))}
              </Select>
            )}
            {canConfigure && (
              <Button variant="outline" onClick={() => setTypeDialog("new")}>
                <Icon name="plus" size={16} />
                {t("fees.newType")}
              </Button>
            )}
            {canConfigure && year && type && (
              <Button onClick={() => setEditing("new")}>
                <Icon name="plus" size={16} />
                {t("fees.newRule")}
              </Button>
            )}
          </>
        }
      />
      {!year ? (
        <Banner tone="info">{t("fees.noYear")}</Banner>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1200px]:grid-cols-[300px_minmax(0,1fr)_300px]">
          <FeeTypesCard
            types={types.data}
            selected={type?.id}
            onSelect={(id) => {
              setChosenType(id);
              setEditing(null);
            }}
          />
          <div className="flex min-w-0 flex-col gap-4">
            {type && (
              <RulesCard
                year={year}
                type={type}
                canConfigure={canConfigure}
                onEditType={() => setTypeDialog(type)}
                onEditRule={setEditing}
              />
            )}
            {canConfigure && type && editing && (
              <RuleEditor
                key={`${type.id}-${editing === "new" ? "new" : editing.id}`}
                year={year}
                type={type}
                rule={editing === "new" ? null : editing}
                onClose={() => setEditing(null)}
              />
            )}
          </div>
          <RateCard year={year} />
        </div>
      )}
      <FeeTypeDialog
        value={typeDialog}
        onClose={() => setTypeDialog(null)}
        onSaved={(saved) => setChosenType(saved.id)}
        onDeleted={() => setChosenType(null)}
      />
    </>
  );
}

function FeeTypesCard({
  types,
  selected,
  onSelect,
}: {
  types: FeeType[];
  selected: string | undefined;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("fees.types.title")}</CardTitle>
      </CardHeader>
      {types.length === 0 ? (
        <CardContent className="text-ink-3">{t("fees.types.empty")}</CardContent>
      ) : (
        <CardContent className="flex flex-col gap-1">
          {types.map((type) => (
            <button
              key={type.id}
              type="button"
              aria-pressed={type.id === selected}
              onClick={() => onSelect(type.id)}
              className={cn(
                "flex flex-col items-start rounded-[10px] border border-transparent px-3.5 py-3 text-left",
                type.id === selected ? "border-lake/25 bg-lake-50" : "hover:bg-gray-50",
              )}
            >
              <span className="font-bold">{type.name}</span>
              <span className="text-sm text-ink-3">
                {type.funds_teacher_bonus
                  ? t("fees.types.bonus")
                  : t(`fees.categories.${type.category}`)}
                {!type.is_active && ` · ${t("fees.types.inactive")}`}
              </span>
            </button>
          ))}
        </CardContent>
      )}
    </Card>
  );
}

// Toute l'école, puis les niveaux dans l'ordre de l'école, les options, les classes.
const SCOPE_ORDER = (rule: FeeRule) => (rule.class_group ? 3 : rule.track ? 2 : rule.level ? 1 : 0);

function RulesCard({
  year,
  type,
  canConfigure,
  onEditType,
  onEditRule,
}: {
  year: Year;
  type: FeeType;
  canConfigure: boolean;
  onEditType: () => void;
  onEditRule: (rule: FeeRule) => void;
}) {
  const { t } = useTranslation();
  const rules = useFeeRules(year.id);
  const levels = useLevels();
  const refresh = useRefresh();
  const toggle = useMutation({
    mutationFn: (is_active: boolean) =>
      call(
        api.PATCH("/api/fee-types/{id}/", {
          params: { path: { id: type.id } },
          body: { is_active },
        }),
      ),
    onSuccess: () => refresh(keys.feeTypes),
  });
  const details = [
    t("fees.type.category", { category: t(`fees.categories.${type.category}`) }),
    type.accounting_code && t("fees.type.account", { code: type.accounting_code }),
    type.funds_teacher_bonus && t("fees.types.bonus"),
  ].filter(Boolean);
  const levelOrder = new Map((levels.data ?? []).map((level) => [level.id, level.order]));
  const list = (rules.data ?? [])
    .filter((rule) => rule.fee_type === type.id)
    .sort(
      (a, b) =>
        SCOPE_ORDER(a) - SCOPE_ORDER(b) ||
        (levelOrder.get(a.level ?? "") ?? 0) - (levelOrder.get(b.level ?? "") ?? 0) ||
        a.scope_name.localeCompare(b.scope_name, undefined, { numeric: true }),
    );

  return (
    <Card>
      <CardHeader className="items-start">
        <div className="min-w-0">
          <CardTitle>{t("fees.type.heading", { name: type.name, year: year.name })}</CardTitle>
          <p className="text-sm text-ink-3">{details.join(" · ")}</p>
        </div>
        {canConfigure && (
          <div className="flex shrink-0 items-center gap-2">
            <Switch
              aria-label={t("fees.type.active")}
              checked={type.is_active}
              disabled={toggle.isPending}
              onCheckedChange={(checked) => toggle.mutate(checked)}
            />
            <Button variant="ghost" size="sm" onClick={onEditType}>
              <Icon name="edit" size={16} />
              {t("common.edit")}
            </Button>
          </div>
        )}
      </CardHeader>
      {toggle.isError && (
        <CardContent>
          <Banner tone="due">{errorMessage(toggle.error, t)}</Banner>
        </CardContent>
      )}
      {rules.isPending ? (
        <CardContent>
          <Skeleton label={t("common.loading")} />
        </CardContent>
      ) : rules.isError ? (
        <CardContent>
          <LoadError error={rules.error} onRetry={() => void rules.refetch()} />
        </CardContent>
      ) : list.length === 0 ? (
        <CardContent className="text-ink-3">
          {t("fees.rules.empty", { year: year.name })}
        </CardContent>
      ) : (
        <Table>
          <thead>
            <tr>
              <th>{t("fees.rules.scope")}</th>
              <th className="text-right">{t("fees.rules.total")}</th>
              <th className="text-right">{t("fees.rules.split")}</th>
              {canConfigure && <th />}
            </tr>
          </thead>
          <tbody>
            {list.map((rule) => (
              <tr key={rule.id}>
                <td>{rule.scope_name || t("fees.rules.wholeSchool")}</td>
                <td className="num font-bold">
                  {formatAmount(rule.total_amount_minor, rule.currency as Currency)}
                </td>
                <td className="num">
                  <Split rule={rule} />
                </td>
                {canConfigure && (
                  <td className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => onEditRule(rule)}>
                      {t("common.edit")}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

/** « 3 × 120,00 $ », « 10 mois », « En une fois », « 3 tranches ». */
function Split({ rule }: { rule: FeeRule }) {
  const { t } = useTranslation();
  const count = rule.installments.length;
  if (rule.schedule_kind === "single") return t("fees.rules.single");
  if (rule.schedule_kind === "monthly") return t("fees.rules.monthly", { count });
  const [first] = rule.installments;
  if (first && rule.installments.every((item) => item.amount_minor === first.amount_minor)) {
    return `${count} × ${formatAmount(first.amount_minor, rule.currency as Currency)}`;
  }
  return t("fees.rules.installments", { count });
}
