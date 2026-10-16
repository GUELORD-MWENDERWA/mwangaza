// Paramètres de l'école (M5) : identité, logos (couleur, noir et blanc des reçus thermiques),
// couleur (lisibilité vérifiée, Q8), fuseau horaire, reçus, devises. Droit `school.configure` ;
// chaque changement va dans le journal de l'école. Carte « Alertes » : 4.2. Carte « Signature et
// cachet » : DOC.1. Carte « Caisses » : avec `finance.configure_fees`.
import { ApiError, api, call, type Schemas } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { formatAmountValue, parseAmount } from "@mwangaza/money";
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
import { can } from "../../lib/permissions";
import { keys, useCurrentMe } from "../../lib/queries";
import { LoadError } from "../status/StatusPages";
import { AlertsCard } from "./AlertsCard";
import { CashRegistersCard } from "./CashRegistersCard";
import { HEADER_MAX_LINES, headerLines, ReceiptCard } from "./ReceiptCard";
import { GradingCard } from "./GradingCard";
import { LevelRulesCard } from "./LevelRulesCard";
import { PassRulesCard } from "./PassRulesCard";
import { PortalCard } from "./PortalCard";
import { RemindersCard } from "./RemindersCard";
import { SigningCard } from "./SigningCard";

type Settings = Schemas["SchoolSettings"];
type Currency = Schemas["CurrencyEnum"];

const CURRENCIES: Currency[] = ["USD", "CDF"];
// Les deux fuseaux de la RDC en tête de liste ; les autres ensuite.
const DRC_ZONES = ["Africa/Lubumbashi", "Africa/Kinshasa"] as const;
const FIELDS = [
  "name",
  "official_name",
  "epst_code",
  "province",
  "city",
  "commune",
  "regime",
  "head_name",
  "head_title",
  "timezone",
  "primary_color",
  "enabled_currencies",
  "default_currency",
  "receipt.header",
  "receipt.footer",
  "alerts.cancellations_per_day",
  "alerts.closing_time",
  "reminders.days_before",
  "reminders.overdue_every_days",
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
  return useMemo(() => {
    // Seuil d'écart saisi comme à la caisse (« 10,00 »), envoyé en plus petite unité.
    const amount = (currency: Currency) =>
      z
        .string()
        .refine(
          (value) => parseAmount(value, currency) !== null,
          t("settings.alerts.invalidAmount"),
        )
        .transform((value) => parseAmount(value, currency) ?? 0);
    // Nombre de jours des relances, de 1 à `max`.
    const days = (max: number) =>
      z
        .string()
        .trim()
        .refine(
          (value) => /^\d{1,2}$/.test(value) && Number(value) >= 1 && Number(value) <= max,
          t("settings.reminders.invalidDays", { max }),
        );
    // Pourcentage entier de 0 à 100 (règles de réussite).
    const percent = z
      .string()
      .trim()
      .refine(
        (value) => /^\d{1,3}$/.test(value) && Number(value) <= 100,
        t("settings.passRules.invalidPercent"),
      );
    return z
      .object({
        name: z.string().trim().min(1, t("validation.nameRequired")).max(200),
        official_name: z.string().trim().max(255),
        epst_code: z
          .string()
          .trim()
          .refine(
            (value) => value === "" || /^\d{7}$/.test(value),
            t("settings.identity.epstCodeInvalid"),
          ),
        province: z.string().trim().max(60),
        city: z.string().trim().max(80),
        commune: z.string().trim().max(80),
        regime: z.enum(["", "public", "convention", "private"]),
        head_name: z.string().trim().max(150),
        head_title: z.string().trim().max(100),
        timezone: z.string().min(1),
        primary_color: z
          .string()
          .refine((value) => normalizeColor(value) !== null, t("validation.colorFormat")),
        enabled_currencies: z
          .array(z.enum(["USD", "CDF"]))
          .min(1, t("settings.currencies.atLeastOne")),
        default_currency: z.enum(["USD", "CDF"]),
        receipt: z.object({
          printer: z.enum(["thermal_80", "thermal_58", "sheet"]),
          sheet_size: z.enum(["half", "third"]),
          header: z
            .string()
            .trim()
            .max(300)
            .refine(
              (value) => headerLines(value).length <= HEADER_MAX_LINES,
              t("settings.receipt.tooManyLines"),
            ),
          footer: z.string().trim().max(200),
        }),
        alerts: z.object({
          difference: z.object({ USD: amount("USD"), CDF: amount("CDF") }),
          cancellations_per_day: z
            .string()
            .trim()
            .regex(/^\d{1,3}$/, t("settings.alerts.invalidCount"))
            .refine((value) => Number(value) <= 100, t("settings.alerts.invalidCount")),
          closing_time: z.string().regex(/^\d{2}:\d{2}$/, t("settings.alerts.invalidTime")),
        }),
        reminders: z.object({
          enabled: z.boolean(),
          days_before: days(30),
          overdue_every_days: days(60),
        }),
        portal: z.object({ teacher_phone: z.boolean() }),
        grading: z.object({ entry: z.enum(["detailed", "totals"]) }),
        pass_rules: z.object({
          pass_percent: percent,
          course_pass_percent: percent,
          resit_mode: z.enum(["band", "any_failed"]),
          resit_floor_percent: percent,
          max_resit_courses: z
            .string()
            .trim()
            .refine((value) => /^\d{1,2}$/.test(value), t("settings.passRules.invalidCount")),
          resit_failures_to_fail: z
            .string()
            .trim()
            .refine(
              (value) => /^\d{1,2}$/.test(value) && Number(value) >= 1,
              t("settings.passRules.invalidCount"),
            ),
        }),
      })
      .transform(({ alerts, reminders, pass_rules: rules, ...values }) => ({
        ...values,
        primary_color: normalizeColor(values.primary_color) ?? values.primary_color,
        alerts: {
          difference_minor: alerts.difference,
          cancellations_per_day: Number(alerts.cancellations_per_day),
          closing_time: alerts.closing_time,
        },
        reminders: {
          enabled: reminders.enabled,
          days_before: Number(reminders.days_before),
          overdue_every_days: Number(reminders.overdue_every_days),
        },
        pass_rules: {
          pass_percent: Number(rules.pass_percent),
          course_pass_percent: Number(rules.course_pass_percent),
          resit_mode: rules.resit_mode,
          resit_floor_percent: Number(rules.resit_floor_percent),
          resit_failures_to_fail: Number(rules.resit_failures_to_fail),
          max_resit_courses: Number(rules.max_resit_courses),
        },
      }));
  }, [t]);
}

type FormValues = z.input<ReturnType<typeof useSchema>>;

export function SchoolSettingsPage() {
  const { t } = useTranslation();
  const me = useCurrentMe();
  const settings = useQuery({
    queryKey: keys.settings,
    queryFn: () => call(api.GET("/api/school/settings/")),
  });
  if (settings.isPending) return <Skeleton label={t("common.loading")} />;
  if (settings.isError) {
    return <LoadError error={settings.error} onRetry={() => void settings.refetch()} />;
  }
  return (
    <div className="flex flex-col gap-5">
      <SettingsForm settings={settings.data} />
      {can(me, ["finance.configure_fees"]) && <CashRegistersCard />}
    </div>
  );
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
      epst_code: settings.epst_code,
      province: settings.province,
      city: settings.city,
      commune: settings.commune,
      regime: settings.regime,
      head_name: settings.head_name,
      head_title: settings.head_title,
      timezone: settings.timezone,
      primary_color: settings.primary_color,
      enabled_currencies: settings.enabled_currencies,
      default_currency: settings.default_currency,
      receipt: settings.receipt,
      alerts: {
        difference: {
          USD: formatAmountValue(settings.alerts.difference_minor.USD ?? 0, "USD"),
          CDF: formatAmountValue(settings.alerts.difference_minor.CDF ?? 0, "CDF"),
        },
        cancellations_per_day: String(settings.alerts.cancellations_per_day),
        closing_time: settings.alerts.closing_time,
      },
      reminders: {
        enabled: settings.reminders.enabled,
        days_before: String(settings.reminders.days_before),
        overdue_every_days: String(settings.reminders.overdue_every_days),
      },
      portal: settings.portal,
      grading: settings.grading,
      pass_rules: {
        pass_percent: String(settings.pass_rules.pass_percent),
        course_pass_percent: String(settings.pass_rules.course_pass_percent),
        resit_mode: settings.pass_rules.resit_mode,
        resit_floor_percent: String(settings.pass_rules.resit_floor_percent),
        resit_failures_to_fail: String(settings.pass_rules.resit_failures_to_fail),
        max_resit_courses: String(settings.pass_rules.max_resit_courses),
      },
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
      <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-4 min-[1100px]:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <IdentityCard form={form} code={settings.code} />
          <LogoColorCard form={form} settings={settings} />
          <SigningCard form={form} settings={settings} />
        </div>
        <div className="flex flex-col gap-4">
          <ReceiptCard form={form} />
          <CurrenciesCard form={form} />
          <AlertsCard form={form} />
          <RemindersCard form={form} />
          <PortalCard form={form} />
          <GradingCard form={form} />
          <PassRulesCard form={form} />
          <LevelRulesCard />
        </div>
      </div>
    </form>
  );
}

export type CardProps = { form: UseFormReturn<FormValues, unknown, unknown> };

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
          id="school-epst-code"
          label={t("settings.identity.epstCode")}
          help={t("settings.identity.epstCodeHelp")}
          error={errors.epst_code?.message}
        >
          {(control) => <Input inputMode="numeric" {...control} {...form.register("epst_code")} />}
        </Field>
        <Field
          id="school-province"
          label={t("settings.identity.province")}
          error={errors.province?.message}
        >
          {(control) => <Input {...control} {...form.register("province")} />}
        </Field>
        <Field id="school-city" label={t("settings.identity.city")} error={errors.city?.message}>
          {(control) => <Input {...control} {...form.register("city")} />}
        </Field>
        <Field
          id="school-commune"
          label={t("settings.identity.commune")}
          help={t("settings.identity.placeHelp")}
          error={errors.commune?.message}
        >
          {(control) => <Input {...control} {...form.register("commune")} />}
        </Field>
        <Field
          id="school-regime"
          label={t("settings.identity.regime")}
          error={errors.regime?.message}
        >
          {(control) => (
            <Select {...control} {...form.register("regime")}>
              <option value="">{t("settings.identity.regimeNone")}</option>
              <option value="public">{t("settings.identity.regimePublic")}</option>
              <option value="convention">{t("settings.identity.regimeConvention")}</option>
              <option value="private">{t("settings.identity.regimePrivate")}</option>
            </Select>
          )}
        </Field>
        <Field
          id="school-timezone"
          label={t("settings.identity.timezone")}
          error={errors.timezone?.message}
          className="min-[600px]:col-span-2"
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
        <div className="grid gap-4 min-[600px]:grid-cols-2">
          <LogoField settings={settings} kind="logo" />
          <LogoField settings={settings} kind="logo_monochrome" />
        </div>
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

/** Logo enregistré aussitôt choisi (envoi à part du formulaire) : logo couleur, ou noir et blanc
 *  des reçus thermiques (sans lui, le logo couleur s'imprime en niveaux de gris). */
function LogoField({ settings, kind }: { settings: Settings; kind: "logo" | "logo_monochrome" }) {
  const { t } = useTranslation();
  const monochrome = kind === "logo_monochrome";
  const logo = settings[kind];
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
      const options = { body: body as unknown as { logo: string } };
      return call(
        monochrome
          ? api.POST("/api/school/settings/logo-monochrome/", options)
          : api.POST("/api/school/settings/logo/", options),
      );
    },
    onSuccess,
  });
  const remove = useMutation({
    mutationFn: () =>
      call(
        monochrome
          ? api.DELETE("/api/school/settings/logo-monochrome/")
          : api.DELETE("/api/school/settings/logo/"),
      ),
    onSuccess,
  });
  const failed = upload.error ?? remove.error;
  const fieldError = failed instanceof ApiError ? Object.values(failed.fields)[0]?.[0] : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold text-ink-2">
        {t(monochrome ? "settings.logo.monochrome" : "settings.logo.label")}
      </span>
      <div className="flex flex-wrap items-center gap-3">
        {logo ? (
          <img
            src={logo}
            alt={t(monochrome ? "settings.logo.monochromeAlt" : "settings.logo.alt")}
            className="size-[84px] rounded-box border border-line bg-white object-contain p-1"
          />
        ) : monochrome ? (
          <span className="grid size-[84px] place-items-center rounded-box border border-dashed border-line text-center text-xs text-ink-3">
            {t("settings.logo.none")}
          </span>
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
            {logo && (
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
          <span className="text-xs text-ink-3">
            {t(monochrome ? "settings.logo.monochromeHelp" : "settings.logo.help")}
          </span>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          aria-label={t(monochrome ? "settings.logo.changeMonochrome" : "settings.logo.change")}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) upload.mutate(file);
          }}
        />
      </div>
      <p role="status" className="text-xs text-ok">
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
          <p role="alert" className="pt-2 text-xs text-due">
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
