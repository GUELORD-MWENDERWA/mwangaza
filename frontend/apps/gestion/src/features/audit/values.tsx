// Détail d'une entrée du journal (M6) : champs changés et leurs valeurs, traduits. Le serveur n'y
// met jamais de mot de passe, de code ni de clé.
import type { Schemas } from "@mwangaza/api";
import { formatDateTime, formatDay, fr, type TFunction } from "@mwangaza/i18n";
import { type Currency, formatAmount } from "@mwangaza/money";
import type { ReactNode } from "react";

import { snapshotTree, termLabels, type TermKind } from "../../lib/terms";

type Log = Schemas["AuditLog"];
type Tone = "ok" | "due" | "warn" | "info" | "gray";

/** Toutes les actions du journal, par domaine, d'après leurs traductions. */
export const ACTIONS = Object.entries(fr.audit.actions).flatMap(([domain, events]) =>
  Object.keys(events).map((event) => `${domain}.${event}` as Log["action"]),
);
export const DOMAINS = Object.keys(fr.audit.domains) as Log["domain"][];

/** Couleur de la pastille (toujours avec son texte). */
export function actionTone(action: string): Tone {
  if (action.startsWith("support.")) return "warn";
  if (/(deleted|deactivated|suspended|totp_disabled|totp_reset)$/.test(action)) return "due";
  if (/(created|added|reactivated|totp_enabled)$/.test(action)) return "ok";
  if (action === "auth.login") return "info";
  return "gray";
}

export function fieldLabel(field: string, t: TFunction): string {
  return field in fr.audit.fields
    ? t(`audit.fields.${field as keyof typeof fr.audit.fields}`)
    : field;
}

const currency = (code: unknown) => (code === "CDF" ? "FC" : String(code));

type ClosingLine = {
  currency: Currency;
  expected_minor: number;
  counted_minor: number;
  difference_minor: number;
};

type Snapshot = {
  kind: TermKind;
  name: string;
  parent: number | null;
  starts_on: string | null;
  ends_on: string | null;
};

function Terms({ terms, t, language }: { terms: Snapshot[]; t: TFunction; language: string }) {
  const tree = snapshotTree(terms);
  const labels = termLabels(tree, t);
  const day = (value: string | null) => (value ? formatDay(value, language) : t("common.none"));
  return (
    <ul className="flex flex-col gap-0.5">
      {tree
        .flatMap((node) => [node, ...(node.children ?? [])])
        .map((node) => {
          const term = terms[(node as { index: number }).index]!;
          return (
            <li
              key={(node as { index: number }).index}
              className={node.kind === "period" || node.kind === "exam" ? "pl-3" : ""}
            >
              {labels.get(node)} : {day(term.starts_on)} → {day(term.ends_on)}
            </li>
          );
        })}
    </ul>
  );
}

/** Valeur lisible d'un champ du journal. */
export function renderValue(
  field: string,
  value: unknown,
  t: TFunction,
  language: string,
  timeZone: string,
): ReactNode {
  if (value === null || value === undefined || value === "") return t("audit.values.none");
  if (typeof value === "boolean") return value ? t("audit.values.yes") : t("audit.values.no");
  switch (field) {
    case "permissions":
      return (value as string[])
        .map((code) =>
          t(`permissions.codes.${code}` as "permissions.codes.students.view", {
            defaultValue: code,
          }),
        )
        .join(", ");
    case "roles":
      // Nom vide : rôle noté sans nom avant M.3.2, et supprimé depuis.
      return (value as Schemas["RoleSummary"][])
        .map((role) => role.name || t("roles.deleted"))
        .join(", ");
    case "second_factor":
      return String(value) in fr.audit.values
        ? t(`audit.values.${value as "totp"}`)
        : String(value);
    case "audience":
      return t(`announcements.audiences.${value as "all_families"}`);
    case "class_groups":
      return (value as string[]).join(", ");
    case "cycle":
      return t(`cycles.${value as "basic"}`);
    case "template":
      return t(`organisation.templates.${value as "secondary"}`);
    case "enabled_currencies":
      return (value as string[]).map(currency).join(", ");
    case "default_currency":
      return currency(value);
    case "receipt_printer":
      return t(`settings.receipt.printers.${value as "sheet"}`, { defaultValue: String(value) });
    case "receipt_sheet_size":
      return t(`settings.receipt.sheetSizes.${value as "a6"}`, { defaultValue: String(value) });
    case "starts_on":
    case "ends_on":
    case "birth_date":
    case "left_on":
      return formatDay(String(value), language);
    case "sex":
      return t(value === "F" ? "students.new.female" : "students.new.male");
    case "status":
      return t(`students.enrollmentStatus.${value as "active"}`, { defaultValue: String(value) });
    case "address":
      return (
        Object.values(value as Record<string, string>)
          .filter(Boolean)
          .join(", ") || t("audit.values.none")
      );
    case "guardians":
      return (value as { full_name: string; relationship: string; phone: string }[])
        .map((guardian) =>
          [
            guardian.full_name,
            t(`students.relationships.${guardian.relationship as "mother"}`),
            guardian.phone,
          ]
            .filter(Boolean)
            .join(", "),
        )
        .join(" ; ");
    case "expires_at":
      return formatDateTime(String(value), language, timeZone);
    case "levels":
      return (value as string[]).join(" · ");
    case "terms":
      return <Terms terms={value as Snapshot[]} t={t} language={language} />;
    case "amounts":
      // Clôture de caisse (3.8.2) : une ligne par devise, jamais additionnées.
      return (
        <ul className="flex flex-col gap-0.5">
          {(value as ClosingLine[]).map((line) => {
            const money = (minor: number) => formatAmount(minor, line.currency);
            return (
              <li key={line.currency}>
                {t("audit.values.closingLine", {
                  currency: currency(line.currency),
                  expected: money(line.expected_minor),
                  counted: money(line.counted_minor),
                  difference: money(line.difference_minor),
                })}
              </li>
            );
          })}
        </ul>
      );
    case "primary_color":
      return (
        <span className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block size-3.5 rounded-[4px] border border-line"
            style={{ backgroundColor: String(value) }}
          />
          {String(value)}
        </span>
      );
  }
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
