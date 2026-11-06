// Onglet « Modèle de carte » (lot 10, A.5) : couleur, texte du verso, validité, champs imprimés,
// formule aux autorités, photo exigée. Enregistré à part (le reste des paramètres ne bouge pas) ;
// une carte déjà émise dont l'impression change passe en « à réimprimer ».
import { api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Field,
  Input,
  Skeleton,
  Switch,
  Textarea,
} from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { cardKeys, type CardSettings } from "./data";

type PrintedField = Schemas["PrintedFieldsEnum"];
const OPTIONAL: PrintedField[] = [
  "birth",
  "sex",
  "nationality",
  "national_id",
  "guardian_phone",
  "address",
  "authorities",
];
const DEFAULT_COLOR = "#1d4ed8";

export function CardModelTab() {
  const { t } = useTranslation();
  const settings = useQuery({
    queryKey: keys.settings,
    queryFn: () => call(api.GET("/api/school/settings/")),
  });
  if (settings.isPending) return <Skeleton label={t("common.loading")} />;
  if (settings.isError) {
    return <LoadError error={settings.error} onRetry={() => void settings.refetch()} />;
  }
  // `key` : le formulaire repart des valeurs enregistrées après chaque relecture.
  return <ModelForm key={JSON.stringify(settings.data.card)} initial={settings.data.card} />;
}

function ModelForm({ initial }: { initial: CardSettings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CardSettings>(initial);
  const set = <K extends keyof CardSettings>(key: K, value: CardSettings[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const toggle = (code: PrintedField, on: boolean) =>
    set(
      "printed_fields",
      OPTIONAL.filter((item) => (item === code ? on : draft.printed_fields.includes(item))),
    );
  const save = useMutation({
    mutationFn: () => call(api.PATCH("/api/school/settings/", { body: { card: draft } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.settings });
      await queryClient.invalidateQueries({ queryKey: cardKeys.all });
    },
  });
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);
  return (
    <form
      className="grid max-w-3xl gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate();
      }}
    >
      <Card>
        <CardHeader>
          <CardTitle>{t("cards.model.printed.title")}</CardTitle>
          <span className="text-sm text-ink-3">{t("cards.model.printed.intro")}</span>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {OPTIONAL.map((code) => (
            <CheckboxField
              key={code}
              id={`card-field-${code}`}
              label={t(`cards.model.fields.${code}`)}
              checked={draft.printed_fields.includes(code)}
              onCheckedChange={(on) => toggle(code, on === true)}
            />
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("cards.model.look.title")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Field id="card-color" label={t("cards.model.color")} help={t("cards.model.colorHelp")}>
            {(control) => (
              <div className="flex items-center gap-3">
                <input
                  {...control}
                  type="color"
                  className="size-10 cursor-pointer rounded-box border border-line bg-card p-1"
                  value={draft.color || DEFAULT_COLOR}
                  onChange={(event) => set("color", event.target.value)}
                />
                {draft.color && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => set("color", "")}>
                    {t("cards.model.colorDefault")}
                  </Button>
                )}
              </div>
            )}
          </Field>
          <Field
            id="card-valid-until"
            label={t("cards.model.validUntil")}
            help={t("cards.model.validUntilHelp")}
          >
            {(control) => (
              <Input
                {...control}
                type="date"
                className="max-w-52"
                value={draft.valid_until ?? ""}
                onChange={(event) => set("valid_until", event.target.value || null)}
              />
            )}
          </Field>
          <Field
            id="card-back-text"
            label={t("cards.model.backText")}
            help={t("cards.model.backTextHelp")}
          >
            {(control) => (
              <Textarea
                {...control}
                rows={3}
                maxLength={240}
                value={draft.back_text}
                onChange={(event) => set("back_text", event.target.value)}
              />
            )}
          </Field>
          {draft.printed_fields.includes("authorities") && (
            <Field
              id="card-authorities"
              label={t("cards.model.authorities")}
              help={t("cards.model.authoritiesHelp")}
            >
              {(control) => (
                <Textarea
                  {...control}
                  rows={2}
                  maxLength={200}
                  value={draft.authorities_text}
                  onChange={(event) => set("authorities_text", event.target.value)}
                />
              )}
            </Field>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="card-require-photo" className="cursor-pointer">
              <b>{t("cards.model.requirePhoto")}</b>
              <span className="block text-sm text-ink-3">{t("cards.model.requirePhotoHelp")}</span>
            </label>
            <Switch
              id="card-require-photo"
              checked={draft.require_photo}
              onCheckedChange={(on) => set("require_photo", on)}
            />
          </div>
        </CardContent>
      </Card>
      {dirty && <Banner tone="warn">{t("cards.model.reprintWarning")}</Banner>}
      {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
      {save.isSuccess && !dirty && <Banner tone="ok">{t("cards.model.saved")}</Banner>}
      <div>
        <Button type="submit" disabled={!dirty || save.isPending}>
          {t("common.save")}
        </Button>
      </div>
    </form>
  );
}
