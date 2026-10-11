// Démonstration depuis la console (4.17.2, A6) : créer un espace rempli de données fictives
// (petite ou grande école), suivre son remplissage (tâche de fond du serveur), ouvrir sa fiche
// d'accès (le document du serveur, aussi en PDF) et le remettre à zéro. Les espaces de
// `make demo` n'ont pas de ligne `demonstration` : rien de cela ne leur est proposé.
import { zodResolver } from "@hookform/resolvers/zod";
import { api, call, type Schemas } from "@mwangaza/api";
import { applyServerErrors, errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  ConfirmDialog,
  Field,
  Input,
  PageHeader,
  Segmented,
  buttonVariants,
} from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { z } from "zod";

import { keys } from "../../lib/queries";

type Detail = Schemas["ConsoleSchoolDetail"];
type Demo = NonNullable<Detail["demonstration"]>;

const PROFILES = ["small", "large"] as const satisfies readonly Demo["profile"][];
const DEMO_FIELDS = ["name", "code", "profile"] as const;

/** L'espace se remplit ou se remet à zéro : la fiche se relit toute seule. */
export const isWorking = (school: Detail | undefined) =>
  school?.demonstration?.state === "filling" || school?.demonstration?.state === "resetting";

/** « Nouvel espace », type Démonstration : nom, adresse et taille de l'école fictive. */
export function NewDemoSpace({ kindField }: { kindField: ReactNode }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = z.object({
    name: z.string().trim().min(1, t("fieldErrors.required")).max(200),
    code: z.string().trim().min(1, t("fieldErrors.required")).max(30),
    profile: z.enum(PROFILES),
  });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", code: "", profile: "small" },
  });
  const create = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      call(api.POST("/api/console/schools/demo/", { body: values })),
    onSuccess: async (school) => {
      queryClient.setQueryData([...keys.schools, school.id], school);
      void queryClient.invalidateQueries({ queryKey: keys.schools, exact: true });
      await navigate(`/schools/${school.id}`);
    },
    onError: (error) => setGeneral(applyServerErrors(error, [...DEMO_FIELDS], form.setError, t)),
  });
  const errors = form.formState.errors;
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
        subtitle={t("console.demo.newSubtitle")}
        actions={
          <Button type="submit" size="lg" disabled={create.isPending}>
            {t("console.demo.create")}
          </Button>
        }
      />
      {general && <Banner tone="due">{general}</Banner>}
      <Card className="max-w-[640px]">
        <CardContent className="grid gap-4 pt-4">
          {kindField}
          <Field
            id="demo-name"
            label={t("console.schools.fields.name")}
            error={errors.name?.message}
          >
            {(control) => <Input {...control} maxLength={200} {...form.register("name")} />}
          </Field>
          <Field
            id="demo-code"
            label={t("console.schools.fields.code")}
            help={t("console.schools.fields.codeHelp")}
            error={errors.code?.message}
          >
            {(control) => (
              <Input {...control} maxLength={30} autoCapitalize="none" {...form.register("code")} />
            )}
          </Field>
          <Field
            id="demo-profile"
            label={t("console.demo.profileLabel")}
            help={t("console.demo.profileHelp")}
          >
            {() => (
              <Controller
                control={form.control}
                name="profile"
                render={({ field }) => (
                  <Segmented
                    label={t("console.demo.profileLabel")}
                    value={field.value}
                    onValueChange={field.onChange}
                    options={PROFILES.map((value) => ({
                      value,
                      label: t(`console.demo.profile.${value}`),
                    }))}
                  />
                )}
              />
            )}
          </Field>
        </CardContent>
      </Card>
    </form>
  );
}

/** Fiche d'un espace qui se remplit : l'avancement, rien d'autre à faire qu'attendre. */
export function DemoProgress({ school }: { school: Detail & { demonstration: Demo } }) {
  const { t } = useTranslation();
  const { steps_done: done, steps_total: total } = school.demonstration;
  return (
    <>
      <PageHeader title={school.name} subtitle={school.url.replace(/^\w+:\/\//, "")} />
      <Banner tone="info" role="status">
        {t("console.demo.filling", { done, total })}
      </Banner>
      <progress
        className="h-3 w-full max-w-[640px] overflow-hidden rounded-full [&::-moz-progress-bar]:bg-primary [&::-webkit-progress-bar]:bg-line [&::-webkit-progress-value]:bg-primary"
        aria-label={t("console.demo.progressLabel")}
        value={done}
        max={Math.max(total, 1)}
      />
      <p className="text-sm text-ink-3">{t("console.demo.fillingHelp")}</p>
    </>
  );
}

/** Carte « Démonstration » de la fiche : fiche d'accès et remise à zéro. */
export function DemoCard({ school }: { school: Detail & { demonstration: Demo } }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const failed = school.demonstration.state === "failed";
  const reset = useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/console/schools/{id}/reset/", {
          params: { path: { id: school.id } },
          body: { confirm: school.code },
        }),
      ),
    onSuccess: (data) => {
      setOpen(false);
      queryClient.setQueryData([...keys.schools, school.id], data);
    },
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.demo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {failed ? (
          <Banner tone="due">{t("console.demo.failed")}</Banner>
        ) : (
          <p className="text-[.9rem]">
            {t("console.demo.ready", {
              profile: t(`console.demo.profile.${school.demonstration.profile}`),
            })}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {!failed && (
            <Link to={`/schools/${school.id}/access`} className={buttonVariants({ size: "sm" })}>
              {t("console.demo.sheet")}
            </Link>
          )}
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            {t("console.demo.reset")}
          </Button>
        </div>
      </CardContent>
      <ConfirmDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          reset.reset();
        }}
        title={t("console.demo.resetTitle", { name: school.name })}
        confirmLabel={t("console.demo.reset")}
        cancelLabel={t("common.cancel")}
        onConfirm={() => reset.mutate()}
        pending={reset.isPending}
        destructive
      >
        <div className="flex flex-col gap-3">
          <p>{t("console.demo.resetText")}</p>
          {reset.isError && <Banner tone="due">{errorMessage(reset.error, t)}</Banner>}
        </div>
      </ConfirmDialog>
    </Card>
  );
}

/** Fiche d'accès à remettre à un visiteur : l'aperçu du document du serveur, et son PDF. */
export function AccessSheetPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const src = (output: "html" | "pdf") =>
    `/api/console/schools/${encodeURIComponent(id)}/access-sheet/?output=${output}`;
  return (
    <>
      <PageHeader
        title={t("console.demo.sheet")}
        subtitle={t("console.demo.sheetSubtitle")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link to={`/schools/${id}`} className={buttonVariants({ variant: "outline" })}>
              {t("console.demo.backToSpace")}
            </Link>
            <a href={src("pdf")} target="_blank" rel="noreferrer" className={buttonVariants()}>
              {t("console.demo.sheetPdf")}
            </a>
          </div>
        }
      />
      <Card className="overflow-hidden p-0">
        <iframe
          title={t("console.demo.sheet")}
          src={src("html")}
          className="block h-[75vh] min-h-[480px] w-full bg-white"
        />
      </Card>
    </>
  );
}
