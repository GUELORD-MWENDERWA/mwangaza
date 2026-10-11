// Suppression d'un espace d'essai ou de démonstration (4.16) : confirmée en retapant son code ;
// le serveur la refuse pour un espace réel. Les données s'effacent en tâche de fond : la fiche
// d'un espace « en cours de suppression » ne propose que de relancer une suppression interrompue.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, ConfirmDialog, Field, Input, PageHeader } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { keys } from "../../lib/queries";

type School = Pick<Schemas["ConsoleSchoolDetail"], "id" | "code" | "name" | "url" | "environment">;

function useDeleteSpace(school: School) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: () =>
      call(
        api.POST("/api/console/schools/{id}/delete/", {
          params: { path: { id: school.id } },
          body: { confirm: school.code },
        }),
      ),
    onSuccess: async () => {
      // Retour à l'onglet de l'espace : il y reste « Suppression en cours » puis disparaît.
      await navigate(`/schools?type=${school.environment}`);
      queryClient.removeQueries({ queryKey: [...keys.schools, school.id] });
      void queryClient.invalidateQueries({ queryKey: keys.schools });
    },
  });
}

/** Bouton « Supprimer » et sa confirmation : le code de l'espace, retapé. */
export function DeleteSpace({ school }: { school: School }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [wrong, setWrong] = useState(false);
  const remove = useDeleteSpace(school);
  return (
    <>
      <Button variant="destructive-outline" size="sm" onClick={() => setOpen(true)}>
        {t("console.schools.delete")}
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          setTyped("");
          setWrong(false);
          remove.reset();
        }}
        title={t("console.schools.deleteTitle", { name: school.name })}
        confirmLabel={t("console.schools.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={() =>
          typed.trim().toLowerCase() === school.code ? remove.mutate() : setWrong(true)
        }
        pending={remove.isPending}
        destructive
      >
        <div className="flex flex-col gap-4">
          <p>{t("console.schools.deleteText")}</p>
          {remove.isError && <Banner tone="due">{errorMessage(remove.error, t)}</Banner>}
          <Field
            id="delete-code"
            label={t("console.schools.deleteConfirm", { code: school.code })}
            error={wrong ? t("console.schools.deleteConfirmWrong") : undefined}
          >
            {(control) => (
              <Input
                {...control}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                maxLength={63}
                value={typed}
                onChange={(event) => {
                  setTyped(event.target.value);
                  setWrong(false);
                }}
              />
            )}
          </Field>
        </div>
      </ConfirmDialog>
    </>
  );
}

/** Fiche d'un espace en cours de suppression : plus rien à y changer. */
export function DeletingSpace({ school }: { school: School }) {
  const { t } = useTranslation();
  const relaunch = useDeleteSpace(school);
  return (
    <>
      <PageHeader title={school.name} subtitle={school.url.replace(/^\w+:\/\//, "")} />
      <Banner tone="warn">{t("console.schools.deletingBanner")}</Banner>
      {relaunch.isError && <Banner tone="due">{errorMessage(relaunch.error, t)}</Banner>}
      <p className="text-sm text-ink-3">{t("console.schools.deleteRelaunchHelp")}</p>
      <Button
        variant="outline"
        className="w-fit"
        disabled={relaunch.isPending}
        onClick={() => relaunch.mutate()}
      >
        {t("console.schools.deleteRelaunch")}
      </Button>
    </>
  );
}
