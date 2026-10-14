import type { ReactNode } from "react";

/** `.pagehead` des maquettes : fil d'Ariane, titre, sous-titre, actions à droite. Au téléphone,
 *  les actions forment une grille de deux colonnes de même largeur ; une action seule, ou la
 *  dernière d'un nombre impair (souvent l'action principale), prend toute la largeur. */
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
        {crumbs && <div className="mb-1.5 text-sm text-ink-3">{crumbs}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="mt-1 text-ink-2">{subtitle}</p>}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-3 max-[560px]:grid max-[560px]:w-full max-[560px]:grid-cols-2 max-[560px]:gap-2 max-[560px]:[&>*]:whitespace-normal max-[560px]:[&>*]:text-center max-[560px]:[&>*:last-child:nth-child(odd)]:col-span-2">
          {actions}
        </div>
      )}
    </div>
  );
}
