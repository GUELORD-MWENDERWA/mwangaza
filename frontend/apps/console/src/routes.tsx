import type { RouteObject } from "react-router";

import { CodePage } from "./features/auth/CodePage";
import { FinishInAdminPage } from "./features/auth/FinishInAdminPage";
import { LoginLayout } from "./features/auth/LoginLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { IdentityPage } from "./features/identity/IdentityPage";
import { ConsoleShell } from "./features/shell/ConsoleShell";
import { RequireAdmin } from "./features/shell/RequireAdmin";

/** Écrans de la console ; les entrées du menu arrivent avec leur tâche (5.3, 5.4). */
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
          { path: "identity", element: <IdentityPage /> },
        ],
      },
    ],
  },
];
