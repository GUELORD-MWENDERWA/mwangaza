// Carte « Signature et cachet » des paramètres (DOC.1) : nom et titre du chef d'établissement
// (enregistrés avec le formulaire), sa signature et le cachet de l'école (envoyés aussitôt
// choisis). Posés sur les reçus, fiches d'inscription, situations, circulaires et lettres ; sans
// image, la ligne reste à signer à la main. Au journal de l'école.
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Card, CardContent, CardHeader, CardTitle, Field, Input } from "@mwangaza/ui";
import { useQueryClient } from "@tanstack/react-query";

import { keys } from "../../lib/queries";
import type { CardProps } from "./SchoolSettingsPage";
import { SignatureField } from "./SignatureField";

type Settings = Schemas["SchoolSettings"];
const asImage = (body: FormData) => ({ body: body as unknown as { image: string } });

export function SigningCard({ form, settings }: CardProps & { settings: Settings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { errors } = form.formState;
  const onSaved = (data: Settings) => {
    queryClient.setQueryData(keys.settings, data);
    // Reçus et bordereaux imprimés par la Gestion : adresses lues avec le compte.
    void queryClient.invalidateQueries({ queryKey: keys.me });
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.signing.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 min-[600px]:grid-cols-2">
        <p className="text-sm text-ink-3 min-[600px]:col-span-2">{t("settings.signing.intro")}</p>
        <Field
          id="school-head-name"
          label={t("settings.signing.headName")}
          error={errors.head_name?.message}
        >
          {(control) => <Input {...control} {...form.register("head_name")} />}
        </Field>
        <Field
          id="school-head-title"
          label={t("settings.signing.headTitle")}
          help={t("settings.signing.headTitleHelp")}
          error={errors.head_title?.message}
        >
          {(control) => <Input {...control} {...form.register("head_title")} />}
        </Field>
        <div className="min-[600px]:col-span-2">
          <SignatureField
            label={t("settings.signing.headSignature")}
            help={t("signature.help")}
            image={settings.head_signature}
            send={(body) => call(api.POST("/api/school/settings/head-signature/", asImage(body)))}
            remove={() => call(api.DELETE("/api/school/settings/head-signature/"))}
            onSaved={onSaved}
          />
        </div>
        <div className="min-[600px]:col-span-2">
          <SignatureField
            label={t("settings.signing.stamp")}
            help={t("settings.signing.stampHelp")}
            image={settings.stamp}
            send={(body) => call(api.POST("/api/school/settings/stamp/", asImage(body)))}
            remove={() => call(api.DELETE("/api/school/settings/stamp/"))}
            onSaved={onSaved}
          />
        </div>
      </CardContent>
    </Card>
  );
}
