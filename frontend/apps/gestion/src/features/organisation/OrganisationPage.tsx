// Organisation scolaire (C1-C3, maquette `organisation-scolaire`) : choix de l'année, onglets
// « Année et périodes », « Niveaux et options », « Classes », « Matricule ». Droit
// `classes.manage` ; réglages en ligne seulement (`03` § 5.2).
import { useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Button,
  Icon,
  PageHeader,
  Select,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@mwangaza/ui";
import { useState } from "react";

import { LoadError } from "../status/StatusPages";
import { ClassesCard } from "./ClassesCard";
import { useYears } from "./data";
import { LevelsCard, TracksCard } from "./LevelsTracks";
import { MatriculeCard } from "./MatriculeCard";
import { NewYearDialog } from "./NewYearDialog";
import { TermsCard } from "./TermsCard";
import { YearCard } from "./YearCard";

export function OrganisationPage() {
  const { t } = useTranslation();
  const years = useYears();
  const [chosen, setChosen] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (years.isPending) return <Skeleton label={t("common.loading")} />;
  if (years.isError) return <LoadError error={years.error} onRetry={() => void years.refetch()} />;

  const list = years.data;
  const year =
    list.find((item) => item.id === chosen) ?? list.find((item) => item.is_current) ?? list[0];
  const newYear = (
    <Button variant="outline" onClick={() => setCreating(true)}>
      <Icon name="plus" size={16} />
      {t("organisation.newYear")}
    </Button>
  );

  return (
    <>
      <PageHeader
        title={t("organisation.title")}
        subtitle={t("organisation.subtitle")}
        actions={
          <>
            {year && (
              <Select
                aria-label={t("organisation.yearChoice")}
                value={year.id}
                onChange={(event) => setChosen(event.target.value)}
                className="w-auto min-w-[240px]"
              >
                {list.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.is_current
                      ? t("organisation.yearOptionCurrent", { name: item.name })
                      : t("organisation.yearOption", { name: item.name })}
                  </option>
                ))}
              </Select>
            )}
            {newYear}
          </>
        }
      />
      {!year ? (
        <Banner tone="info">{t("organisation.noYear")}</Banner>
      ) : (
        <Tabs defaultValue="year">
          <TabsList>
            <TabsTrigger value="year">{t("organisation.tabs.year")}</TabsTrigger>
            <TabsTrigger value="levels">{t("organisation.tabs.levels")}</TabsTrigger>
            <TabsTrigger value="classes">{t("organisation.tabs.classes")}</TabsTrigger>
            <TabsTrigger value="matricule">{t("organisation.tabs.matricule")}</TabsTrigger>
          </TabsList>
          <TabsContent value="year">
            <div className="grid items-start gap-4 min-[1100px]:grid-cols-[1fr_1.4fr]">
              <div className="flex flex-col gap-4">
                <YearCard key={year.id} year={year} onDeleted={() => setChosen(null)} />
                <MatriculeCard />
              </div>
              <TermsCard key={year.id} year={year} />
            </div>
          </TabsContent>
          <TabsContent value="levels">
            <div className="grid items-start gap-4 min-[1100px]:grid-cols-2">
              <LevelsCard />
              <TracksCard />
            </div>
          </TabsContent>
          <TabsContent value="classes">
            <ClassesCard year={year} />
          </TabsContent>
          <TabsContent value="matricule">
            <MatriculeCard />
          </TabsContent>
        </Tabs>
      )}
      <NewYearDialog
        open={creating}
        onOpenChange={setCreating}
        years={list}
        onCreated={(created) => setChosen(created.id)}
      />
    </>
  );
}
