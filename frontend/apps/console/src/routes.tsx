import type { ReactNode } from "react";
import type { RouteObject } from "react-router";

import { AccountPage } from "./features/accounts/AccountPage";
import { AccountsPage } from "./features/accounts/AccountsPage";
import { AnnouncementsPage } from "./features/announcements/AnnouncementsPage";
import { CodePage } from "./features/auth/CodePage";
import { FinishInAdminPage } from "./features/auth/FinishInAdminPage";
import { LoginLayout } from "./features/auth/LoginLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { DemoRequestsPage } from "./features/demoRequests/DemoRequestsPage";
import { DevicesPage } from "./features/devices/DevicesPage";
import { IdentityPage } from "./features/identity/IdentityPage";
import { JournalPage } from "./features/journal/JournalPage";
import { SupportSessionsPage } from "./features/journal/SupportSessionsPage";
import { AccessSheetPage } from "./features/schools/Demonstration";
import { NewSchoolPage } from "./features/schools/NewSchoolPage";
import { SchoolPage } from "./features/schools/SchoolPage";
import { SchoolsPage } from "./features/schools/SchoolsPage";
import { RIGHTS, type Right } from "./lib/rights";
import { Allowed, Home } from "./features/shell/Allowed";
import { ConsoleShell } from "./features/shell/ConsoleShell";
import { RequireAdmin } from "./features/shell/RequireAdmin";
import { SitePage } from "./features/site/SitePage";
import { TeamPage } from "./features/team/TeamPage";

const { schoolsView, schoolsManage, demosManage, accountsSupport, auditView } = RIGHTS;

/** Page gardée : un des droits demandés (EQ.2), sinon un message. */
const only = (rights: readonly Right[], page: ReactNode) => (
  <Allowed rights={rights}>{page}</Allowed>
);

/** Écrans de la console ; les entrées du menu arrivent avec leur tâche. */
export const routes: RouteObject[] = [
  {
    path: "/login",
    element: <LoginLayout />,
    children: [
      { index: true, element: <LoginPage /> },
      { path: "code", element: <CodePage /> },
      { path: "finish", element: <FinishInAdminPage /> },
    ],
  },
  {
    element: <RequireAdmin />,
    children: [
      {
        element: <ConsoleShell />,
        children: [
          { index: true, element: <Home /> },
          { path: "schools", element: only([schoolsView, demosManage], <SchoolsPage />) },
          { path: "schools/new", element: only([schoolsManage, demosManage], <NewSchoolPage />) },
          { path: "schools/:id", element: only([schoolsView, demosManage], <SchoolPage />) },
          { path: "schools/:id/access", element: only([demosManage], <AccessSheetPage />) },
          { path: "demo-requests", element: only([RIGHTS.leadsManage], <DemoRequestsPage />) },
          { path: "accounts", element: only([accountsSupport], <AccountsPage />) },
          { path: "accounts/:id", element: only([accountsSupport], <AccountPage />) },
          { path: "announcements", element: only([RIGHTS.newsPublish], <AnnouncementsPage />) },
          { path: "site", element: only([RIGHTS.siteEdit], <SitePage />) },
          { path: "identity", element: only([RIGHTS.identityEdit], <IdentityPage />) },
          { path: "devices", element: only([RIGHTS.healthView], <DevicesPage />) },
          { path: "journal", element: only([auditView], <JournalPage />) },
          {
            path: "journal/support",
            element: only([auditView, accountsSupport], <SupportSessionsPage />),
          },
          { path: "team", element: only([RIGHTS.teamManage], <TeamPage />) },
        ],
      },
    ],
  },
];
