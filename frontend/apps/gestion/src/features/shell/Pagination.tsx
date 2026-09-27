import { useTranslation } from "@mwangaza/i18n";
import { Button } from "@mwangaza/ui";
import type { ReactNode } from "react";

/** Pied d'une liste paginée par le serveur (50 par page) : « 1 – 50 sur 1 312 », précédent,
 *  suivant. */
export function Pagination({
  summary,
  page,
  hasPrevious,
  hasNext,
  onPage,
}: {
  summary: ReactNode;
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPage: (page: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-[18px] py-3 text-sm text-ink-3">
      <span>{summary}</span>
      {(hasPrevious || hasNext) && (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrevious}
            onClick={() => onPage(page - 1)}
          >
            {t("common.previous")}
          </Button>
          <Button variant="outline" size="sm" disabled={!hasNext} onClick={() => onPage(page + 1)}>
            {t("common.next")}
          </Button>
        </div>
      )}
    </div>
  );
}
