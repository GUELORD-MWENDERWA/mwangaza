import type { RouteObject } from "react-router";

import { AccountPage } from "./features/accounts/AccountPage";
import { AccountsPage } from "./features/accounts/AccountsPage";
import { AnnouncementsPage } from "./features/announcements/AnnouncementsPage";
import { CodePage } from "./features/auth/CodePage";
import { FinishInAdminPage } from "./features/auth/FinishInAdminPage";
import { LoginLayout } from "./features/auth/LoginLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DevicesPage } from "./features/devices/DevicesPage";
import { IdentityPage } from "./features/identity/IdentityPage";
import { JournalPage } from "./features/journal/JournalPage";
import { SupportSessionsPage } from "./features/journal/SupportSessionsPage";
import { AccessSheetPage } from "./features/schools/Demonstration";
import { NewSchoolPage } from "./features/schools/NewSchoolPage";
import { SchoolPage } from "./features/schools/SchoolPage";
import { SchoolsPage } from "./features/schools/SchoolsPage";
import { ConsoleShell } from "./features/shell/ConsoleShell";
import { RequireAdmin } from "./features/shell/RequireAdmin";

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
          { index: true, element: <DashboardPage /> },
          { path: "schools", element: <SchoolsPage /> },
          { path: "schools/new", element: <NewSchoolPage /> },
          { path: "schools/:id", element: <SchoolPage /> },
          { path: "schools/:id/access", element: <AccessSheetPage /> },
          { path: "accounts", element: <AccountsPage /> },
          { path: "accounts/:id", element: <AccountPage /> },
          { path: "announcements", element: <AnnouncementsPage /> },
          { path: "identity", element: <IdentityPage /> },
          { path: "devices", element: <DevicesPage /> },
          { path: "journal", element: <JournalPage /> },
          { path: "journal/support", element: <SupportSessionsPage /> },
        ],
      },
    ],
  },
];
