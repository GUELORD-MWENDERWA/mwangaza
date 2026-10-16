// Adresses de la Gestion, sous /app/ (anglais, comme le code) : connexion en étapes, écrans
// réservés à un compte connecté, coquille avec le menu.
import type { ReactNode } from "react";
import type { RouteObject } from "react-router";

import { AccountPage } from "./features/account/AccountPage";
import { AccountTwoFactorPage } from "./features/account/AccountTwoFactorPage";
import { AnnouncementsPage } from "./features/announcements/AnnouncementsPage";
import { CalendarPage } from "./features/calendar/CalendarPage";
import { StaffNewsPage } from "./features/staff-news/StaffNewsPage";
import { SummonsPage } from "./features/summons/SummonsPage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { PlatformNewsPage } from "./features/platform-news/PlatformNewsPage";
import { AuditPage } from "./features/audit/AuditPage";
import { CodePage } from "./features/auth/CodePage";
import { LoginLayout } from "./features/auth/LoginLayout";
import { LoginPage } from "./features/auth/LoginPage";
import { LoginTwoFactorPage } from "./features/auth/LoginTwoFactorPage";
import { NewPasswordPage } from "./features/auth/NewPasswordPage";
import { CashPage } from "./features/cash/CashPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DevicesPage } from "./features/devices/DevicesPage";
import { FeesPage } from "./features/fees/FeesPage";
import { CoursesPage } from "./features/courses/CoursesPage";
import { TeachingLoadsPage } from "./features/courses/TeachingLoadsPage";
import { GradesPage } from "./features/grades/GradesPage";
import { GradeSheetsPage } from "./features/grades/GradeSheetsPage";
import { ReportCardPage } from "./features/grades/ReportCardPage";
import { GradeValidationPage } from "./features/grades/GradeValidationPage";
import { OrganisationPage } from "./features/organisation/OrganisationPage";
import { PriorPaymentsPage } from "./features/prior-payments/PriorPaymentsPage";
import { RolesPage } from "./features/roles/RolesPage";
import { SchoolChoicePage } from "./features/schools/SchoolChoicePage";
import { SchoolSettingsPage } from "./features/settings/SchoolSettingsPage";
import { StaffPage } from "./features/staff/StaffPage";
import { ClassListPage } from "./features/students/ClassListPage";
import { EditStudentPage } from "./features/students/EditStudentPage";
import { FamilyPage } from "./features/students/FamilyPage";
import { InvitationsPage } from "./features/students/InvitationsPage";
import { ImportStudentsPage } from "./features/students/ImportStudentsPage";
import { NewStudentPage } from "./features/students/NewStudentPage";
import { RegistrationFormPage } from "./features/students/RegistrationFormPage";
import { StudentPage } from "./features/students/StudentPage";
import { StudentStatementPage, UnpaidStatementsPage } from "./features/students/StatementPage";
import { StudentsPage } from "./features/students/StudentsPage";
import { AppShell } from "./features/shell/AppShell";
import { CreditsPage } from "./features/credits/CreditsPage";
import { CancellationsPage } from "./features/cancellations/CancellationsPage";
import { ClosingsPage } from "./features/closings/ClosingsPage";
import { ReceiptRegisterPage } from "./features/closings/ReceiptRegisterPage";
import { HomePage } from "./features/shell/HomePage";
import { MenuScreen } from "./features/shell/MenuScreen";
import { RequireAuth } from "./features/shell/RequireAuth";
import { SchoolGate } from "./features/shell/SchoolGate";
import { ParentRequestsPage } from "./features/parent-requests/ParentRequestsPage";
import { NotFound, RouteError } from "./features/status/StatusPages";
import { SupportPage } from "./features/support/SupportPage";
import { UnpaidExportPage } from "./features/unpaid/UnpaidExportPage";
import { UnpaidPage } from "./features/unpaid/UnpaidPage";
import { MENU_ITEMS, type MenuItem, type MenuKey } from "./lib/menu";

/** Écrans construits, par entrée du menu (chaque tâche ajoute le sien) ; les autres :
 *  « bientôt disponible ». Le droit de l'entrée est vérifié avant (`MenuScreen`). */
const SCREENS: Partial<Record<MenuKey, ReactNode>> = {
  dashboard: <DashboardPage />,
  students: <StudentsPage />,
  courses: <CoursesPage />,
  teachingLoads: <TeachingLoadsPage />,
  grades: <GradesPage />,
  gradeValidation: <GradeValidationPage />,
  reportCards: <ReportCardPage />,
  gradeSheets: <GradeSheetsPage />,
  schoolSettings: <SchoolSettingsPage />,
  organisation: <OrganisationPage />,
  cash: <CashPage />,
  credits: <CreditsPage />,
  cancellations: <CancellationsPage />,
  closings: <ClosingsPage />,
  unpaid: <UnpaidPage />,
  fees: <FeesPage />,
  staff: <StaffPage />,
  roles: <RolesPage />,
  devices: <DevicesPage />,
  audit: <AuditPage />,
  announcements: <AnnouncementsPage />,
  staffNews: <StaffNewsPage />,
  calendar: <CalendarPage />,
  summons: <SummonsPage />,
  parentRequests: <ParentRequestsPage />,
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
    path: "fees/prior-payments",
    item: { ...menuItem("fees"), permissions: ["finance.import_prior_payments"] },
    element: <PriorPaymentsPage />,
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
  { path: "students/class-list", item: menuItem("students"), element: <ClassListPage /> },
  { path: "students/invitations", item: menuItem("students"), element: <InvitationsPage /> },
  { path: "students/:id/form", item: menuItem("students"), element: <RegistrationFormPage /> },
  {
    path: "students/:id/statement",
    item: menuItem("students"),
    element: <StudentStatementPage />,
  },
  {
    path: "students/:id/finances/schedule",
    item: { ...menuItem("students"), permissions: ["finance.grant_discount"] },
    element: <StudentPage schedule />,
  },
  { path: "students/:id/:tab?", item: menuItem("students"), element: <StudentPage /> },
  { path: "families/:id", item: menuItem("students"), element: <FamilyPage /> },
  { path: "cash-closings/register", item: menuItem("closings"), element: <ReceiptRegisterPage /> },
  { path: "unpaid/export", item: menuItem("unpaid"), element: <UnpaidExportPage /> },
  { path: "unpaid/statements", item: menuItem("unpaid"), element: <UnpaidStatementsPage /> },
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
                  { path: "platform-news", element: <PlatformNewsPage /> },
                  { path: "notifications", element: <NotificationsPage /> },
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
