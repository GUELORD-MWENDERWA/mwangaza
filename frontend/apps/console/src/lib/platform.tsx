import { cachedPlatform, loadPlatform } from "@mwangaza/api";
import { setPlatformName } from "@mwangaza/i18n";
import { applyPlatform, NO_PLATFORM, PlatformContext } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect } from "react";

import { keys } from "./queries";

/** Avant le premier affichage : l'identité gardée sur l'appareil (sans réseau aussi). */
export function startPlatform() {
  const cached = cachedPlatform();
  setPlatformName(cached?.name ?? "");
  if (cached) applyPlatform(cached);
}

/** Identité de la plateforme (5.1) pour toute l'application, relue sur le serveur. */
export function PlatformProvider({ children }: { children: ReactNode }) {
  const { data = NO_PLATFORM } = useQuery({
    queryKey: keys.platform,
    queryFn: loadPlatform,
    initialData: cachedPlatform() ?? undefined,
    staleTime: 5 * 60_000,
  });
  useEffect(() => {
    setPlatformName(data.name);
    applyPlatform(data);
    document.title = data.name;
  }, [data]);
  return <PlatformContext value={data}>{children}</PlatformContext>;
}
