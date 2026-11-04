// Bouton d'un usage de l'IA (IA.1.2) : caché sans le module ou le droit `ai.use` (fait par
// l'écran), grisé avec la raison quand le serveur refuserait à coup sûr (IA éteinte, plafond
// atteint, pause, crédits sous le coût d'une réponse). Le serveur revérifie tout au clic.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import { Button } from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { keys } from "../../lib/queries";

export function useAiCredits(enabled = true) {
  return useQuery({
    queryKey: keys.aiCredits,
    queryFn: () => call(api.GET("/api/ai/credits/")),
    enabled,
    staleTime: 60_000,
  });
}

const BLOCKED = ["ai_off", "ai_cap_reached", "ai_paused", "ai_no_credits", "ai_not_available"];
export type Blocked =
  "ai_off" | "ai_cap_reached" | "ai_paused" | "ai_no_credits" | "ai_not_available";

/** Code de refus connu de l'interface ; un code inattendu se lit « usage non donné ». */
export function blockedCode(code: string): Blocked {
  return (BLOCKED.includes(code) ? code : "ai_not_available") as Blocked;
}

/** Raison d'un refus certain pour cet usage, ou `""`. */
export function useAiBlocked(use: string): string {
  const { t } = useTranslation();
  const credits = useAiCredits();
  const row = credits.data?.uses.find((item) => item.code === use);
  const code = credits.data ? (row ? row.blocked : credits.data.blocked || "ai_not_available") : "";
  return code ? t(`ai.blocked.${blockedCode(code)}`) : "";
}

export function AiButton({
  use,
  onClick,
  children,
}: {
  use: string;
  onClick: () => void;
  children: ReactNode;
}) {
  const reason = useAiBlocked(use);
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <Button variant="outline" size="sm" disabled={Boolean(reason)} onClick={onClick}>
        {children}
      </Button>
      {reason && <span className="text-xs text-ink-3">{reason}</span>}
    </span>
  );
}
