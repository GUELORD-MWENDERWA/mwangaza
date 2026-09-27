// Paramètres de l'école (M5) : identité, logo, couleur (lisibilité vérifiée, Q8), fuseau horaire,
// devises. Droit `school.configure` ; chaque changement va dans le journal de l'école. Cartes
// « Reçus » (3.2) et « Alertes » (4.2) : avec leur tâche.
import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  SchoolBadge,
  Select,
  Skeleton,
  Switch,
} from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { nearbyReadable, normalizeColor, textColor } from "../../lib/colors";
import { applyServerErrors, errorMessage, fieldMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";

type Settings = Schemas["SchoolSettings"];
type Currency = Schemas["CurrencyEnum"];

const CURRENCIES: Currency[] = ["USD", "CDF"];
// Les deux fuseaux de la RDC en tête de liste ; les autres ensuite.
const DRC_ZONES = ["Africa/Lubumbashi", "Africa/Kinshasa"] as const;
const FIELDS = [
  "name",
  "official_name",
  "timezone",
  "primary_color",
  "enabled_currencies",
  "default_currency",
] as const;

function otherZones(current: string): string[] {
  let zones: string[] = [];
  try {
    zones = Intl.supportedValuesOf("timeZone");
  } catch {
    // Navigateur ancien : seulement les fuseaux de la RDC et celui de l'école.
  }
  const all = new Set([...zones, current]);
  return [...all].filter((zone) => !(DRC_ZONES as readonly string[]).includes(zone)).sort();
}

function useSchema() {
  const { t } = useTranslation();
  return useMemo(
    () =>
      z
        .object({
          name: z.string().trim().min(1, t("validation.nameRequired")).max(200),
          official_name: z.string().trim().max(255),
          timezone: z.string().min(1),
          primary_color: z
            .string()
            .refine((value) => normalizeColor(value) !== null, t("validation.colorFormat")),
          enabled_currencies: z
            .array(z.enum(["USD", "CDF"]))
            .min(1, t("settings.currencies.atLeastOne")),
          default_currency: z.enum(["USD", "CDF"]),
        })
        .transform((values) => ({
          ...values,
          primary_color: normalizeColor(values.primary_color) ?? values.primary_color,
        })),
    [t],
  );
}

type FormValues = z.input<ReturnType<typeof useSchema>>;

export function SchoolSettingsPage() {
  const { t } = useTranslation();
  const settings = useQuery({
    queryKey: keys.settings,
    queryFn: () => call(api.GET("/api/school/settings/")),
  });
  if (settings.isPending) return <Skeleton label={t("common.loading")} />;
  if (settings.isError) {
    return <LoadError error={settings.error} onRetry={() => void settings.refetch()} />;
  }
  return <SettingsForm settings={settings.data} />;
}

function SettingsForm({ settings }: { settings: Settings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const schema = useSchema();
  const [general, setGeneral] = useState<string | null>(null);
  const form = useForm<FormValues, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: settings.name,
      official_name: settings.official_name,
      timezone: settings.timezone,
      primary_color: settings.primary_color,
      enabled_currencies: settings.enabled_currencies,
      default_currency: settings.default_currency,
    },
  });
  const save = useMutation({
    mutationFn: (body: z.output<typeof schema>) =>
      call(api.PATCH("/api/school/settings/", { body })),
    onSuccess: (data) => {
      queryClient.setQueryData(keys.settings, data);
      form.reset(form.getValues());
      // Nom et couleur de l'école : menu, écran de connexion.
      void queryClient.invalidateQueries({ queryKey: keys.school });
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...FIELDS], form.setError, t)),
  });

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        save.reset();
        save.mutate(values);
      })}
    >
      <PageHeader
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
        actions={
          <Button type="submit" size="lg" disabled={save.isPending}>
            {t("settings.save")}
          </Button>
        }
      />
      {general && <Banner tone="due">{general}</Banner>}
      {save.isSuccess && !form.formState.isDirty && (
        <Banner tone="ok" role="status">
          {t("settings.saved")}
        </Banner>
      )}
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-[1.4fr_1fr]">
        <div className="flex flex-col gap-4">
          <IdentityCard form={form} code={settings.code} />
          <LogoColorCard form={form} settings={settings} />
        </div>
        <CurrenciesCard form={form} />
      </div>
    </form>
  );
}

type CardProps = { form: UseFormReturn<FormValues, unknown, unknown> };

function IdentityCard({ form, code }: CardProps & { code: string }) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  const timezone = form.watch("timezone");
  const zones = useMemo(() => otherZones(timezone), [timezone]);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.identity.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 min-[600px]:grid-cols-2">
        <Field
          id="school-name"
          label={t("settings.identity.name")}
          required
          help={t("settings.identity.nameHelp")}
          error={errors.name?.message}
        >
          {(control) => <Input {...control} {...form.register("name")} />}
        </Field>
        <Field
          id="school-address"
          label={t("settings.identity.address")}
          help={t("settings.identity.addressHelp")}
        >
          {(control) => (
            <Input {...control} value={window.location.host || code} readOnly tabIndex={-1} />
          )}
        </Field>
        <Field
          id="school-official-name"
          label={t("settings.identity.officialName")}
          help={t("settings.identity.officialNameHelp")}
          error={errors.official_name?.message}
          className="min-[600px]:col-span-2"
        >
          {(control) => <Input {...control} {...form.register("official_name")} />}
        </Field>
        <Field
          id="school-timezone"
          label={t("settings.identity.timezone")}
          error={errors.timezone?.message}
        >
          {(control) => (
            <Select {...control} {...form.register("timezone")}>
              <option value="Africa/Lubumbashi">
                {`Africa/Lubumbashi — ${t("settings.identity.zoneLubumbashi")}`}
              </option>
              <option value="Africa/Kinshasa">
                {`Africa/Kinshasa — ${t("settings.identity.zoneKinshasa")}`}
              </option>
              <optgroup label={t("settings.identity.otherZones")}>
                {zones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </optgroup>
            </Select>
          )}
        </Field>
      </CardContent>
    </Card>
  );
}

function LogoColorCard({ form, settings }: CardProps & { settings: Settings }) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  const color = normalizeColor(form.watch("primary_color"));
  const text = color ? textColor(color) : null;
  const proposal = color && !text ? nearbyReadable(color) : null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.logo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <LogoField settings={settings} />
        <Field
          id="school-color"
          label={t("settings.color.label")}
          help={t("settings.color.help")}
          error={errors.primary_color?.message}
        >
          {(control) => (
            <div className="flex items-center gap-3">
              <Controller
                control={form.control}
                name="primary_color"
                render={({ field }) => (
                  <input
                    type="color"
                    aria-label={t("settings.color.picker")}
                    value={color ?? "#000000"}
                    onChange={(event) => field.onChange(event.target.value.toUpperCase())}
                    className="size-10 shrink-0 cursor-pointer rounded-field border border-field bg-card p-0.5"
                  />
                )}
              />
              <Input {...control} {...form.register("primary_color")} className="font-mono" />
              <span
                className="grid min-h-10 shrink-0 place-items-center rounded-field px-3 text-sm font-bold"
                style={color ? { backgroundColor: color, color: text ?? "#FFFFFF" } : undefined}
              >
                {t("settings.color.preview")}
              </span>
            </div>
          )}
        </Field>
        {proposal && (
          <Banner tone="warn">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{t("settings.color.unreadable", { color: proposal })}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  form.setValue("primary_color", proposal, {
                    shouldDirty: true,
                    shouldValidate: true,
                  })
                }
              >
                {t("settings.color.useProposal", { color: proposal })}
              </Button>
            </div>
          </Banner>
        )}
      </CardContent>
    </Card>
  );
}

/** Logo enregistré aussitôt choisi (envoi à part du formulaire). */
function LogoField({ settings }: { settings: Settings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const onSuccess = (data: Settings) => {
    queryClient.setQueryData(keys.settings, data);
    void queryClient.invalidateQueries({ queryKey: keys.school });
  };
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("logo", file);
      return call(
        api.POST("/api/school/settings/logo/", {
          body: body as unknown as { logo: string },
        }),
      );
    },
    onSuccess,
  });
  const remove = useMutation({
    mutationFn: () => call(api.DELETE("/api/school/settings/logo/")),
    onSuccess,
  });
  const failed = upload.error ?? remove.error;
  const fieldError = failed instanceof ApiError ? Object.values(failed.fields)[0]?.[0] : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[.87rem] font-bold text-ink-2">{t("settings.logo.label")}</span>
      <div className="flex flex-wrap items-center gap-3">
        {settings.logo ? (
          <img
            src={settings.logo}
            alt={t("settings.logo.alt")}
            className="size-[84px] rounded-box border border-line bg-white object-contain p-1"
          />
        ) : (
          <SchoolBadge
            code={settings.code}
            name={settings.name}
            color={settings.primary_color}
            textColor={settings.text_color}
            logo={null}
            size="lg"
          />
        )}
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => input.current?.click()}
            >
              <Icon name="upload" size={14} />
              {t("settings.logo.change")}
            </Button>
            {settings.logo && (
              <Button
                variant="ghost"
                size="sm"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
              >
                {t("settings.logo.remove")}
              </Button>
            )}
          </div>
          <span className="text-[.8rem] text-ink-3">{t("settings.logo.help")}</span>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg,image/svg+xml"
          className="hidden"
          aria-label={t("settings.logo.change")}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) upload.mutate(file);
          }}
        />
      </div>
      <p role="status" className="text-[.8rem] text-ok">
        {upload.isSuccess && t("settings.logo.saved")}
        {remove.isSuccess && t("settings.logo.removed")}
      </p>
      {failed && (
        <Banner tone="due">
          {fieldError ? fieldMessage(fieldError.code, t) : errorMessage(failed, t)}
        </Banner>
      )}
    </div>
  );
}

function CurrenciesCard({ form }: CardProps) {
  const { t } = useTranslation();
  const { errors } = form.formState;
  const enabled = form.watch("enabled_currencies");
  const labels: Record<Currency, [string, string]> = {
    USD: [t("settings.currencies.usd"), t("settings.currencies.usdHelp")],
    CDF: [t("settings.currencies.cdf"), t("settings.currencies.cdfHelp")],
  };
  const toggle = (currency: Currency, on: boolean) => {
    const next = CURRENCIES.filter((item) => (item === currency ? on : enabled.includes(item)));
    form.setValue("enabled_currencies", next, { shouldDirty: true, shouldValidate: true });
    const main = form.getValues("default_currency");
    if (!next.includes(main) && next[0]) {
      form.setValue("default_currency", next[0], { shouldDirty: true });
    }
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.currencies.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col">
        {CURRENCIES.map((currency) => (
          <div
            key={currency}
            className="flex items-center justify-between gap-3 border-b border-line-soft py-3"
          >
            <label htmlFor={`currency-${currency}`} className="cursor-pointer">
              <b>{labels[currency][0]}</b>
              {` · ${labels[currency][1]}`}
            </label>
            <Switch
              id={`currency-${currency}`}
              checked={enabled.includes(currency)}
              onCheckedChange={(on) => toggle(currency, on)}
            />
          </div>
        ))}
        {errors.enabled_currencies && (
          <p role="alert" className="pt-2 text-[.8rem] text-due">
            {errors.enabled_currencies.message}
          </p>
        )}
        <div className="flex items-center justify-between gap-3 pt-3">
          <label htmlFor="default-currency">{t("settings.currencies.main")}</label>
          <Select id="default-currency" className="w-auto" {...form.register("default_currency")}>
            {enabled.map((currency) => (
              <option key={currency} value={currency}>
                {currency === "CDF" ? "FC" : currency}
              </option>
            ))}
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}
