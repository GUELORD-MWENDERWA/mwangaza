// Droits de l'équipe de la plateforme (EQ.1, `accounts/platform_roles.py`). La console masque ce
// que les rôles du membre ne permettent pas (EQ.2) ; le serveur vérifie chaque point de toute façon.
import type { IconName } from "@mwangaza/ui";

import type { ConsoleMode } from "./mode";
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
  aiManage: "platform.ai.manage",
  supportHandle: "platform.support.handle",
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

/** Entrées du menu latéral (maquette `console/tableau-de-bord`), rangées sous quatre titres, et
 *  les droits (un seul suffit) que demande chacune. `live` : la page n'existe qu'en mode réel (le
 *  serveur répond 404 en démonstration). Les entrées d'un même groupe se suivent. */
export const MENU = [
  {
    to: "/",
    key: "dashboard",
    group: "pilotage",
    icon: "home",
    end: true,
    live: false,
    rights: [RIGHTS.schoolsView],
  },
  {
    to: "/business",
    key: "business",
    group: "pilotage",
    icon: "wallet",
    end: true,
    live: true,
    rights: [RIGHTS.schoolsView, RIGHTS.billingManage, RIGHTS.leadsManage],
  },
  {
    to: "/schools",
    key: "schools",
    group: "clients",
    icon: "school",
    end: false,
    live: false,
    rights: [RIGHTS.schoolsView, RIGHTS.demosManage],
  },
  {
    to: "/demo-requests",
    key: "demoRequests",
    group: "clients",
    icon: "inbox",
    end: true,
    live: false,
    rights: [RIGHTS.leadsManage],
  },
  {
    to: "/support",
    key: "support",
    group: "clients",
    icon: "chat",
    end: false,
    live: false,
    rights: [RIGHTS.supportHandle],
  },
  {
    to: "/billing",
    key: "billing",
    group: "clients",
    icon: "card",
    end: true,
    live: true,
    rights: [RIGHTS.billingManage, RIGHTS.schoolsView],
  },
  {
    to: "/accounts",
    key: "accounts",
    group: "clients",
    icon: "users",
    end: false,
    live: false,
    rights: [RIGHTS.accountsSupport],
  },
  {
    to: "/announcements",
    key: "announcements",
    group: "clients",
    icon: "megaphone",
    end: true,
    live: false,
    rights: [RIGHTS.newsPublish],
  },
  {
    to: "/site",
    key: "site",
    group: "site",
    icon: "globe",
    end: true,
    live: true,
    rights: [RIGHTS.siteEdit],
  },
  {
    to: "/news",
    key: "news",
    group: "site",
    icon: "book",
    end: false,
    live: true,
    rights: [RIGHTS.siteEdit],
  },
  {
    to: "/photos",
    key: "photos",
    group: "site",
    icon: "image",
    end: true,
    live: true,
    rights: [RIGHTS.siteEdit],
  },
  {
    to: "/identity",
    key: "identity",
    group: "platform",
    icon: "settings",
    end: true,
    live: true,
    rights: [RIGHTS.identityEdit],
  },
  {
    to: "/devices",
    key: "devices",
    group: "platform",
    icon: "phone",
    end: true,
    live: false,
    rights: [RIGHTS.healthView],
  },
  {
    to: "/ai",
    key: "ai",
    group: "platform",
    icon: "sparkle",
    end: true,
    live: false,
    rights: [RIGHTS.aiManage],
  },
  {
    to: "/journal",
    key: "journal",
    group: "platform",
    icon: "journal",
    end: false,
    live: false,
    rights: [RIGHTS.auditView, RIGHTS.accountsSupport],
  },
  {
    to: "/team",
    key: "team",
    group: "platform",
    icon: "shield",
    end: true,
    live: true,
    rights: [RIGHTS.teamManage],
  },
] as const satisfies readonly {
  to: string;
  key: string;
  group: "pilotage" | "clients" | "site" | "platform";
  icon: IconName;
  end: boolean;
  live: boolean;
  rights: readonly Right[];
}[];

/** Le menu du membre dans ce mode ; sans le journal lui-même, « Journal » mène aux sessions
 *  support. */
export function menuFor(can: Can, mode: ConsoleMode = "live") {
  return MENU.filter((item) => can(...item.rights) && (mode === "live" || !item.live)).map(
    (item) =>
      item.key === "journal" && !can(RIGHTS.auditView) ? { ...item, to: "/journal/support" } : item,
  );
}

export type MenuItem = ReturnType<typeof menuFor>[number];

/** Les entrées du membre rangées par titre (un titre sans page disparaît). */
export function menuGroups(
  can: Can,
  mode: ConsoleMode = "live",
): { key: MenuItem["group"]; items: MenuItem[] }[] {
  const groups: { key: MenuItem["group"]; items: MenuItem[] }[] = [];
  for (const item of menuFor(can, mode)) {
    const last = groups[groups.length - 1];
    if (last?.key === item.group) last.items.push(item);
    else groups.push({ key: item.group, items: [item] });
  }
  return groups;
}
