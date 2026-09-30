// Exporter les impayés (G1, M17, maquette `impayes-export`) : les filtres de la liste (dans
// l'adresse) sont repris ; PDF A4 à l'italienne produit par le serveur, par classe (à remettre aux
// titulaires) ou en liste unique, avec son aperçu ; Excel avec une ligne par frais en retard.
// Chaque fichier est noté dans le journal d'audit par le serveur (données personnelles).
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Icon,
  PageHeader,
  Segmented,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { keys } from "../../lib/queries";
import { DocumentPreview } from "../students/DocumentPreview";
import { type ExportOptions, exportUrl, filtersOf } from "./data";

const name = (items: { id: string; name: string }[] | undefined, id?: string) =>
  items?.find((item) => item.id === id)?.name;

export function UnpaidExportPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const filters = filtersOf(params);
  const summary = useQuery({
    queryKey: [...keys.unpaid, "summary", filters],
    queryFn: () => call(api.GET("/api/unpaid/summary/", { params: { query: filters } })),
  });
  const [group, setGroup] = useState<ExportOptions["group"]>("class");
  const [pagePerClass, setPagePerClass] = useState(true);
  const [phone, setPhone] = useState(true);
  const [detail, setDetail] = useState(false);
  const options = { group, pagePerClass, phone, detail };
  const query = new URLSearchParams(filters).toString();
  // « 3e Électricité A · Minerval · Retard : plus de 30 jours » : les filtres repris, en clair.
  const described = [
    name(summary.data?.class_groups, filters.class_group) ?? t("unpaid.export.allClasses"),
    name(summary.data?.fee_types, filters.fee_type) ?? t("unpaid.export.allFees"),
    filters.installment,
    filters.over_days
      ? t("unpaid.filters.lateOver", { count: Number(filters.over_days) })
      : t("unpaid.filters.lateAll"),
    filters.currency && (filters.currency === "CDF" ? "FC" : filters.currency),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to={`/unpaid${query ? `?${query}` : ""}`} className="text-lake underline">
              {t("unpaid.title")}
            </Link>{" "}
            / {t("unpaid.export.crumb")}
          </>
        }
        title={t("unpaid.export.title")}
        subtitle={t("unpaid.export.subtitle", { filters: described })}
        actions={
          <>
            <Button asChild variant="outline">
              <a href={exportUrl(filters, { output: "xlsx", ...options })} download>
                <Icon name="excel" size={16} />
                {t("unpaid.excel")}
              </a>
            </Button>
            <Button asChild>
              <a
                href={exportUrl(filters, { output: "pdf", ...options })}
                target="_blank"
                rel="noopener"
              >
                <Icon name="print" size={16} />
                {group === "class" ? t("unpaid.pdf") : t("unpaid.export.pdfList")}
              </a>
            </Button>
          </>
        }
      />
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex flex-col gap-4 min-[1000px]:order-2">
          <Card>
            <CardHeader>
              <CardTitle>{t("unpaid.export.options")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <span className="text-[.87rem] font-bold text-ink-2">
                  {t("unpaid.export.group")}
                </span>
                <Segmented
                  label={t("unpaid.export.group")}
                  value={group}
                  onValueChange={setGroup}
                  options={[
                    { value: "class", label: t("unpaid.export.byClass") },
                    { value: "list", label: t("unpaid.export.singleList") },
                  ]}
                />
              </div>
              {group === "class" && (
                <CheckboxField
                  id="page-per-class"
                  label={t("unpaid.export.pagePerClass")}
                  checked={pagePerClass}
                  onCheckedChange={(checked) => setPagePerClass(checked === true)}
                />
              )}
              <CheckboxField
                id="guardian-phone"
                label={t("unpaid.export.phone")}
                checked={phone}
                onCheckedChange={(checked) => setPhone(checked === true)}
              />
              <CheckboxField
                id="installment-detail"
                label={t("unpaid.export.detail")}
                checked={detail}
                onCheckedChange={(checked) => setDetail(checked === true)}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("unpaid.export.excelTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-ink-2">{t("unpaid.export.excelHelp")}</CardContent>
          </Card>
        </div>
        <div className="min-[1000px]:order-1">
          <DocumentPreview
            title={t("unpaid.export.preview")}
            src={exportUrl(filters, { output: "html", ...options })}
          />
        </div>
      </div>
    </>
  );
}
