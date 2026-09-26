import { formatVisit, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Card, Icon, SchoolBadge, StatusPill, Tag, cn } from "@mwangaza/ui";
import { Link } from "react-router";

import { errorMessage } from "../../lib/errors";
import { displayName, roleName } from "../../lib/people";
import { useCurrentMe } from "../../lib/queries";
import { useCurrentSchool } from "../../lib/school";
import { useLogout } from "../../lib/session";
import { AuthFrame } from "../auth/AuthFrame";

/** Choisir l'école (M2) : depuis « Toutes mes écoles… », ou quand le compte n'a aucun rôle dans
 *  l'école de cette adresse. Seules les écoles où il a une appartenance active ; suspendue :
 *  grisée. Ouvrir une école = aller à son adresse et s'y connecter (session propre à chacune). */
export function SchoolChoicePage() {
  const { t, i18n } = useTranslation();
  const me = useCurrentMe();
  const school = useCurrentSchool();
  const logout = useLogout();
  const name = displayName(me);
  const intro =
    me.schools.length === 0
      ? t("schools.none")
      : me.school
        ? t("schools.subtitle", { name })
        : t("schools.noAccess", { name });

  return (
    <AuthFrame school={null} width={560}>
      <h1>{t("schools.title")}</h1>
      <p className="text-ink-3">{intro}</p>
      {me.schools.map((item) => {
        const here = item.code === school.code;
        const current = here && me.school !== null;
        const suspended = item.status === "suspended";
        // Aucun droit à cette adresse : l'ouvrir ramènerait ici.
        const unavailable = suspended || (here && !current);
        return (
          <Card key={item.code} className={cn("shadow-none", suspended && "opacity-55")}>
            <div className="flex flex-wrap items-center gap-3.5 px-[18px] py-4">
              <SchoolBadge
                code={item.code}
                name={item.name}
                color={suspended ? "var(--color-gray-50)" : item.primary_color}
                textColor={suspended ? "var(--color-ink-2)" : item.text_color}
                logo={item.logo}
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <b>{item.name}</b>
                  {current && <StatusPill tone="info">{t("schools.current")}</StatusPill>}
                  {suspended && <StatusPill tone="gray">{t("schools.suspended")}</StatusPill>}
                </div>
                <span className="text-sm text-ink-3">{new URL(item.url).host}</span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {item.roles.map((role) => (
                    <Tag key={role.id}>{roleName(role, t)}</Tag>
                  ))}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <span className="text-xs text-ink-3">
                  {item.last_login_at
                    ? t("schools.lastVisit", {
                        date: formatVisit(
                          item.last_login_at,
                          i18n.language,
                          school.timezone,
                          (time) => t("common.today", { time }),
                        ),
                      })
                    : t("common.none")}
                </span>
                {unavailable ? (
                  <Button variant="outline" size="sm" disabled>
                    {t("schools.unavailable")}
                  </Button>
                ) : current ? (
                  <Button asChild size="sm">
                    <Link to="/">
                      {t("schools.open")}
                      <Icon name="chevron" size={16} />
                    </Link>
                  </Button>
                ) : (
                  <Button asChild size="sm">
                    <a href={`${item.url}/app/`}>
                      {t("schools.open")}
                      <Icon name="chevron" size={16} />
                    </a>
                  </Button>
                )}
              </div>
            </div>
          </Card>
        );
      })}
      {me.schools.length > 0 && <p className="text-sm text-ink-3">{t("schools.note")}</p>}
      {logout.isError && <Banner tone="due">{errorMessage(logout.error, t)}</Banner>}
      <div>
        <Button variant="ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
          <Icon name="logout" size={16} />
          {t("common.logout")}
        </Button>
      </div>
    </AuthFrame>
  );
}
