// Facturation de la plateforme (lot 3, maquette `console/facturation`) : factures et paiements des
// écoles, contrats, offres, conditions. Droit « abonnements et factures » (Finance) ; les offres et
// les conditions se lisent aussi avec « voir les écoles » (le serveur vérifie chaque appel).
import { useTranslation } from "@mwangaza/i18n";
import { PageHeader } from "@mwangaza/ui";
import { useState } from "react";

import { RIGHTS, useCan } from "../../lib/rights";
import { ContractsTab } from "./ContractsTab";
import { InvoicesTab } from "./InvoicesTab";
import { LegalTab } from "./LegalTab";
import { ModuleRequestsTab } from "./ModuleRequestsTab";
import { PlansTab } from "./PlansTab";

const TABS = ["invoices", "contracts", "plans", "requests", "legal"] as const;
type Tab = (typeof TABS)[number];

export function BillingPage() {
  const { t } = useTranslation();
  const can = useCan();
  const manage = can(RIGHTS.billingManage);
  const tabs = TABS.filter((tab) => manage || tab === "plans" || tab === "legal");
  const [tab, setTab] = useState<Tab>(tabs[0]!);
  return (
    <>
      <PageHeader title={t("console.billing.title")} subtitle={t("console.billing.subtitle")} />
      <nav
        className="flex gap-1 overflow-x-auto border-b border-line"
        aria-label={t("console.billing.title")}
      >
        {tabs.map((name) => (
          <button
            key={name}
            type="button"
            aria-current={tab === name ? "page" : undefined}
            onClick={() => setTab(name)}
            className={`-mb-px border-b-[3px] px-3.5 py-2.5 font-bold whitespace-nowrap ${
              tab === name ? "border-lake text-ink" : "border-transparent text-ink-3 hover:text-ink"
            }`}
          >
            {t(`console.billing.tabs.${name}`)}
          </button>
        ))}
      </nav>
      {tab === "invoices" && <InvoicesTab />}
      {tab === "contracts" && <ContractsTab />}
      {tab === "plans" && <PlansTab manage={manage} />}
      {tab === "requests" && <ModuleRequestsTab manage={manage} />}
      {tab === "legal" && <LegalTab manage={manage} />}
    </>
  );
}
