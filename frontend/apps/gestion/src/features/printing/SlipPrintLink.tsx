import { useTranslation } from "@mwangaza/i18n";

import { PrintLayoutFields } from "./PrintLayoutFields";
import { DEFAULT_LAYOUT, layoutQuery, usePrintOptions } from "./printOptions";

/** Lien vers un document court (convocation, circulaire) avec ses options d'impression, retrouvées
 *  d'une fois à l'autre. */
export function SlipPrintLink({
  document,
  path,
  label,
}: {
  document: string;
  path: string;
  label: string;
}) {
  const { t } = useTranslation();
  const [layout, setLayout] = usePrintOptions(document, DEFAULT_LAYOUT);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-4">
        <a
          className="text-sm font-bold text-lake underline"
          href={`${path}?${new URLSearchParams(layoutQuery(layout))}`}
          target="_blank"
          rel="noreferrer"
        >
          {label}
        </a>
        <details className="text-sm">
          <summary className="cursor-pointer text-ink-3">{t("print.options")}</summary>
          <div className="mt-2 flex flex-col gap-3">
            <PrintLayoutFields layout={layout} onChange={setLayout} copies />
          </div>
        </details>
      </div>
    </div>
  );
}
