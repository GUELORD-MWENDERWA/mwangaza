// Adresses de la Gestion, sous /app/ (anglais, comme le code) : connexion en étapes, écrans
// réservés à un compte connecté, coquille avec le menu.
import type { ReactNode } from "react";
import type { RouteObject } from "react-router";

import { AccountPage } from "./features/account/AccountPage";
import { AccountTwoFactorPage } from "./features/account/AccountTwoFactorPage";
import { AuditPage } from "./features/audit/AuditPage";
import { CodePage } from "./features/auth/CodePage";
import { LoginLayout } from "./features/auth/LoginLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { LoginTwoFactorPage } from "./features/auth/LoginTwoFactorPage";
import { NewPasswordPage } from "./features/auth/NewPasswordPage";
import { OrganisationPage } from "./features/organisation/OrganisationPage";
import { RolesPage } from "./features/roles/RolesPage";
import { SchoolChoicePage } from "./features/schools/SchoolChoicePage";
import { SchoolSettingsPage } from "./features/settings/SchoolSettingsPage";
import { StaffPage } from "./features/staff/StaffPage";
import { EditStudentPage } from "./features/students/EditStudentPage";
import { FamilyPage } from "./features/students/FamilyPage";
import { ImportStudentsPage } from "./features/students/ImportStudentsPage";
import { NewStudentPage } from "./features/students/NewStudentPage";
import { StudentPage } from "./features/students/StudentPage";
import { StudentsPage } from "./features/students/StudentsPage";
import { AppShell } from "./features/shell/AppShell";
import { HomePage } from "./features/shell/HomePage";
import { MenuScreen } from "./features/shell/MenuScreen";
import { RequireAuth } from "./features/shell/RequireAuth";
import { SchoolGate } from "./features/shell/SchoolGate";
import { NotFound, RouteError } from "./features/status/StatusPages";
import { SupportPage } from "./features/support/SupportPage";
import { MENU_ITEMS, type MenuItem, type MenuKey } from "./lib/menu";

/** Écrans construits, par entrée du menu (chaque tâche ajoute le sien) ; les autres :
 *  « bientôt disponible ». Le droit de l'entrée est vérifié avant (`MenuScreen`). */
const SCREENS: Partial<Record<MenuKey, ReactNode>> = {
  students: <StudentsPage />,
  schoolSettings: <SchoolSettingsPage />,
  organisation: <OrganisationPage />,
  staff: <StaffPage />,
  roles: <RolesPage />,
  audit: <AuditPage />,
};

const menuItem = (key: MenuKey) => MENU_ITEMS.find((item) => item.key === key)!;

/** Écrans ouverts depuis une entrée du menu, avec leur propre droit (ex. inscrire un élève). */
const PAGES: { path: string; item: MenuItem; element: ReactNode }[] = [
  {
    path: "students/new",
    item: { ...menuItem("students"), permissions: ["students.edit"] },
    element: <NewStudentPage />,
  },
  {
    path: "students/import/:importId?",
    item: { ...menuItem("students"), permissions: ["students.import"] },
    element: <ImportStudentsPage />,
  },
  {
    path: "students/:id/edit",
    item: { ...menuItem("students"), permissions: ["students.edit"] },
    element: <EditStudentPage />,
  },
  { path: "students/:id/:tab?", item: menuItem("students"), element: <StudentPage /> },
  { path: "families/:id", item: menuItem("students"), element: <FamilyPage /> },
];

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <SchoolGate />,
    errorElement: <RouteError standalone />,
    children: [
      {
        path: "login",
        element: <LoginLayout />,
        children: [
          { index: true, element: <LoginPage /> },
          { path: "code", element: <CodePage /> },
          { path: "new-password", element: <NewPasswordPage /> },
          { path: "two-factor", element: <LoginTwoFactorPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          { path: "schools", element: <SchoolChoicePage /> },
          { path: "support", element: <SupportPage /> },
          {
            element: <AppShell />,
            children: [
              {
                errorElement: <RouteError />,
                children: [
                  { index: true, element: <HomePage /> },
                  { path: "account", element: <AccountPage /> },
                  { path: "account/two-factor", element: <AccountTwoFactorPage /> },
                  ...MENU_ITEMS.map((item) => ({
                    path: item.path,
                    element: <MenuScreen item={item}>{SCREENS[item.key]}</MenuScreen>,
                  })),
                  ...PAGES.map(({ path, item, element }) => ({
                    path,
                    element: <MenuScreen item={item}>{element}</MenuScreen>,
                  })),
                  { path: "*", element: <NotFound /> },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
];
