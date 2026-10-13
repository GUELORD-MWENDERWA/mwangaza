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
  "portal",
  "notifications",
  "offline",
];

export function ModulesCard({ school, onSaved }: { school: Detail; onSaved: (d: Detail) => void }) {
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
      <CardContent className="grid gap-3">
        <p className="text-[.9rem] text-ink-3">{t("console.schools.modulesHelp")}</p>
        {MODULES.map((code) => (
          <CheckboxField
            key={code}
            id={`module-${code}`}
            label={t(`console.schools.modules.${code}`)}
            checked={chosen.includes(code)}
            onCheckedChange={(on) => {
              setSaved(false);
              setChosen(on === true ? [...chosen, code] : chosen.filter((c) => c !== code));
            }}
          />
        ))}
        {chosen.length === 0 && (
          <p className="text-[.9rem] text-ink-3">{t("console.schools.modulesNone")}</p>
        )}
        {save.isError && <Banner tone="due">{errorMessage(save.error, t)}</Banner>}
        {saved && !changed && (
          <Banner tone="ok" role="status">
            {t("console.schools.modulesSaved")}
          </Banner>
        )}
      </CardContent>
      <CardFooter>
        <Button disabled={!changed || save.isPending} onClick={() => save.mutate()}>
          {t("console.schools.save")}
        </Button>
      </CardFooter>
    </Card>
  );
}
