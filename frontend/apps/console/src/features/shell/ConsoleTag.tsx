import { useTranslation } from "@mwangaza/i18n";

/** Pastille « Console » à côté de la marque : on sait toujours qu'on est sur la plateforme. */
export function ConsoleTag() {
  const { t } = useTranslation();
  return (
    <span className="rounded-full bg-lamp px-2.5 py-0.5 text-xs font-bold tracking-[.08em] text-basalt uppercase">
      {t("console.tag")}
    </span>
  );
}
