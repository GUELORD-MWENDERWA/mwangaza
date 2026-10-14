import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Brand, Button, cn, Icon, type IconName, PlatformMark } from "@mwangaza/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";

import { accountKey, forgetFamilyData, forgetLastSession } from "../../lib/account";
import { useFamilies } from "../../lib/families";
import { disablePush } from "../../lib/push";
import { NotificationBell } from "../notifications/NotificationBell";

/** Pages du compte (maquettes `accueil`, `enfant-paiements`, `annonces`) : en-tête sombre avec
 *  la marque et la déconnexion, ou, sur la page d'un enfant (`title`), le retour à l'accueil et
 *  son nom, ou, sur une page de la barre du bas (`heading`), la marque et son titre ; une ligne
 *  sous le titre (salutation, école…) ; barre de navigation en bas. */
export function PortalFrame({
  subtitle,
  heading,
  title,
  aside,
  childId,
  children,
}: {
  subtitle?: string;
  heading?: string;
  title?: string;
  /** À droite du titre (photo de l'enfant). */
  aside?: ReactNode;
  /** Enfant affiché : cible de « Paiements » dans la barre du bas. */
  childId?: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const logout = useLogout();
  const families = useFamilies();
  // Démonstration ou essai (4.18) : le bandeau suit la première école qui n'est pas réelle.
  const space = families.data?.find((family) => family.school_environment !== "live");

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {space && (
        <Banner tone="warn" className="rounded-none" role="note">
          <b>{t(`space.${space.school_environment as "demo" | "test"}`)}</b>
        </Banner>
      )}
      <header className="bg-basalt px-4 py-4 text-basalt-ink">
        <div className="mx-auto flex max-w-[640px] items-center justify-between gap-3">
          {heading !== undefined ? (
            <>
              <div className="flex items-center gap-2.5">
                <PlatformMark className="h-[26px] min-w-[26px]" />
                <h1 className="text-lg text-basalt-ink">{heading}</h1>
              </div>
              <NotificationBell />
            </>
          ) : title === undefined ? (
            <>
              <Brand />
              <div className="flex items-center gap-1">
                <NotificationBell />
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
            </>
          ) : (
            <>
              <Link to="/" aria-label={t("portal.child.back")} className="text-basalt-ink">
                <Icon name="back" size={22} />
              </Link>
              <h1 className="min-w-0 flex-1 truncate text-lg text-basalt-ink">{title}</h1>
              {aside}
            </>
          )}
        </div>
        {subtitle && (
          <p className="mx-auto mt-1.5 max-w-[640px] text-sm text-basalt-muted">{subtitle}</p>
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

/** Déconnexion : rien de cette famille ne reste sur le téléphone, ni ses données ni son numéro,
 *  et ses notifications ne s'y affichent plus (téléphone prêté ou partagé). */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      // Avant la fin de la session : le serveur doit encore reconnaître le compte.
      await disablePush().catch(() => undefined);
      return call(api.POST("/api/auth/logout/"));
    },
    onSuccess: async () => {
      forgetLastSession();
      await forgetFamilyData(queryClient);
      queryClient.setQueryData(accountKey, null);
    },
  });
}

/** `.pnav` des maquettes. « Paiements » : l'enfant affiché, sinon le premier de l'accueil.
 */
function PortalNav({ childId }: { childId?: string }) {
  const { t } = useTranslation();
  const families = useFamilies();
  const first = families.data?.find((family) => family.status === "active")?.children[0];
  const payments = childId ?? first?.id;
  // Une entrée n'apparaît que si une école de la famille a le module (M.2.2).
  const offered = (module: "finance" | "communication") =>
    families.data?.some(
      (family) => family.status === "active" && family.school_modules.includes(module),
    ) ?? false;
  const items: { to: string; icon: IconName; label: string }[] = [
    { to: "/", icon: "home", label: t("portal.nav.home") },
  ];
  if (payments && offered("finance")) {
    items.push({ to: `/children/${payments}`, icon: "card", label: t("portal.nav.payments") });
  }
  // La cloche est celle des notifications (en-tête) : les annonces ont le porte-voix.
  if (offered("communication")) {
    items.push({ to: "/announcements", icon: "megaphone", label: t("portal.nav.announcements") });
  }
  items.push({ to: "/calendar", icon: "calendar", label: t("portal.nav.calendar") });
  items.push({ to: "/profile", icon: "user", label: t("portal.nav.profile") });

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
                "flex flex-1 flex-col items-center gap-[3px] p-1 text-xs font-bold no-underline",
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
