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

/** Entrées du menu et les droits (un seul suffit) que demande chacune. */
export const MENU = [
  { to: "/", key: "dashboard", end: true, rights: [RIGHTS.schoolsView] },
  { to: "/schools", key: "schools", end: false, rights: [RIGHTS.schoolsView, RIGHTS.demosManage] },
  { to: "/demo-requests", key: "demoRequests", end: true, rights: [RIGHTS.leadsManage] },
  { to: "/accounts", key: "accounts", end: false, rights: [RIGHTS.accountsSupport] },
  { to: "/announcements", key: "announcements", end: true, rights: [RIGHTS.newsPublish] },
  { to: "/identity", key: "identity", end: true, rights: [RIGHTS.identityEdit] },
  { to: "/devices", key: "devices", end: true, rights: [RIGHTS.healthView] },
  {
    to: "/journal",
    key: "journal",
    end: false,
    rights: [RIGHTS.auditView, RIGHTS.accountsSupport],
  },
  { to: "/team", key: "team", end: true, rights: [RIGHTS.teamManage] },
] as const;

/** Le menu du membre ; sans le journal lui-même, l'entrée « Journal » mène aux sessions support. */
export function menuFor(can: Can) {
  return MENU.filter((item) => can(...item.rights)).map((item) =>
    item.key === "journal" && !can(RIGHTS.auditView) ? { ...item, to: "/journal/support" } : item,
  );
}
