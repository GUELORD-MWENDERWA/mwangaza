// Droits de l'équipe de la plateforme (EQ.1, `accounts/platform_roles.py`). La console masque ce
// que les rôles du membre ne permettent pas (EQ.2) ; le serveur vérifie chaque point de toute façon.
import { useMe } from "./queries";

export const RIGHTS = {
  schoolsView: "platform.schools.view",
  schoolsManage: "platform.schools.manage",
  schoolsStop: "platform.schools.stop",
  accountsSupport: "platform.accounts.support",
  demosManage: "platform.demos.manage",
  leadsManage: "platform.leads.manage",
  siteEdit: "platform.site.edit",
  newsPublish: "platform.news.publish",
  healthView: "platform.health.view",
  auditView: "platform.audit.view",
  billingManage: "platform.billing.manage",
  identityEdit: "platform.identity.edit",
  teamManage: "platform.team.manage",
} as const;

export type Right = (typeof RIGHTS)[keyof typeof RIGHTS];
export const ALL_RIGHTS: Right[] = Object.values(RIGHTS);

export type Can = (...rights: Right[]) => boolean;

/** `can(a, b)` : vrai si le membre connecté a l'un de ces droits. */
export function useCan(): Can {
  const { data } = useMe();
  const mine = new Set(data?.platform_permissions ?? []);
  return (...rights) => rights.some((right) => mine.has(right));
}

/** Espace réel : `liveRight` ; essai ou démonstration : `platform.demos.manage` (comme le serveur). */
export function spaceRight(environment: string, liveRight: Right): Right {
  return environment === "live" ? liveRight : RIGHTS.demosManage;
}

/** Entrées du menu et les droits (un seul suffit) que demande chacune ; `group` : l'entrée de la
 *  barre sous laquelle elles se rangent (maquette `console/menu`). Les entrées d'un même groupe
 *  se suivent. */
export const MENU = [
  { to: "/", key: "dashboard", group: "dashboard", end: true, rights: [RIGHTS.schoolsView] },
  {
    to: "/schools",
    key: "schools",
    group: "clients",
    end: false,
    rights: [RIGHTS.schoolsView, RIGHTS.demosManage],
  },
  {
    to: "/demo-requests",
    key: "demoRequests",
    group: "clients",
    end: true,
    rights: [RIGHTS.leadsManage],
  },
  {
    to: "/business",
    key: "business",
    group: "clients",
    end: true,
    rights: [RIGHTS.schoolsView, RIGHTS.billingManage, RIGHTS.leadsManage],
  },
  {
    to: "/billing",
    key: "billing",
    group: "clients",
    end: true,
    rights: [RIGHTS.billingManage, RIGHTS.schoolsView],
  },
  {
    to: "/accounts",
    key: "accounts",
    group: "clients",
    end: false,
    rights: [RIGHTS.accountsSupport],
  },
  { to: "/site", key: "site", group: "site", end: true, rights: [RIGHTS.siteEdit] },
  { to: "/news", key: "news", group: "site", end: false, rights: [RIGHTS.siteEdit] },
  { to: "/photos", key: "photos", group: "site", end: true, rights: [RIGHTS.siteEdit] },
  {
    to: "/announcements",
    key: "announcements",
    group: "site",
    end: true,
    rights: [RIGHTS.newsPublish],
  },
  {
    to: "/identity",
    key: "identity",
    group: "platform",
    end: true,
    rights: [RIGHTS.identityEdit],
  },
  { to: "/devices", key: "devices", group: "platform", end: true, rights: [RIGHTS.healthView] },
  {
    to: "/journal",
    key: "journal",
    group: "platform",
    end: false,
    rights: [RIGHTS.auditView, RIGHTS.accountsSupport],
  },
  { to: "/team", key: "team", group: "platform", end: true, rights: [RIGHTS.teamManage] },
] as const;

/** Le menu du membre ; sans le journal lui-même, l'entrée « Journal » mène aux sessions support. */
export function menuFor(can: Can) {
  return MENU.filter((item) => can(...item.rights)).map((item) =>
    item.key === "journal" && !can(RIGHTS.auditView) ? { ...item, to: "/journal/support" } : item,
  );
}

export type MenuItem = ReturnType<typeof menuFor>[number];

/** La barre du haut : les entrées du membre rangées par groupe (un groupe vide disparaît). */
export function menuGroups(can: Can): { key: MenuItem["group"]; items: MenuItem[] }[] {
  const groups: { key: MenuItem["group"]; items: MenuItem[] }[] = [];
  for (const item of menuFor(can)) {
    const last = groups[groups.length - 1];
    if (last?.key === item.group) last.items.push(item);
    else groups.push({ key: item.group, items: [item] });
  }
  return groups;
}
