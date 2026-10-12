// Carte « Portail des parents » des paramètres de l'école (5.7) : le nom du titulaire de la
// classe est toujours montré aux parents ; son téléphone seulement si l'école l'a choisi (c'est
// le numéro personnel d'un enseignant). Enregistrée avec le reste du formulaire.
import { useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle, Switch } from "@mwangaza/ui";

import type { CardProps } from "./SchoolSettingsPage";

export function PortalCard({ form }: CardProps) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.portal.title")}</CardTitle>
        <span className="text-sm text-ink-3">{t("settings.portal.intro")}</span>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="portal-teacher-phone" className="cursor-pointer">
            <b>{t("settings.portal.teacherPhone")}</b>
            <span className="block text-sm text-ink-3">
              {t("settings.portal.teacherPhoneHelp")}
            </span>
          </label>
          <Switch
            id="portal-teacher-phone"
            checked={form.watch("portal.teacher_phone")}
            onCheckedChange={(on) =>
              form.setValue("portal.teacher_phone", on, { shouldDirty: true })
            }
          />
        </div>
      </CardContent>
    </Card>
  );
}
