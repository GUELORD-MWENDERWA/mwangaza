import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Skeleton } from "@mwangaza/ui";
import { Navigate, Outlet, type RouteObject } from "react-router";

import { ActivatePage } from "./features/auth/ActivatePage";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { ChildPage } from "./features/child/ChildPage";
import { AddSchoolPage } from "./features/home/AddSchoolPage";
import { HomePage } from "./features/home/HomePage";
import { InstallPage } from "./features/home/InstallPage";
import { useAccount } from "./lib/account";

/** Pages sans compte, montrées sans attendre le serveur : un parent déjà connecté va à l'accueil
 *  dès que son compte est lu. */
function GuestOnly() {
  const account = useAccount();
  if (account.data) return <Navigate to="/" replace />;
  return <Outlet />;
}

/** Pages du compte : sans session, la connexion. */
function RequireAccount() {
  const { t } = useTranslation();
  const account = useAccount();
  if (account.isPending) return <Skeleton label={t("common.loading")} />;
  if (account.isError) {
    return (
      <div className="mx-auto flex max-w-[440px] flex-col gap-3 p-4">
        <Banner tone="due">{errorMessage(account.error, t)}</Banner>
        <Button variant="outline" onClick={() => void account.refetch()}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }
  if (!account.data) return <Navigate to="/login" replace />;
  return <Outlet context={account.data} />;
}

export const routes: RouteObject[] = [
  {
    element: <GuestOnly />,
    children: [
      { path: "login", element: <LoginPage /> },
      { path: "activate", element: <ActivatePage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
    ],
  },
  {
    element: <RequireAccount />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "add-school", element: <AddSchoolPage /> },
      { path: "install", element: <InstallPage /> },
      { path: "children/:id", element: <ChildPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
