import type { ReactNode } from "react";

import { Icon, type IconName } from "../icons";

/** `.toast` des maquettes : notification passagère en bas de l'écran (ex. nouvelle version). */
export function Toast({
  icon = "sparkle",
  children,
  action,
}: {
  icon?: IconName;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      role="status"
      className="fixed right-4 bottom-4 left-4 z-50 mx-auto flex max-w-[480px] animate-fade-in items-center gap-3 rounded-card bg-basalt px-4 py-3 text-md text-basalt-ink shadow-float"
    >
      <Icon name={icon} size={20} />
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  );
}
