import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.tbl` et `.tblwrap` des maquettes : en-tête gris clair, lignes séparées d'un trait ; ligne
// choisie (`aria-selected`) sur fond lac clair, ligne en erreur ou en avertissement
// (`data-tone="due"` / `"warn"`, `.errrow` / `.warnrow`) ; sous 900 px, les cellules ne se coupent
// pas (`.tbl` dans styles.css) et le tableau défile dans sa carte ; `data-wrap` sur une cellule de
// texte long la laisse passer à la ligne. `freeze` (tableaux qu'on remplit : notes, fiches de
// cotes, délibération) : la ligne des titres et la 1re colonne (le nom de l'élève) restent visibles
// quand on fait défiler un long tableau vers le bas ou vers la droite (`.tbl-freeze`).
// Titre d'une colonne de montants (`th.num` des maquettes) : `className="text-right"` sur le `th`,
// rendu plus fort que l'alignement à gauche par défaut, sinon le titre se décale de ses valeurs.
export function Table({
  className,
  stacked,
  freeze,
  ...props
}: ComponentProps<"table"> & {
  /** Téléphone : une carte par ligne (cellules `data-label`), au lieu de défiler de côté. */
  stacked?: boolean;
  /** Titres et 1re colonne figés quand le tableau défile (tableaux à remplir). */
  freeze?: boolean;
}) {
  return (
    <div className={freeze ? "tbl-freeze-wrap overflow-auto" : "overflow-x-auto"}>
      <table
        className={cn(
          stacked && "tbl-stacked",
          freeze && "tbl-freeze",
          "tbl w-full border-collapse text-md [&_td]:border-b [&_td]:border-line-soft [&_td]:px-4 [&_td]:py-3 [&_td]:align-middle [&_th]:border-b [&_th]:border-line [&_th]:bg-table-head [&_th]:px-4 [&_th]:py-2.5 [&_th]:text-left [&_th.text-right]:text-right [&_th]:text-xs [&_th]:font-semibold [&_th]:whitespace-nowrap [&_th]:text-ink-3 [&_tbody_tr]:transition-colors [&_tbody_tr:hover_td]:bg-table-head [&_tr:last-child_td]:border-b-0 [&_tfoot_td]:border-t [&_tfoot_td]:border-line [&_tr[aria-selected=true]_td]:bg-lake-50 [&_tr[data-tone=due]_td]:bg-due-50 [&_tr[data-tone=warn]_td]:bg-warn-50",
          className,
        )}
        {...props}
      />
    </div>
  );
}
