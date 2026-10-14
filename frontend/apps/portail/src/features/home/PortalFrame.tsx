import { api, call } from "@mwangaza/api";
import { errorMessage, useTranslation } from "@mwangaza/i18n";
import {
  Banner,
  Brand,
  Button,
  cn,
  DESKTOP,
  Icon,
  type IconName,
  PlatformMark,
  useMediaQuery,
} from "@mwangaza/ui";
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
 *  sous le titre (salutation, école…) ; barre de navigation en bas.
 *  Ordinateur (≥ 1024 px) : barre du haut (marque, navigation, cloche, déconnexion) au lieu de
 *  la barre du bas ; l'en-tête devient le titre de la page (la salutation sur l'accueil) ;
 *  contenu jusqu'à 1 120 px (`wide` : accueil, enfant) ou 760 px pour lire. */
export function PortalFrame({
  subtitle,
  heading,
  title,
  aside,
  childId,
  wide,
  children,
}: {
  subtitle?: string;
  heading?: string;
  title?: string;
  /** À droite du titre (photo de l'enfant). */
  aside?: ReactNode;
  /** Enfant affiché : cible de « Paiements » dans la barre du bas. */
  childId?: string;
  /** Ordinateur : page sur deux colonnes (accueil, enfant). */
  wide?: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const logout = useLogout();
  const families = useFamilies();
  const desktop = useMediaQuery(DESKTOP);
  const home = heading === undefined && title === undefined;
  // Démonstration ou essai (4.18) : le bandeau suit la première école qui n'est pas réelle.
  const space = families.data?.find((family) => family.school_environment !== "live");

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {space && (
        <Banner tone="warn" className="rounded-none" role="note">
          <b>{t(`space.${space.school_environment as "demo" | "test"}`)}</b>
        </Banner>
      )}
      {desktop && (
        <DesktopBar
          childId={childId}
          logoutPending={logout.isPending}
          onLogout={() => logout.mutate()}
        />
      )}
      <header className="relief bg-night px-4 py-4 text-night-ink sm:px-6 lg:px-8 lg:pt-7 lg:pb-8">
        <div className="mx-auto flex max-w-[640px] items-center justify-between gap-3 sm:max-w-[712px] lg:max-w-[1120px]">
          {desktop && home ? (
            <h1 className="text-2xl text-white">{subtitle}</h1>
          ) : desktop && heading !== undefined ? (
            <h1 className="text-2xl text-white">{heading}</h1>
          ) : heading !== undefined ? (
            <>
              <div className="flex items-center gap-2.5">
                <PlatformMark />
                <h1 className="text-lg text-night-ink">{heading}</h1>
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
                  className="text-night-ink"
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
              <Link to="/" aria-label={t("portal.child.back")} className="text-night-ink">
                <Icon name="back" size={22} />
              </Link>
              <h1 className="min-w-0 flex-1 truncate text-lg text-night-ink lg:text-2xl lg:text-white">
                {title}
              </h1>
              {aside}
            </>
          )}
        </div>
        {subtitle && !(desktop && home) && (
          <p className="mx-auto mt-1.5 max-w-[640px] text-sm text-night-soft sm:max-w-[712px] lg:max-w-[1120px] lg:text-md">
            {subtitle}
          </p>
        )}
      </header>
      <main
        className={cn(
          "mx-auto flex w-full max-w-[640px] flex-1 flex-col gap-4 px-4 py-5 sm:max-w-[760px] sm:px-6 lg:gap-5 lg:px-8 lg:py-8",
          wide ? "lg:max-w-[1184px]" : "lg:max-w-[824px]",
        )}
      >
        {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
        {children}
      </main>
      {!desktop && <PortalNav childId={childId} />}
    </div>
  );
}

/** Barre du haut sur ordinateur : marque, mêmes entrées que la barre du bas, cloche, déconnexion. */
function DesktopBar({
  childId,
  logoutPending,
  onLogout,
}: {
  childId?: string;
  logoutPending: boolean;
  onLogout: () => void;
}) {
  const { t } = useTranslation();
  const items = useNavItems(childId);
  return (
    <div className="relief sticky top-0 z-30 h-16 border-b border-night-3 bg-night px-8 text-night-ink">
      <div className="mx-auto flex h-full max-w-[1120px] items-center gap-7">
        <Link to="/" className="text-night-ink no-underline">
          <Brand />
        </Link>
        <nav aria-label={t("portal.nav.label")} className="flex h-full gap-0.5">
          {items.map((item) => (
            <NavLink
              key={item.icon}
              to={item.to}
              end
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 border-y-3 border-transparent px-3 text-md font-semibold no-underline transition-colors",
                  isActive
                    ? "border-b-lamp text-white [&_svg]:text-lamp"
                    : "text-night-soft hover:text-white",
                )
              }
            >
              <Icon name={item.icon} size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1">
          <NotificationBell />
          <Button
            variant="ghost"
            size="sm"
            className="text-night-ink hover:bg-night-2"
            disabled={logoutPending}
            onClick={onLogout}
          >
            <Icon name="logout" size={16} />
            {t("portal.home.logout")}
          </Button>
        </div>
      </div>
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
  const items = useNavItems(childId);

  return (
    <nav
      aria-label={t("portal.nav.label")}
      className="sticky bottom-0 border-t border-line bg-card px-1 pt-1.5 pb-2.5 shadow-raised"
    >
      <div className="mx-auto flex max-w-[640px] sm:max-w-[760px]">
        {items.map((item) => (
          <NavLink
            key={item.icon}
            to={item.to}
            end
            className={({ isActive }) =>
              cn(
                "flex flex-1 flex-col items-center gap-[3px] p-1 text-xs font-semibold no-underline",
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

/** Entrées de la navigation (barre du bas ou du haut) : une entrée n'apparaît que si une école
 *  de la famille a le module (M.2.2). */
function useNavItems(childId?: string) {
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
  return items;
}
