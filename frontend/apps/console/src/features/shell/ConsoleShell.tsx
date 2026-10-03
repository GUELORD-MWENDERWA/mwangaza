import { useTranslation } from "@mwangaza/i18n";
import {
  Avatar,
  Brand,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  initials,
} from "@mwangaza/ui";
import { NavLink, Outlet } from "react-router";

import { useMe } from "../../lib/queries";
import { useLogout } from "../auth/useGoToStep";
import { ConsoleTag } from "./ConsoleTag";

// Entrées du menu, ajoutées avec leur tâche.
const MENU = [
  { to: "/", key: "dashboard", end: true },
  { to: "/schools", key: "schools", end: false },
  { to: "/accounts", key: "accounts", end: false },
  { to: "/announcements", key: "announcements", end: true },
  { to: "/identity", key: "identity", end: true },
  { to: "/devices", key: "devices", end: true },
  { to: "/journal", key: "journal", end: false },
] as const;

/** Design propre à la console (maquette `console/tableau-de-bord`) : pas de menu latéral comme la
 *  Gestion, une barre du haut en basalte avec la navigation dessous, contenu large et clair. */
export function ConsoleShell() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const logout = useLogout();
  const name = me ? [me.first_name, me.last_name].filter(Boolean).join(" ") : "";

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-basalt text-basalt-ink">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-2.5 px-4 pt-3 min-[820px]:px-6">
          <div className="flex items-center gap-3">
            <Brand />
            <ConsoleTag />
            <span className="flex-1" />
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label={t("console.menu.account")}
                className="flex cursor-pointer items-center gap-2 rounded-full text-sm"
              >
                <Avatar
                  text={me ? initials(me.last_name, me.first_name) : ""}
                  className="bg-basalt-2 text-lamp"
                />
                <b className="hidden min-[820px]:inline">{name}</b>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <a href="/admin/">{t("console.troubleshooting")}</a>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => void logout()}>
                  {t("common.logout")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <nav className="flex gap-1 overflow-x-auto">
            {MENU.map((item) => (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive
                    ? "border-b-[3px] border-lamp px-3 py-2.5 text-[.92rem] font-bold whitespace-nowrap text-white"
                    : "border-b-[3px] border-transparent px-3 py-2.5 text-[.92rem] whitespace-nowrap text-basalt-soft hover:text-white"
                }
              >
                {t(`console.menu.${item.key}`)}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto flex max-w-[1240px] flex-col gap-5 px-4 py-6 min-[820px]:px-6">
        <Outlet />
      </main>
    </div>
  );
}
