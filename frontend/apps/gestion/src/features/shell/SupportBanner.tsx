import { api, call, type Schemas } from "@mwangaza/api";
import { formatTime, Trans, useTranslation } from "@mwangaza/i18n";
import { Button, Icon } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { errorMessage } from "../../lib/errors";
import { keys } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";

/** Bandeau rouge de la session support (A3), en haut de chaque écran tant qu'elle est ouverte :
 *  école, heure de fin (heure de l'école), motif, « Quitter ». À l'heure de fin, le compte est
 *  relu : la session n'existe plus et l'écran revient à l'ouverture de session. */
export function SupportBanner({ support }: { support: Schemas["SupportSession"] }) {
  const { t, i18n } = useTranslation();
  const school = useCurrentSchool();
  const queryClient = useQueryClient();
  const quit = useMutation({
    mutationFn: () => call(api.DELETE("/api/support/")),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.me }),
  });

  useEffect(() => {
    const delay = Math.max(Date.parse(support.expires_at) - Date.now(), 0) + 1_000;
    const timer = setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: keys.me });
    }, delay);
    return () => clearTimeout(timer);
  }, [support.expires_at, queryClient]);

  return (
    <div
      role="region"
      aria-label={t("support.bannerLabel")}
      className="flex flex-wrap items-center gap-2.5 bg-due px-3.5 py-2.5 text-sm text-white"
    >
      <Icon name="shield" />
      <div className="min-w-0 flex-1">
        <div>
          <Trans
            i18nKey="support.banner"
            values={{
              school: support.school.name,
              time: formatTime(support.expires_at, i18n.language, school.timezone),
            }}
            components={{ b: <b /> }}
          />
        </div>
        <div>{t("support.bannerReason", { reason: support.reason })}</div>
        {quit.isError && <div role="alert">{errorMessage(quit.error, t)}</div>}
      </div>
      <Button
        size="sm"
        variant="outline"
        className="border-white text-due hover:bg-due-50"
        onClick={() => quit.mutate()}
        disabled={quit.isPending}
      >
        <Icon name="logout" size={16} />
        {t("support.quit")}
      </Button>
    </div>
  );
}
