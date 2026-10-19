// Nouvelle école (5.3, A1) : type d'espace (4.15 : réel, essai ou démonstration, choisi une fois
// pour toutes), identité, devises, abonnement et premier directeur. Démonstration : formulaire
// court de `Demonstration.tsx`, le serveur écrit les données fictives (4.17.2). Nouveau numéro :
// le serveur crée son compte et renvoie un mot de passe provisoire, affiché ici une seule fois
// (pas de SMS en V1) ; numéro connu : le compte est ajouté, ses noms ne changent pas.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, useTranslation } from "@mwangaza/i18n";
import { CURRENCIES, type Currency } from "@mwangaza/money";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CheckboxField,
  Code,
  Field,
  Input,
  PageHeader,
  Segmented,
  Select,
  buttonVariants,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { Link, useSearchParams } from "react-router";
import { z } from "zod";

import { keys } from "../../lib/queries";
import { RIGHTS, spaceRight, useCan } from "../../lib/rights";
import { NewDemoSpace } from "./Demonstration";
import { MODULES, ModuleChoices } from "./ModulesCard";
import {
  IdentityFields,
  KINDS,
  SCHOOL_FIELDS,
  SubscriptionFields,
  schoolBody,
  today,
  useSchoolSchema,
} from "./schoolForm";

type Created = Schemas["ConsoleSchoolCreated"];

const HEAD_FIELDS = ["phone", "last_name", "middle_name", "first_name"] as const;
const TRIAL_DAYS = 90;

function trialEnd(): string {
  const day = new Date(`${today()}T12:00:00`);
  day.setDate(day.getDate() + TRIAL_DAYS);
  return day.toLocaleDateString("en-CA");
}

function useSchema() {
  const { t } = useTranslation();
  const school = useSchoolSchema();
  return school
    .extend({
      environment: z.enum(KINDS),
      enabled_currencies: z
        .array(z.enum(CURRENCIES))
        .min(1, t("console.schools.fields.noCurrency")),
      default_currency: z.enum(CURRENCIES),
      modules: z.array(z.enum(MODULES)),
      head: z.object({
        phone: z.string().trim().min(1, t("fieldErrors.required")),
        last_name: z.string().trim().max(100),
        middle_name: z.string().trim().max(100),
        first_name: z.string().trim().max(100),
      }),
    })
    .refine((values) => values.enabled_currencies.includes(values.default_currency), {
      path: ["default_currency"],
      message: t("fieldErrors.default_currency_disabled"),
    });
}

type Values = z.infer<ReturnType<typeof useSchema>>;

export function NewSchoolPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  // Type de l'onglet d'où l'on vient (`?type=`) ; sinon un espace réel. Seulement les types que
  // les rôles du membre permettent de créer (EQ.2).
  const asked = useSearchParams()[0].get("type");
  const can = useCan();
  const kinds = KINDS.filter((value) => can(spaceRight(value, RIGHTS.schoolsManage)));
  const form = useForm<Values>({
    resolver: zodResolver(useSchema()),
    defaultValues: {
      environment: kinds.find((kind) => kind === asked) ?? kinds[0],
      name: "",
      official_name: "",
      code: "",
      status: "trial",
      plan: "",
      trial_ends_on: trialEnd(),
      paid_until: "",
      enabled_currencies: [...CURRENCIES],
      default_currency: CURRENCIES[0],
      modules: [...MODULES],
      head: { phone: "", last_name: "", middle_name: "", first_name: "" },
    },
  });
  const kind = useWatch({ control: form.control, name: "environment" });
  const create = useMutation({
    mutationFn: ({ environment, ...values }: Values) =>
      call(
        api.POST("/api/console/schools/", {
          // Un espace de démonstration passe par son propre formulaire.
          body: { ...values, ...schoolBody(values), environment: environment as "live" | "test" },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.schools });
      void queryClient.invalidateQueries({ queryKey: keys.dashboard });
    },
    onError: (error) =>
      setGeneral(
        applyServerErrors(
          error,
          [
            ...SCHOOL_FIELDS,
            "environment",
            "enabled_currencies",
            "default_currency",
            "modules",
            ...HEAD_FIELDS.map((name) => `head.${name}` as const),
          ],
          form.setError,
          t,
        ),
      ),
  });

  if (create.data) return <Done created={create.data} />;

  const errors = form.formState.errors;
  const kindField = (
    <Field
      id="school-environment"
      label={t("console.schools.kindLabel")}
      help={t(`console.schools.kindHelp.${kind}`)}
      error={errors.environment?.message}
    >
      {() => (
        <Controller
          control={form.control}
          name="environment"
          render={({ field }) => (
            <Segmented
              label={t("console.schools.kindLabel")}
              value={field.value}
              onValueChange={field.onChange}
              options={kinds.map((value) => ({
                value,
                label: t(`console.schools.kind.${value}`),
              }))}
            />
          )}
        />
      )}
    </Field>
  );
  if (kind === "demo") return <NewDemoSpace kindField={kindField} />;
  const head = (name: (typeof HEAD_FIELDS)[number], help?: string) => (
    <Field
      id={`head-${name}`}
      label={t(`console.schools.head.${name}`)}
      help={help}
      error={errors.head?.[name]?.message}
    >
      {(control) => (
        <Input
          {...control}
          inputMode={name === "phone" ? "tel" : undefined}
          maxLength={name === "phone" ? 20 : 100}
          {...form.register(`head.${name}`)}
        />
      )}
    </Field>
  );

  return (
    <form
      noValidate
      className="flex flex-col gap-5"
      onSubmit={form.handleSubmit((values) => {
        setGeneral(null);
        create.mutate(values);
      })}
    >
      <PageHeader
        title={t("console.schools.newTitle")}
        subtitle={t("console.schools.newSubtitle")}
        actions={
          <Button type="submit" size="lg" disabled={create.isPending}>
            {t("console.schools.create")}
          </Button>
        }
      />
      {general && <Banner tone="due">{general}</Banner>}
      <div className="grid items-start gap-4 min-[1100px]:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("console.schools.identityTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {kindField}
            <IdentityFields form={form} codeHelp={t("console.schools.fields.codeHelp")} />
            <Field
              id="school-currencies"
              label={t("console.schools.fields.currencies")}
              help={t("console.schools.fields.currenciesHelp")}
              error={errors.enabled_currencies?.message}
            >
              {() => (
                <Controller
                  control={form.control}
                  name="enabled_currencies"
                  render={({ field }) => (
                    <div className="flex flex-wrap gap-4">
                      {CURRENCIES.map((currency) => (
                        <CheckboxField
                          key={currency}
                          id={`currency-${currency}`}
                          label={t(`fees.currencies.${currency}`)}
                          checked={field.value.includes(currency)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              CURRENCIES.filter((c) =>
                                c === currency ? checked === true : field.value.includes(c),
                              ),
                            )
                          }
                        />
                      ))}
                    </div>
                  )}
                />
              )}
            </Field>
            <Field
              id="school-default_currency"
              label={t("console.schools.fields.default_currency")}
              error={errors.default_currency?.message}
            >
              {(control) => (
                <Select {...control} {...form.register("default_currency")}>
                  {CURRENCIES.map((currency: Currency) => (
                    <option key={currency} value={currency}>
                      {t(`fees.currencies.${currency}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </CardContent>
        </Card>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.headTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              {head("phone", t("console.schools.head.phoneHelp"))}
              {head("last_name", t("console.schools.head.lastNameHelp"))}
              {head("middle_name")}
              {head("first_name")}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.modulesTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <p className="text-md text-ink-3">{t("console.schools.modulesCreateHelp")}</p>
              <Controller
                control={form.control}
                name="modules"
                render={({ field }) => (
                  <ModuleChoices chosen={field.value} onChange={field.onChange} />
                )}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("console.schools.subscriptionTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 min-[820px]:grid-cols-2">
              <SubscriptionFields form={form} />
            </CardContent>
          </Card>
        </div>
      </div>
    </form>
  );
}

/** École créée : son adresse et, pour un nouveau compte, le mot de passe provisoire du
 *  directeur, affiché cette seule fois. */
function Done({ created }: { created: Created }) {
  const { t } = useTranslation();
  const name = [created.head.first_name, created.head.last_name].filter(Boolean).join(" ");
  return (
    <>
      <PageHeader title={t("console.schools.createdTitle", { name: created.school.name })} />
      <Card>
        <CardContent className="flex flex-col gap-3 pt-4">
          <p>
            {t("console.schools.createdAddress")}{" "}
            <a href={`${created.school.url}/app/`} className="font-bold text-primary underline">
              {created.school.url.replace(/^\w+:\/\//, "")}
            </a>
          </p>
          {created.temporary_password ? (
            <Banner tone="warn">
              <p>{t("console.schools.temporaryPassword", { name, phone: created.head.phone })}</p>
              <Code className="mt-2 inline-block text-lg">{created.temporary_password}</Code>
              <p className="mt-2 text-sm">{t("console.schools.temporaryPasswordOnce")}</p>
            </Banner>
          ) : (
            <Banner tone="info">{t("console.schools.existingHead", { name })}</Banner>
          )}
          <div className="flex flex-wrap gap-2">
            <Link to={`/schools/${created.school.id}`} className={buttonVariants()}>
              {t("console.schools.openSchool")}
            </Link>
            <Link to="/schools" className={buttonVariants({ variant: "outline" })}>
              {t("console.schools.backToList")}
            </Link>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
