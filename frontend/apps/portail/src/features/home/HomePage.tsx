import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Brand, Button, Card, CardContent, Icon } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOutletContext } from "react-router";

import { type Account, accountKey } from "../../lib/account";
import { LanguageLinks } from "../auth/AuthFrame";

/** Accueil du compte. Les enfants, leurs paiements et les annonces arrivent avec la tâche 4.4.2
 *  (maquette `accueil`). */
export function HomePage() {
  const { t } = useTranslation();
  const account = useOutletContext<Account>();
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: () => call(api.POST("/api/auth/logout/")),
    onSuccess: () => queryClient.setQueryData(accountKey, null),
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
      </header>
      <main className="mx-auto flex max-w-[640px] flex-col gap-4 px-4 py-5">
        <h1 className="text-[1.5rem]">{t("portal.home.greeting", { name: account.name })}</h1>
        {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
        <Card>
          <CardContent>{t("portal.home.soon")}</CardContent>
        </Card>
        <LanguageLinks />
      </main>
    </div>
  );
}
