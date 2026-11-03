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
import { NavLink, Outlet, matchPath, useLocation } from "react-router";

import { useMe } from "../../lib/queries";
import { RIGHTS, type MenuItem, menuGroups, useCan } from "../../lib/rights";
import { useLogout } from "../auth/useGoToStep";
import { useAlertMessages } from "../journal/AlertsCard";
import { ConsoleTag } from "./ConsoleTag";

/** Design propre à la console (maquette `console/tableau-de-bord`) : pas de menu latéral comme la
 *  Gestion, une barre du haut en bleu nuit avec la navigation dessous, contenu large et clair. Le
 *  menu ne montre que les pages des rôles du membre (EQ.2, `lib/rights.ts`). */
export function ConsoleShell() {
  const { t } = useTranslation();
  const { data: me } = useMe();
  const logout = useLogout();
  const can = useCan();
  useAlertMessages();
  const name = me ? [me.first_name, me.last_name].filter(Boolean).join(" ") : "";

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-night text-night-ink">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-2.5 px-4 pt-3 min-[820px]:px-6">
          <div className="flex items-center gap-3">
            <Brand inverse />
            <ConsoleTag />
            <span className="flex-1" />
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label={t("console.menu.account")}
                className="flex cursor-pointer items-center gap-2 rounded-full text-sm"
              >
                <Avatar
                  text={me ? initials(me.last_name, me.first_name) : ""}
                  className="bg-night-2 text-lamp"
                />
                <b className="hidden min-[820px]:inline">{name}</b>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {/* Administration de dépannage : propriétaire seulement (EQ.1). */}
                {can(RIGHTS.teamManage) && (
                  <>
                    <DropdownMenuItem asChild>
                      <a href="/admin/">{t("console.troubleshooting")}</a>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}
                <DropdownMenuItem onSelect={() => void logout()}>
                  {t("common.logout")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <nav className="flex gap-1">
            {menuGroups(can).map((group) =>
              group.items.length === 1 ? (
                <MenuLink key={group.key} item={group.items[0]!} />
              ) : (
                <MenuGroup key={group.key} name={group.key} items={group.items} />
              ),
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto flex max-w-[1240px] flex-col gap-6 px-4 py-6 min-[820px]:px-6 min-[820px]:py-8">
        <Outlet />
      </main>
    </div>
  );
}

const TAB = "border-b-[3px] px-3 py-2.5 text-md font-semibold whitespace-nowrap transition-colors";
const ON = `${TAB} border-lamp text-white`;
const OFF = `${TAB} border-transparent text-night-soft hover:text-white`;

function MenuLink({ item }: { item: MenuItem }) {
  const { t } = useTranslation();
  return (
    <NavLink to={item.to} end={item.end} className={({ isActive }) => (isActive ? ON : OFF)}>
      {t(`console.menu.${item.key}`)}
    </NavLink>
  );
}

/** Un groupe de pages sous un seul titre de la barre ; souligné quand une de ses pages est ouverte. */
function MenuGroup({
  name,
  items,
}: {
  name: "clients" | "site" | "platform" | "dashboard";
  items: MenuItem[];
}) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const active = items.some((item) => matchPath({ path: item.to, end: item.end }, pathname));
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={`cursor-pointer ${active ? ON : OFF}`}>
        {t(`console.menu.groups.${name}`)}
        <span aria-hidden className="ml-1.5 text-xs">
          ▾
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {items.map((item) => (
          <DropdownMenuItem key={item.key} asChild>
            <NavLink to={item.to} end={item.end}>
              {t(`console.menu.${item.key}`)}
            </NavLink>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
