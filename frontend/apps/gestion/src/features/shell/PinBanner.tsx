// Bandeau « Travailler sans internet » (maquette `hors-ligne-preparer`, L.6) : sur un appareil
// mémorisé sans code PIN, l'application ne rouvrirait pas sans réseau. Le PIN se choisit sur la
// carte de « Mon compte ».
import { useTranslation } from "@mwangaza/i18n";
import { Banner, Button } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useMatch } from "react-router";

import { localDevice } from "../../lib/device";
import { keys, type Me } from "../../lib/queries";

const LATER = "mwangaza.pinLater";

function laterChosen() {
  try {
    return sessionStorage.getItem(LATER) === "1";
  } catch {
    return false;
  }
}

export function PinBanner({ me }: { me: Me }) {
  const { t } = useTranslation();
  const [hidden, setHidden] = useState(laterChosen);
  const onAccount = useMatch("/account");
  // Même clé que la carte PIN : le bandeau disparaît dès que le code est enregistré.
  const device = useQuery({
    queryKey: [...keys.localDevice, me.id],
    queryFn: async () => (await localDevice(me.id)) ?? null,
    retry: false,
    enabled: !me.support,
  });
  if (me.support || hidden || onAccount || !device.data || device.data.pin) return null;

  function later() {
    try {
      sessionStorage.setItem(LATER, "1");
    } catch {
      // Stockage refusé : caché pour cet écran seulement.
    }
    setHidden(true);
  }

  return (
    <Banner tone="info" icon="lock" role="region" aria-label={t("shell.pin.title")}>
      <b>{t("shell.pin.title")}</b>
      <p className="mt-0.5">{t("shell.pin.text")}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button size="sm" asChild>
          <Link to="/account#pin">{t("shell.pin.choose")}</Link>
        </Button>
        <Button size="sm" variant="ghost" onClick={later}>
          {t("shell.pin.later")}
        </Button>
      </div>
    </Banner>
  );
}
