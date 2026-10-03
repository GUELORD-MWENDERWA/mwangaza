// Coquille de la Gestion (maquettes `tableau-de-bord` et `menu-mobile`, M7) : menu latéral, barre
// du haut avec l'état du réseau et le compte, menu tiroir sous 900 px, bandeau de session support.
import { useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Brand,
  Button,
  initials,
  Icon,
  Sheet,
  SheetClose,
  SheetContent,
  SheetTrigger,
} from "@mwangaza/ui";
import { useEffect, useState } from "react";
import { Link, Navigate, Outlet } from "react-router";

import { keepForOfflineStart } from "../../lib/device";
import { errorMessage } from "../../lib/errors";
import { displayName, rolesLabel } from "../../lib/people";
import { can } from "../../lib/permissions";
import { useCurrentMe, type Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useLogout } from "../../lib/session";
import { GuideProvider, useGuide } from "../guide/Guide";
import { PlatformNewsBanner } from "../platform-news/PlatformNewsBanner";
import { PlatformNewsLink } from "../platform-news/PlatformNewsLink";
import { SearchPalette } from "./SearchPalette";
import { Nav, SchoolSwitcher, Sidebar } from "./Sidebar";
import { SupportBanner } from "./SupportBanner";
import { StorageBanner, SyncMenu, useSyncSession } from "./SyncMenu";

export function AppShell() {
  const me = useCurrentMe();
  const school = useCurrentSchool();
  useSyncSession(me);
  // Gardés sur l'appareil mémorisé : l'application démarrera sans réseau (B5).
  useEffect(() => void keepForOfflineStart(me, school).catch(() => undefined), [me, school]);
  // Aucun droit dans cette école : le support ouvre sa session, les autres choisissent une école.
  if (!me.school) return <Navigate to={me.is_platform_admin ? "/support" : "/schools"} replace />;
  return (
    <GuideProvider me={me}>
      <div className="min-h-screen min-[900px]:grid min-[900px]:grid-cols-[248px_minmax(0,1fr)]">
        <Sidebar me={me} />
        <div className="flex min-w-0 flex-col">
          {/* Bandeau support et barre du haut restent visibles en faisant défiler. */}
          <div className="sticky top-0 z-30">
            {me.support && <SupportBanner support={me.support} />}
            <TopBar me={me} />
          </div>
          <main className="flex w-full max-w-[1360px] flex-col gap-5 p-4 min-[900px]:p-6">
            <PlatformNewsBanner />
            <StorageBanner />
            <Outlet />
          </main>
        </div>
      </div>
    </GuideProvider>
  );
}

/** Rôle affiché sous le nom : « Support Mwangaza » pendant une session support. */
function useRoleLine(me: Me) {
  const { t } = useTranslation();
  return me.support ? t("roles.support") : rolesLabel(me.school?.roles ?? [], t);
}

function TopBar({ me }: { me: Me }) {
  const { t } = useTranslation();
  const roleLine = useRoleLine(me);
  return (
    <header className="flex h-14 items-center gap-2.5 border-b border-line bg-card px-3 min-[900px]:h-[60px] min-[900px]:gap-4 min-[900px]:px-6">
      <MobileMenu me={me} />
      {can(me, ["students.view"]) && <SearchPalette />}
      <SyncMenu className="max-[899px]:px-[9px] max-[899px]:py-[5px] max-[899px]:text-[.78rem]" />
      <Link
        to="/account"
        className="ml-auto flex items-center gap-2.5 text-[.88rem] text-ink no-underline"
        aria-label={`${displayName(me)} — ${t("shell.account")}`}
      >
        <span className="hidden text-right min-[900px]:block">
          <b>{displayName(me)}</b>
          <br />
          <span className="text-sm text-ink-3">{roleLine}</span>
        </span>
        <Avatar text={initials(me.last_name, me.first_name, me.middle_name)} />
      </Link>
    </header>
  );
}

/** Menu tiroir (M7) : se ferme en touchant à côté, avec Échap, ou après un choix. */
function MobileMenu({ me }: { me: Me }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const logout = useLogout();
  const { restart } = useGuide();
  const close = () => setOpen(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="size-11 p-0 min-[900px]:hidden">
          <Icon name="menu" />
          <span className="sr-only">{t("shell.openMenu")}</span>
        </Button>
      </SheetTrigger>
      <SheetContent title={t("shell.mainMenu")}>
        <div className="flex items-center justify-between px-1.5 pt-0.5 pb-2.5">
          <Link to="/" onClick={close} className="text-basalt-ink no-underline">
            <Brand />
          </Link>
          <SheetClose className="grid size-11 cursor-pointer place-items-center text-basalt-soft">
            <Icon name="x" />
            <span className="sr-only">{t("shell.closeMenu")}</span>
          </SheetClose>
        </div>
        <SchoolSwitcher me={me} />
        <div className="mt-1">
          <Nav me={me} onNavigate={close} />
        </div>
        <div className="mt-auto flex flex-col gap-1 border-t border-basalt-3 px-1.5 pt-2.5">
          <div className="flex items-center gap-2.5">
            <Link
              to="/account"
              onClick={close}
              className="flex min-h-11 min-w-0 flex-1 items-center gap-2.5 text-sm text-basalt-ink no-underline"
            >
              <Avatar
                text={initials(me.last_name, me.first_name, me.middle_name)}
                className="size-[30px] text-[.72rem]"
              />
              <span className="min-w-0">
                <b className="block truncate">{displayName(me)}</b>
                <span className="text-basalt-muted">{t("shell.account")}</span>
              </span>
            </Link>
            <button
              type="button"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="grid size-11 cursor-pointer place-items-center text-basalt-soft"
            >
              <Icon name="logout" />
              <span className="sr-only">{t("common.logout")}</span>
            </button>
          </div>
          <PlatformNewsLink onClick={close} />
          {restart && (
            <button
              type="button"
              onClick={() => {
                close();
                restart();
              }}
              className="flex min-h-11 cursor-pointer items-center gap-2.5 text-sm text-basalt-soft"
            >
              <Icon name="info" size={18} />
              {t("guide.help")}
            </button>
          )}
          {logout.isError && (
            <p role="alert" className="text-xs text-lamp">
              {errorMessage(logout.error, t)}
            </p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
