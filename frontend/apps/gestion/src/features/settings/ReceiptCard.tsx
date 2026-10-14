// Carte « Reçus » des paramètres de l'école (M5) : en-tête et mention du reçu, imprimante, taille
// du reçu sur une feuille A4, exemplaires. Enregistrée avec le reste du formulaire ; lue par le
// reçu imprimé (3.2.2).
import type { Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Segmented,
  Select,
  Textarea,
} from "@mwangaza/ui";
import type { ReactNode } from "react";
import { Controller } from "react-hook-form";

import type { CardProps } from "./SchoolSettingsPage";

type Printer = Schemas["PrinterEnum"];
type SheetSize = Schemas["SheetSizeEnum"];

const PRINTERS: Printer[] = ["thermal_80", "thermal_58", "sheet"];
const SHEET_SIZES: SheetSize[] = ["a6", "a5", "small"];
export const HEADER_MAX_LINES = 5;

/** Nombre de lignes d'en-tête, comme le serveur (lignes vides du début et de la fin ignorées). */
export function headerLines(header: string): string[] {
  const text = header.trim();
  return text ? text.split("\n").map((line) => line.trim()) : [];
}

function Choice({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold text-ink-2">{label}</span>
      {children}
      {help && <span className="text-xs text-ink-3">{help}</span>}
    </div>
  );
}

export function ReceiptCard({ form }: CardProps) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  const [name, header, footer, printer] = form.watch([
    "name",
    "receipt.header",
    "receipt.footer",
    "receipt.printer",
  ]);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.receipt.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.receipt.preview")}</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div
          aria-hidden
          className="rounded-box border border-dashed border-line bg-white px-4 py-3 text-center text-xs leading-snug text-black"
        >
          <b className="block text-md uppercase">{name}</b>
          {headerLines(header).map((line, index) => (
            <span key={index} className="block">
              {line}
            </span>
          ))}
          {footer.trim() && (
            <>
              <hr className="my-2 border-dashed border-black/40" />
              <span className="block text-xs">{footer}</span>
            </>
          )}
        </div>
        <Field
          id="receipt-header"
          label={t("settings.receipt.header")}
          help={t("settings.receipt.headerHelp")}
          error={errors.receipt?.header?.message}
        >
          {(control) => (
            <Textarea
              {...control}
              rows={3}
              placeholder={t("settings.receipt.headerPlaceholder")}
              {...form.register("receipt.header")}
            />
          )}
        </Field>
        <Field
          id="receipt-footer"
          label={t("settings.receipt.footer")}
          error={errors.receipt?.footer?.message}
        >
          {(control) => (
            <Input
              {...control}
              placeholder={t("settings.receipt.footerPlaceholder")}
              {...form.register("receipt.footer")}
            />
          )}
        </Field>
        <Choice label={t("settings.receipt.printer")} help={t("settings.receipt.printerHelp")}>
          <Controller
            control={form.control}
            name="receipt.printer"
            render={({ field }) => (
              <Segmented
                label={t("settings.receipt.printer")}
                value={field.value}
                onValueChange={field.onChange}
                className="self-start"
                options={PRINTERS.map((value) => ({
                  value,
                  label: t(`settings.receipt.printerOptions.${value}`),
                }))}
              />
            )}
          />
        </Choice>
        {printer === "sheet" && (
          <Field
            id="receipt-sheet-size"
            label={t("settings.receipt.sheetSize")}
            help={t("settings.receipt.sheetSizeHelp")}
          >
            {(control) => (
              <Select {...control} {...form.register("receipt.sheet_size")}>
                {SHEET_SIZES.map((value) => (
                  <option key={value} value={value}>
                    {t(`settings.receipt.sheetSizes.${value}`)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <Choice label={t("settings.receipt.copies")}>
          <Controller
            control={form.control}
            name="receipt.copies"
            render={({ field }) => (
              <Segmented
                label={t("settings.receipt.copies")}
                value={String(field.value)}
                onValueChange={(value) => field.onChange(Number(value))}
                className="self-start"
                options={[
                  { value: "1", label: t("settings.receipt.copiesOptions.one") },
                  { value: "2", label: t("settings.receipt.copiesOptions.two") },
                ]}
              />
            )}
          />
        </Choice>
      </CardContent>
    </Card>
  );
}
