// « Précédent / Suivant » sous une liste paginée par le serveur (appareils, journal, sessions).
import { useTranslation } from "@mwangaza/i18n";
import { Button } from "@mwangaza/ui";

export function Pager({
  page,
  onPage,
  previous,
  next,
}: {
  page: number;
  onPage: (page: number) => void;
  previous?: string | null;
  next?: string | null;
}) {
  const { t } = useTranslation();
  if (!previous && !next) return null;
  return (
    <div className="flex justify-end gap-2 border-t border-line px-4 py-2.5">
      <Button variant="outline" size="sm" disabled={!previous} onClick={() => onPage(page - 1)}>
        {t("console.schools.previous")}
      </Button>
      <Button variant="outline" size="sm" disabled={!next} onClick={() => onPage(page + 1)}>
        {t("console.schools.next")}
      </Button>
    </div>
  );
}
