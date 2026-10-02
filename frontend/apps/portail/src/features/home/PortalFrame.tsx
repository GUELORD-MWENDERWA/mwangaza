import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Brand, Button, Icon } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { accountKey } from "../../lib/account";
import { forgetOfflineData } from "../../lib/families";

/** Pages du compte (maquette `accueil`) : en-tête sombre avec la marque, la déconnexion et une
 *  ligne sous le titre (salutation, école…). */
export function PortalFrame({ subtitle, children }: { subtitle?: string; children: ReactNode }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: () => call(api.POST("/api/auth/logout/")),
    onSuccess: async () => {
      // Rien de cette famille ne reste sur le téléphone, ni en mémoire ni hors ligne.
      await forgetOfflineData();
      queryClient.removeQueries({ queryKey: ["portal"] });
      queryClient.setQueryData(accountKey, null);
    },
  });

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-basalt px-4 py-4 text-basalt-ink">
        <div className="mx-auto flex max-w-[640px] items-center justify-between gap-3">
          <Brand />
          <Button
            variant="ghost"
            size="sm"
            className="text-basalt-ink"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            <Icon name="logout" size={16} />
            {t("portal.home.logout")}
          </Button>
        </div>
        {subtitle && (
          <p className="mx-auto mt-1.5 max-w-[640px] text-[.88rem] text-basalt-muted">{subtitle}</p>
        )}
      </header>
      <main className="mx-auto flex max-w-[640px] flex-col gap-4 px-4 py-5">
        {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
        {children}
      </main>
    </div>
  );
}
