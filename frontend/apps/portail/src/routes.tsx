import { errorMessage, useTranslation } from "@mwangaza/i18n";
import { Banner, Button, Skeleton } from "@mwangaza/ui";
import { useState } from "react";
import { Navigate, Outlet, type RouteObject, useLocation } from "react-router";

import { AnnouncementsPage } from "./features/announcements/AnnouncementsPage";
import { ActivatePage } from "./features/auth/ActivatePage";
import { ForgotPasswordPage } from "./features/auth/ForgotPasswordPage";
import { LoginPage } from "./features/auth/LoginPage";
import { ChildPage } from "./features/child/ChildPage";
import { AddSchoolPage } from "./features/home/AddSchoolPage";
import { HomePage } from "./features/home/HomePage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { GuidePage } from "./features/home/GuidePage";
import { InstallPage } from "./features/home/InstallPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { useAccount } from "./lib/account";

/** Pages sans compte, montrées sans attendre le serveur : un parent déjà connecté va à l'accueil
 *  dès que son compte est lu. Compte arrivé par une connexion faite ici : la page mène elle-même
 *  plus loin (ex. le guide après l'activation), sans être devancée par l'accueil. */
function GuestOnly() {
  const account = useAccount();
  const [guest, setGuest] = useState(false);
  if (account.data === null && !guest) setGuest(true);
  if (account.data && !guest) return <Navigate to="/" replace />;
  return <Outlet />;
}

/** Pages du compte : sans session, la connexion, qui ramène ensuite à la page demandée. Réseau
 *  lent ou coupé au retour dans l'application : le compte déjà lu reste à l'écran. */
function RequireAccount() {
  const { t } = useTranslation();
  const location = useLocation();
  const account = useAccount();
  if (account.data) return <Outlet context={account.data} />;
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
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
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
      { path: "guide", element: <GuidePage /> },
      { path: "children/:id", element: <ChildPage /> },
      { path: "announcements", element: <AnnouncementsPage /> },
      { path: "notifications", element: <NotificationsPage /> },
      { path: "profile", element: <ProfilePage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
];
