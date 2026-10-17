// Places de l'année suivante (8.4.5, maquette `accueil`) : une ligne par enfant à qui l'école
// garde une place, toutes écoles reliées ; le parent répond « revient » ou non, et peut changer
// d'avis tant que l'école ne l'a pas inscrit. La réponse ne crée rien.
import { api, call, type Schemas } from "@mwangaza/api";
import { errorMessage, formatDate, formatDay, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, CardContent, CardHeader, CardTitle, StatusPill } from "@mwangaza/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ChildAvatar } from "../child/ChildAvatar";

type Place = Schemas["PortalPlace"];
const placesKey = ["portal", "places"];

export function PlaceOffers() {
  const { t } = useTranslation();
  const places = useQuery({
    queryKey: placesKey,
    queryFn: () => call(api.GET("/api/portal/places/")),
    staleTime: 60_000,
  });
  if (!places.data?.length) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("portal.places.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col divide-y divide-line-soft">
        {places.data.map((place) => (
          <PlaceLine key={place.id} place={place} />
        ))}
      </CardContent>
    </Card>
  );
}

function PlaceLine({ place }: { place: Place }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const [changing, setChanging] = useState(false);
  const answer = useMutation({
    mutationFn: (value: "yes" | "no") =>
      call(
        api.PUT("/api/portal/places/{id}/", {
          params: { path: { id: place.id } },
          body: { answer: value },
        }),
      ),
    onSuccess: () => {
      setChanging(false);
      void client.invalidateQueries({ queryKey: placesKey });
    },
  });
  const answered = place.answer !== "" && !changing;
  // Accord en français (« Revient-elle ? ») ; l'anglais dit « they ».
  const girl = place.sex === "F";

  return (
    <div className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0">
      <div className="flex items-center gap-3">
        <ChildAvatar name={place.full_name} photo={null} className="size-12" />
        <div className="min-w-0 flex-1">
          <b className="block">{place.full_name}</b>
          <span className="text-sm text-ink-3">
            {place.school_name} · {place.year_name} : <b>{place.class_name}</b>
          </span>
        </div>
      </div>
      {answered ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <StatusPill tone={place.answer === "yes" ? "ok" : "due"}>
            {t(place.answer === "yes" ? "portal.places.answeredYes" : "portal.places.answeredNo", {
              date: place.answered_at
                ? formatDate(place.answered_at, i18n.language, place.school_timezone)
                : "",
            })}
          </StatusPill>
          <Button variant="ghost" size="sm" onClick={() => setChanging(true)}>
            {t("portal.places.change")}
          </Button>
        </div>
      ) : (
        <>
          <span className="text-sm">
            {t(girl ? "portal.places.questionF" : "portal.places.question", {
              date: formatDay(place.starts_on, i18n.language),
            })}
          </span>
          <div className="flex flex-wrap gap-2">
            <Button disabled={answer.isPending} onClick={() => answer.mutate("yes")}>
              {t(girl ? "portal.places.yesF" : "portal.places.yes")}
            </Button>
            <Button
              variant="outline"
              disabled={answer.isPending}
              onClick={() => answer.mutate("no")}
            >
              {t(girl ? "portal.places.noF" : "portal.places.no")}
            </Button>
          </div>
        </>
      )}
      {answer.isError && <Banner tone="due">{errorMessage(answer.error, t)}</Banner>}
    </div>
  );
}
