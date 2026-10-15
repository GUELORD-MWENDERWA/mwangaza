// Registre des reçus (DOC.3, maquette `registre-recus`) : un reçu par ligne, par jour, par mois ou
// entre deux dates, pour une caisse ou toutes ; PDF A4 à l'italienne et son aperçu, ou Excel.
// Produit par le serveur (`finance.view_reports`) ; chaque fichier est noté dans le journal
// d'audit. Les reçus annulés restent listés, hors des totaux.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  Segmented,
  Select,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { schoolDay } from "../cash/offline";
import { PrintLayoutFields } from "../printing/PrintLayoutFields";
import { DEFAULT_LAYOUT, layoutQuery, usePrintOptions } from "../printing/printOptions";
import { DocumentPreview } from "../students/DocumentPreview";

type Mode = "day" | "month" | "range";

/** Premier et dernier jour (« 2026-10-01 », « 2026-10-31 ») du mois « 2026-10 ». */
function monthBounds(month: string): [string, string] {
  const [year, number] = month.split("-").map(Number);
  const last = new Date(Date.UTC(year!, number!, 0)).getUTCDate();
  return [`${month}-01`, `${month}-${String(last).padStart(2, "0")}`];
}

export function ReceiptRegisterPage() {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const today = schoolDay(school.timezone);
  const [mode, setMode] = useState<Mode>("month");
  const [day, setDay] = useState(today);
  const [month, setMonth] = useState(today.slice(0, 7));
  const [from, setFrom] = useState(`${today.slice(0, 7)}-01`);
  const [to, setTo] = useState(today);
  const [register, setRegister] = useState("");
  const [layout, setLayout] = usePrintOptions("receipt-register", DEFAULT_LAYOUT);
  const registers = useQuery({
    queryKey: [...keys.closings, "summary", { month: today.slice(0, 7) }],
    queryFn: () =>
      call(api.GET("/api/cash-closings/summary/", { params: { query: { month: today } } })),
  });

  const [start, end] =
    mode === "day" ? [day, day] : mode === "month" ? monthBounds(month) : [from, to];
  const valid = Boolean(start && end && start <= end);
  const address = (output: "xlsx" | "pdf" | "html") =>
    `/api/receipt-register/?${new URLSearchParams({
      start,
      end,
      output,
      ...layoutQuery(layout),
      ...(register ? { cash_register: register } : {}),
    })}`;

  return (
    <>
      <PageHeader
        crumbs={
          <>
            <Link to="/cash-closings" className="text-lake underline">
              {t("closings.title")}
            </Link>{" "}
            / {t("closings.register_.crumb")}
          </>
        }
        title={t("closings.register_.title")}
        subtitle={t("closings.register_.subtitle")}
        actions={
          valid && (
            <>
              <Button asChild variant="outline">
                <a href={address("xlsx")} download>
                  <Icon name="excel" size={16} />
                  {t("closings.excel")}
                </a>
              </Button>
              <Button asChild>
                <a href={address("pdf")} target="_blank" rel="noopener">
                  <Icon name="print" size={16} />
                  {t("closings.register_.pdf")}
                </a>
              </Button>
            </>
          )
        }
      />
      <div className="grid items-start gap-4 min-[1000px]:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex flex-col gap-4 min-[1000px]:order-2">
          <Card>
            <CardHeader>
              <CardTitle>{t("closings.register_.period")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Segmented
                label={t("closings.register_.period")}
                value={mode}
                onValueChange={setMode}
                options={[
                  { value: "day", label: t("closings.register_.day") },
                  { value: "month", label: t("closings.register_.month") },
                  { value: "range", label: t("closings.register_.range") },
                ]}
              />
              {mode === "day" && (
                <Field id="register-day" label={t("closings.register_.day")}>
                  {(control) => (
                    <Input
                      {...control}
                      type="date"
                      value={day}
                      max={today}
                      onChange={(event) => setDay(event.target.value)}
                    />
                  )}
                </Field>
              )}
              {mode === "month" && (
                <Field id="register-month" label={t("closings.register_.month")}>
                  {(control) => (
                    <Input
                      {...control}
                      type="month"
                      value={month}
                      max={today.slice(0, 7)}
                      onChange={(event) => setMonth(event.target.value)}
                    />
                  )}
                </Field>
              )}
              {mode === "range" && (
                <>
                  <Field id="register-from" label={t("closings.register_.from")}>
                    {(control) => (
                      <Input
                        {...control}
                        type="date"
                        value={from}
                        max={today}
                        onChange={(event) => setFrom(event.target.value)}
                      />
                    )}
                  </Field>
                  <Field
                    id="register-to"
                    label={t("closings.register_.to")}
                    error={!valid && start && end ? t("closings.register_.order") : undefined}
                  >
                    {(control) => (
                      <Input
                        {...control}
                        type="date"
                        value={to}
                        max={today}
                        onChange={(event) => setTo(event.target.value)}
                      />
                    )}
                  </Field>
                </>
              )}
              <Field id="register-cash" label={t("closings.register")}>
                {(control) => (
                  <Select
                    {...control}
                    value={register}
                    onChange={(event) => setRegister(event.target.value)}
                  >
                    <option value="">{t("closings.allRegisters")}</option>
                    {(registers.data?.registers ?? []).map((item) => (
                      <option key={item.id} value={item.id}>
                        {t("closings.registerOption", { name: item.name })}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <PrintLayoutFields layout={layout} onChange={setLayout} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("closings.register_.excelTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-ink-2">
              {t("closings.register_.excelHelp")}
            </CardContent>
          </Card>
        </div>
        <div className="min-[1000px]:order-1">
          {valid && (
            <DocumentPreview title={t("closings.register_.preview")} src={address("html")} />
          )}
        </div>
      </div>
    </>
  );
}
