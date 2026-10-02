import { useTranslation } from "@mwangaza/i18n";
import { Banner, buttonVariants } from "@mwangaza/ui";

/** Première connexion d'un super-admin (mot de passe provisoire, double authentification à
 *  activer) : ses étapes existent dans l'administration de dépannage, à la même adresse ; la
 *  connexion en cours y continue (même session). */
export function FinishInAdminPage() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <h1>{t("console.login.finishTitle")}</h1>
      <Banner tone="info">{t("console.login.finishText")}</Banner>
      <a href="/admin/login/?next=/" className={buttonVariants({ size: "lg" })}>
        {t("console.login.finishLink")}
      </a>
    </div>
  );
}
