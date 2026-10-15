import { useTranslation } from "@mwangaza/i18n";
import { Segmented } from "@mwangaza/ui";

import type { PrintLayout } from "./printOptions";

/** Papier, sens et (documents courts) exemplaires par feuille : même bloc sur tous les écrans
 *  d'impression. */
export function PrintLayoutFields({
  layout,
  onChange,
  copies = false,
}: {
  layout: PrintLayout;
  onChange: (change: Partial<PrintLayout>) => void;
  /** Convocation, circulaire : plusieurs exemplaires sur une feuille. */
  copies?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-bold text-ink-2">{t("print.paper")}</span>
        <Segmented
          label={t("print.paper")}
          value={layout.paper}
          onValueChange={(paper) => onChange({ paper })}
          options={[
            { value: "a4", label: "A4" },
            { value: "a5", label: "A5" },
          ]}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-bold text-ink-2">{t("print.orientation")}</span>
        <Segmented
          label={t("print.orientation")}
          value={layout.orientation}
          onValueChange={(orientation) => onChange({ orientation })}
          options={[
            { value: "auto", label: t("print.auto") },
            { value: "portrait", label: t("print.portrait") },
            { value: "landscape", label: t("print.landscape") },
          ]}
        />
      </div>
      {copies && (
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-bold text-ink-2">{t("print.perSheet")}</span>
          <Segmented
            label={t("print.perSheet")}
            value={String(layout.perSheet)}
            onValueChange={(count) =>
              onChange({ perSheet: Number(count) as PrintLayout["perSheet"] })
            }
            options={["1", "2", "3"].map((count) => ({ value: count, label: count }))}
          />
        </div>
      )}
    </>
  );
}
