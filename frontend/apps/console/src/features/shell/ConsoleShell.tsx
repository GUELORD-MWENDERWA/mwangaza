// Coquille de la console (lot 5, ②bis, maquettes `console/tableau-de-bord` et `console/menu`) : la
// même que la Gestion — menu latéral bleu nuit avec l'interrupteur Réel / Démonstration, barre du
// haut (recherche, état des services, journal, compte), menu tiroir sous 900 px, bandeau orange
// en démonstration. Le menu ne montre que les pages des rôles du membre (EQ.2) et du mode.
import { api, call } from "@mwangaza/api";
import { useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Brand,
  Button,
  cn,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Icon,
  initials,
  Sheet,
  SheetClose,
  SheetContent,
  SheetTrigger,
} from "@mwangaza/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router";

import { useConsoleMode } from "../../lib/mode";
import { keys, useMe } from "../../lib/queries";
import { RIGHTS, menuGroups, useCan } from "../../lib/rights";
import { useLogout } from "../auth/useGoToStep";
import { useAlertMessages } from "../journal/AlertsCard";
import { ConsoleSearch } from "./ConsoleSearch";
import { ConsoleTag } from "./ConsoleTag";
import { DemoBanner, ModeSwitch } from "./ModeSwitch";

export function ConsoleShell() {
  const mode = useConsoleMode();
  useAlertMessages();
  return (
    <div className="min-h-screen bg-surface min-[900px]:grid min-[900px]:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col gap-1 overflow-y-auto bg-night px-3 py-[18px] text-night-ink min-[900px]:flex">
        <BrandLine />
        <ModeSwitch />
        <div className="mt-1">
          <Nav />
        </div>
        <SidebarFoot />
      </aside>
      <div className="flex min-w-0 flex-col">
        <div className="sticky top-0 z-30">
          <DemoBanner />
          <TopBar />
        </div>
        {/* Changer de mode recrée la page : rien de l'autre mode ne reste affiché. */}
        <main
          key={mode}
          className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 p-4 min-[900px]:p-8 min-[900px]:pt-7"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function BrandLine({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link
      to="/"
      onClick={onNavigate}
      className="flex flex-wrap items-center gap-x-2.5 gap-y-2 px-2.5 pt-1 pb-[18px] text-night-ink no-underline"
    >
      <Brand inverse />
      <ConsoleTag />
    </Link>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation();
  const can = useCan();
  const mode = useConsoleMode();
  return (
    <nav aria-label={t("console.shell.mainMenu")} className="flex flex-col gap-0.5">
      {menuGroups(can, mode).map(({ key, items }) => (
        <div key={key} className="flex flex-col gap-0.5">
          <div className="px-2.5 pt-4 pb-1.5 text-xs font-semibold tracking-wider text-night-muted uppercase">
            {t(`console.menu.groups.${key}`)}
          </div>
          {items.map((item) => (
            <NavLink
              key={item.key}
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "group relative flex min-h-11 items-center gap-3 rounded-field px-2.5 py-2 text-md text-night-soft no-underline transition-colors hover:bg-night-2 hover:text-white min-[900px]:min-h-0",
                  isActive &&
                    "bg-night-2 font-semibold text-white before:absolute before:top-1.5 before:bottom-1.5 before:-left-3 before:w-1 before:rounded-r-[4px] before:bg-lamp",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span className={cn("shrink-0", isActive ? "text-lamp" : "opacity-80")}>
                    <Icon name={item.icon} />
                  </span>
                  <span>{t(`console.menu.${item.key}`)}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

function SidebarFoot() {
  const { t } = useTranslation();
  const can = useCan();
  // Administration de dépannage : propriétaire seulement (EQ.1).
  if (!can(RIGHTS.teamManage)) return null;
  return (
    <div className="mt-auto p-2.5 text-xs">
      <a href="/admin/" className="text-night-soft underline-offset-2 hover:underline">
        {t("console.troubleshooting")}
      </a>
    </div>
  );
}

/** Nom et rôles du membre connecté. */
function useMember() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  return {
    name: me ? [me.first_name, me.last_name].filter(Boolean).join(" ") : "",
    initials: me ? initials(me.last_name, me.first_name) : "",
    roles: (me?.platform_roles ?? [])
      .map((role) => t(`console.team.roleNames.${role}`, { defaultValue: role }))
      .join(", "),
  };
}

function TopBar() {
  const { t } = useTranslation();
  const can = useCan();
  const member = useMember();
  const logout = useLogout();
  return (
    <header className="flex h-14 items-center gap-2.5 border-b border-line bg-card/90 px-3 backdrop-blur min-[900px]:h-16 min-[900px]:gap-4 min-[900px]:px-8">
      <MobileMenu />
      <ConsoleSearch />
      {can(RIGHTS.schoolsView, RIGHTS.healthView) && <ServicesPill />}
      {can(RIGHTS.auditView) && (
        <Link
          to="/journal"
          aria-label={t("console.shell.alerts")}
          title={t("console.shell.alerts")}
          className="grid size-11 place-items-center rounded-field text-ink-2 hover:bg-surface"
        >
          <Icon name="bell" />
        </Link>
      )}
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`${member.name} | ${t("console.menu.account")}`}
          className="flex cursor-pointer items-center gap-2.5 text-sm text-ink"
        >
          <span className="hidden text-right min-[900px]:block">
            <b>{member.name}</b>
            <br />
            <span className="text-sm text-ink-3">{member.roles}</span>
          </span>
          <Avatar text={member.initials} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {can(RIGHTS.teamManage) && (
            <>
              <DropdownMenuItem asChild>
                <a href="/admin/">{t("console.troubleshooting")}</a>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuItem onSelect={() => void logout()}>{t("common.logout")}</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

const PILL_DOTS = { ok: "bg-ok", warning: "bg-warn", error: "bg-due", off: "bg-ink-3" } as const;
const PILL_TEXTS = {
  ok: "console.health.allGood",
  off: "console.health.allGood",
  warning: "console.health.warning",
  error: "console.health.error",
} as const;

/** État des services, vérifié toutes les deux minutes ; il mène au tableau de bord. */
function ServicesPill() {
  const { t } = useTranslation();
  const health = useQuery({
    queryKey: keys.health,
    queryFn: () => call(api.GET("/api/console/health/")),
    refetchInterval: 120_000,
    staleTime: 60_000,
  });
  if (!health.data) return null;
  const { status } = health.data;
  return (
    <Link
      to="/"
      className="flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border border-line px-2.5 text-xs text-ink-2 no-underline hover:bg-surface min-[900px]:text-sm"
    >
      <i aria-hidden="true" className={cn("size-2 rounded-full", PILL_DOTS[status])} />
      <span className="min-[900px]:hidden">{t("console.shell.services")}</span>
      <b className="hidden font-semibold min-[900px]:inline">{t(PILL_TEXTS[status])}</b>
    </Link>
  );
}

/** Menu tiroir sous 900 px : se ferme en touchant à côté, avec Échap, ou après un choix. */
function MobileMenu() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const member = useMember();
  const logout = useLogout();
  const close = () => setOpen(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="size-11 shrink-0 p-0 min-[900px]:hidden">
          <Icon name="menu" />
          <span className="sr-only">{t("shell.openMenu")}</span>
        </Button>
      </SheetTrigger>
      <SheetContent title={t("console.shell.mainMenu")}>
        <div className="flex items-start justify-between">
          <BrandLine onNavigate={close} />
          <SheetClose className="grid size-11 shrink-0 cursor-pointer place-items-center text-night-soft">
            <Icon name="x" />
            <span className="sr-only">{t("shell.closeMenu")}</span>
          </SheetClose>
        </div>
        <ModeSwitch onSwitch={close} />
        <div className="mt-1">
          <Nav onNavigate={close} />
        </div>
        <div className="mt-auto flex items-center gap-2.5 border-t border-night-3 px-1.5 pt-2.5 text-sm">
          <Avatar text={member.initials} className="size-[30px] text-xs" />
          <span className="min-w-0 flex-1">
            <b className="block truncate">{member.name}</b>
            <span className="block truncate text-night-muted">{member.roles}</span>
          </span>
          <button
            type="button"
            onClick={() => void logout()}
            className="grid size-11 cursor-pointer place-items-center text-night-soft"
          >
            <Icon name="logout" />
            <span className="sr-only">{t("common.logout")}</span>
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
