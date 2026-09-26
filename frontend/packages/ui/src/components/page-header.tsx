import type { ReactNode } from "react";

/** `.pagehead` des maquettes : fil d'Ariane, titre, sous-titre, actions à droite. */
export function PageHeader({
  title,
  subtitle,
  crumbs,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  crumbs?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {crumbs && <div className="mb-1.5 text-[.82rem] text-ink-3">{crumbs}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="mt-1 text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}
