import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Brand, Button, cn, Icon, type IconName } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";

import { accountKey } from "../../lib/account";
import { forgetOfflineData, useFamilies } from "../../lib/families";

/** Pages du compte (maquettes `accueil`, `enfant-paiements`) : en-tête sombre avec la marque et
 *  la déconnexion, ou, sur la page d'un enfant (`title`), le retour à l'accueil et son nom ; une
 *  ligne sous le titre (salutation, école…) ; barre de navigation en bas. */
export function PortalFrame({
  subtitle,
  title,
  aside,
  childId,
  children,
}: {
  subtitle?: string;
  title?: string;
  /** À droite du titre (photo de l'enfant). */
  aside?: ReactNode;
  /** Enfant affiché : cible de « Paiements » dans la barre du bas. */
  childId?: string;
  children: ReactNode;
}) {
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
    <div className="flex min-h-screen flex-col bg-background">
      <header className="bg-basalt px-4 py-4 text-basalt-ink">
        <div className="mx-auto flex max-w-[640px] items-center justify-between gap-3">
          {title === undefined ? (
            <>
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
            </>
          ) : (
            <>
              <Link to="/" aria-label={t("portal.child.back")} className="text-basalt-ink">
                <Icon name="back" size={22} />
              </Link>
              <h1 className="min-w-0 flex-1 truncate text-[1.1rem] text-basalt-ink">{title}</h1>
              {aside}
            </>
          )}
        </div>
        {subtitle && (
          <p className="mx-auto mt-1.5 max-w-[640px] text-[.88rem] text-basalt-muted">{subtitle}</p>
        )}
      </header>
      <main className="mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-4 px-4 py-5">
        {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
        {children}
      </main>
      <PortalNav childId={childId} />
    </div>
  );
}

/** `.pnav` des maquettes. « Paiements » : l'enfant affiché, sinon le premier de l'accueil.
 *  Annonces et Profil s'ajoutent avec leurs écrans (4.4.4, 4.4.5). */
function PortalNav({ childId }: { childId?: string }) {
  const { t } = useTranslation();
  const families = useFamilies();
  const first = families.data?.find((family) => family.status === "active")?.children[0];
  const payments = childId ?? first?.id;
  const items: { to: string; icon: IconName; label: string }[] = [
    { to: "/", icon: "home", label: t("portal.nav.home") },
  ];
  if (payments) {
    items.push({ to: `/children/${payments}`, icon: "card", label: t("portal.nav.payments") });
  }

  return (
    <nav
      aria-label={t("portal.nav.label")}
      className="sticky bottom-0 border-t border-line bg-card px-1 pt-1.5 pb-2.5"
    >
      <div className="mx-auto flex max-w-[640px]">
        {items.map((item) => (
          <NavLink
            key={item.icon}
            to={item.to}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center gap-[3px] p-1 text-[.72rem] font-bold no-underline",
                isActive ? "text-lake" : "text-ink-3",
              )
            }
          >
            <Icon name={item.icon} size={22} />
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
