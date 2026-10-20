// Modules d'une école (M.1) : ce que la plateforme lui donne ; le socle est toujours actif.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
  CheckboxField,
} from "@mwangaza/ui";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

type Detail = Schemas["ConsoleSchoolDetail"];
type Module = Detail["modules"][number];

export const MODULES: Module[] = [
  "students",
  "finance",
  "communication",
  "academics",
  "timetable",
  "portal",
  "notifications",
  "offline",
];

// Même catalogue que `accounts/modules.py` ; le serveur reste maître (il ajoute ce qui manque et
// refuse le reste), ici on évite seulement un aller-retour d'erreur.
const NEEDS: Partial<Record<Module, Module[]>> = {
  finance: ["students"],
  academics: ["students"],
  timetable: ["academics", "students"],
  portal: ["students"],
};

/** Cases des modules avec leurs dépendances : cocher un module coche ce dont il a besoin,
 *  décocher un module décoche ceux qui en ont besoin. */
export function ModuleChoices({
  chosen,
  onChange,
}: {
  chosen: Module[];
  onChange: (modules: Module[]) => void;
}) {
  const { t } = useTranslation();
  const toggle = (code: Module, on: boolean) => {
    const next = new Set(chosen);
    if (on) {
      next.add(code);
      NEEDS[code]?.forEach((needed) => next.add(needed));
    } else {
      next.delete(code);
      MODULES.forEach((other) => {
        if (NEEDS[other]?.includes(code)) next.delete(other);
      });
    }
    onChange(MODULES.filter((m) => next.has(m)));
  };
  return (
    <>
      {MODULES.map((code) => (
        <div key={code}>
          <CheckboxField
            id={`module-${code}`}
            label={t(`console.schools.modules.${code}`)}
            checked={chosen.includes(code)}
            onCheckedChange={(on) => toggle(code, on === true)}
          />
          {NEEDS[code] && (
            <p className="pl-7 text-sm text-ink-3">
              {t("console.schools.modulesNeeds", {
                modules: NEEDS[code].map((m) => t(`console.schools.modules.${m}`)).join(", "),
              })}
            </p>
          )}
        </div>
      ))}
      {chosen.length === 0 && (
        <p className="text-md text-ink-3">{t("console.schools.modulesNone")}</p>
      )}
    </>
  );
}

/** `readOnly` : membre sans le droit de changer cette école (EQ.2) ; il voit les modules. */
export function ModulesCard({
  school,
  onSaved,
  readOnly = false,
}: {
  school: Detail;
  onSaved: (d: Detail) => void;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  const [chosen, setChosen] = useState<Module[]>(school.modules);
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: () =>
      call(
        api.PATCH("/api/console/schools/{id}/", {
          params: { path: { id: school.id } },
          body: { modules: chosen },
        }),
      ),
    onSuccess: (data) => {
      setSaved(true);
      onSaved(data);
    },
  });
  const changed =
    chosen.length !== school.modules.length ||
    chosen.some((code) => !school.modules.includes(code));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("console.schools.modulesTitle")}</CardTitle>
      </CardHeader>
      <CardContent>
        <fieldset disabled={readOnly} className="grid min-w-0 gap-3">
          <p className="text-md text-ink-3">{t("console.schools.modulesHelp")}</p>
          <ModuleChoices
            chosen={chosen}
            onChange={(modules) => {
              setSaved(false);
              setChosen(modules);
            }}
          />
          {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
          {saved && !changed && (
            <Banner tone="ok" role="status">
              {t("console.schools.modulesSaved")}
            </Banner>
          )}
        </fieldset>
      </CardContent>
      {!readOnly && (
        <CardFooter>
          <Button disabled={!changed || save.isPending} onClick={() => save.mutate()}>
            {t("console.schools.save")}
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}
