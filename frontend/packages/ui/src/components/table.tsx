import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.tbl` et `.tblwrap` des maquettes : en-tête gris clair, lignes séparées d'un trait ; ligne
// choisie (`aria-selected`) sur fond lac clair, ligne en erreur ou en avertissement
// (`data-tone="due"` / `"warn"`, `.errrow` / `.warnrow`) ; sous 900 px, les cellules ne se coupent
// pas (`.tbl` dans styles.css) et le tableau défile dans sa carte ; `data-wrap` sur une cellule de
// texte long la laisse passer à la ligne.
// Titre d'une colonne de montants (`th.num` des maquettes) : `className="text-right"` sur le `th`,
// rendu plus fort que l'alignement à gauche par défaut, sinon le titre se décale de ses valeurs.
export function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn(
          "tbl w-full border-collapse text-md [&_td]:border-b [&_td]:border-line-soft [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-middle [&_th]:border-b [&_th]:border-line [&_th]:bg-table-head [&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th.text-right]:text-right [&_th]:text-xs [&_th]:font-bold [&_th]:whitespace-nowrap [&_th]:text-ink-2 [&_tr[aria-selected=true]_td]:bg-lake-50 [&_tr[data-tone=due]_td]:bg-due-50 [&_tr[data-tone=warn]_td]:bg-warn-50",
          className,
        )}
        {...props}
      />
    </div>
  );
}
