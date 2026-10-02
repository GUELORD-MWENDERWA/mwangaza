import { api, call, ensureCsrf } from "@mwangaza/api";
import { applyServerErrors, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, buttonVariants, Card, CardContent, Field } from "@mwangaza/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router";
import { z } from "zod";

import { familiesKey } from "../../lib/families";
import { FamilyCodeInput } from "../auth/FamilyCodeInput";
import { PortalFrame } from "./PortalFrame";

/** « Ajouter un enfant d'une autre école » (H2) : le code famille remis par cette école ; elle
 *  doit avoir le numéro du compte pour son contact principal. Jamais par le numéro seul. */
export function AddSchoolPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [general, setGeneral] = useState<string | null>(null);
  const schema = useMemo(
    () => z.object({ code: z.string().trim().min(1, t("validation.codeRequired")) }),
    [t],
  );
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { code: "" } });
  const link = useMutation({
    mutationFn: async (values: z.infer<typeof schema>) => {
      await ensureCsrf();
      return call(api.POST("/api/portal/families/link/", { body: values }));
    },
    onMutate: () => setGeneral(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: familiesKey });
      void navigate("/");
    },
    onError: (error) => setGeneral(applyServerErrors(error, ["code"], form.setError, t)),
  });

  return (
    <PortalFrame>
      <Card>
        <CardContent>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={form.handleSubmit((values) => link.mutate(values))}
          >
            <h1 className="text-[1.4rem]">{t("portal.addSchool.title")}</h1>
            <p className="text-ink-2">{t("portal.addSchool.help")}</p>
            {general && <Banner tone="due">{general}</Banner>}
            <Field
              id="code"
              label={t("portal.activate.code")}
              help={t("portal.addSchool.codeHint")}
              error={form.formState.errors.code?.message}
            >
              {(control) => <FamilyCodeInput {...control} {...form.register("code")} />}
            </Field>
            <Button type="submit" size="lg" disabled={link.isPending}>
              {t("portal.addSchool.submit")}
            </Button>
            <Link to="/" className={buttonVariants({ variant: "ghost" })}>
              {t("common.cancel")}
            </Link>
          </form>
        </CardContent>
      </Card>
    </PortalFrame>
  );
}
