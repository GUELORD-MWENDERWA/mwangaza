import { articleForPath, HelpButton, type ScreenTable, WhatsNew } from "@mwangaza/help";
import { useLocation } from "react-router";

import { useAccount } from "../../lib/account";

// Table écran → article d'aide (AIDE.2) : `backend/apps/core/help/<langue>/portail/<clé>.md`.
export const HELP_SCREENS: ScreenTable = {
  install: "install-parent-app",
  children: "follow-child-payments",
  profile: "follow-child-payments",
};

/** Bouton « Aide » du Portail, pour l'en-tête sombre. */
export function PortalHelp() {
  const { pathname } = useLocation();
  return (
    <HelpButton
      app="portail"
      screen={articleForPath(HELP_SCREENS, pathname)}
      className="border-night-3 bg-transparent text-night-ink hover:border-night-soft"
    />
  );
}

/** « Quoi de neuf » du Portail : une fois par compte et par appareil. */
export function PortalNews() {
  const account = useAccount().data;
  return account ? <WhatsNew app="portail" userId={account.id} enabled /> : null;
}
