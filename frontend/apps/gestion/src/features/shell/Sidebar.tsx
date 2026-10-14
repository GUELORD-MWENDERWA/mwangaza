// Menu latéral basalte (maquette `tableau-de-bord`) et son contenu, repris dans le menu tiroir
// sous 900 px (M7) : école (changement d'école, M2), entrées permises par le rôle, pied.
import { useTranslation } from "@mwangaza/i18n";
import {
  Brand,
  cn,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Icon,
} from "@mwangaza/ui";
import { Link, NavLink, useNavigate } from "react-router";

import { visibleMenu } from "../../lib/menu";
import type { Me } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useGuide } from "../guide/Guide";
import { PlatformNewsLink } from "../platform-news/PlatformNewsLink";

export function Nav({ me, onNavigate }: { me: Me; onNavigate?: () => void }) {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("shell.mainMenu")} className="flex flex-col gap-0.5">
      {visibleMenu(me).map(({ section, items }) => (
        <div key={section} className="flex flex-col gap-0.5">
          <div className="px-2.5 pt-3.5 pb-1 text-xs text-basalt-muted">
            {t(`shell.sections.${section}`)}
          </div>
          {items.map((item) => (
            <NavLink
              key={item.key}
              to={`/${item.path}`}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "relative flex min-h-11 items-center gap-2.5 rounded-field px-2.5 py-2 text-md text-basalt-ink no-underline hover:bg-basalt-2 min-[900px]:min-h-0",
                  isActive &&
                    "bg-basalt-2 font-bold before:absolute before:top-1.5 before:bottom-1.5 before:-left-3 before:w-1 before:rounded-r-[4px] before:bg-lamp",
                )
              }
            >
              <span className="opacity-85">
                <Icon name={item.icon} />
              </span>
              <span>{t(`shell.menu.${item.key}`)}</span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

/** Encadré de l'école en haut du menu. Plusieurs écoles : il ouvre la liste (M2) ; ouvrir une
 *  autre école = aller à son adresse, où l'on se connecte (session propre à chaque adresse). */
export function SchoolSwitcher({ me }: { me: Me }) {
  const { t } = useTranslation();
  const school = useCurrentSchool();
  const navigate = useNavigate();
  const box = (
    <>
      <span className="min-w-0 flex-1">
        <b className="block truncate text-md">{school.name}</b>
        <span className="block truncate text-basalt-soft">{window.location.host}</span>
      </span>
      {me.schools.length > 1 && <Icon name="chevdown" size={16} />}
    </>
  );
  const boxClasses =
    "flex w-full items-center gap-2 rounded-box bg-basalt-2 px-3 py-2.5 text-left text-sm text-basalt-ink";

  if (me.schools.length <= 1) return <div className={boxClasses}>{box}</div>;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(boxClasses, "cursor-pointer hover:bg-basalt-3")}
        aria-label={`${school.name} — ${t("shell.switchSchool")}`}
      >
        {box}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)]">
        {me.schools.map((item) =>
          item.code === school.code ? (
            <DropdownMenuItem key={item.code} className="bg-lake-50" onSelect={() => navigate("/")}>
              <b>{item.name}</b>
              <span className="text-xs text-ink-3">{t("shell.currentSchool")}</span>
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem key={item.code} disabled={item.status === "suspended"} asChild>
              <a href={`${item.url}/app/`} className="text-ink no-underline">
                {item.name}
              </a>
            </DropdownMenuItem>
          ),
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-lake" onSelect={() => navigate("/schools")}>
          {t("shell.allSchools")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Menu latéral des écrans larges (≥ 900 px). */
export function Sidebar({ me }: { me: Me }) {
  const { t } = useTranslation();
  const { restart } = useGuide();
  return (
    <aside className="sticky top-0 hidden h-screen flex-col gap-1 overflow-y-auto bg-basalt px-3 py-[18px] text-basalt-ink min-[900px]:flex">
      <Link to="/" className="px-2.5 pt-1 pb-[18px] text-basalt-ink no-underline">
        <Brand />
      </Link>
      <SchoolSwitcher me={me} />
      <div className="mt-3">
        <Nav me={me} />
      </div>
      <div className="mt-auto px-2.5">
        <PlatformNewsLink />
      </div>
      <div className="p-2.5 text-xs text-basalt-muted">
        {t("common.version", { version: __APP_VERSION__ })}
        {restart && (
          <>
            {" · "}
            <button
              type="button"
              onClick={restart}
              className="cursor-pointer text-basalt-soft underline-offset-2 hover:underline"
            >
              {t("guide.help")}
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
