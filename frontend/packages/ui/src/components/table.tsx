import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.tbl` et `.tblwrap` des maquettes : en-tête gris clair, lignes séparées d'un trait ; ligne
// choisie (`aria-selected`) sur fond lac clair ; défilement horizontal sur petit écran.
export function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn(
          "w-full border-collapse text-[.9rem] [&_td]:border-b [&_td]:border-line-soft [&_td]:px-3 [&_td]:py-2.5 [&_td]:align-middle [&_th]:border-b [&_th]:border-line [&_th]:bg-[#f8fafa] [&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-[.8rem] [&_th]:font-bold [&_th]:whitespace-nowrap [&_th]:text-ink-2 [&_tr[aria-selected=true]_td]:bg-lake-50",
          className,
        )}
        {...props}
      />
    </div>
  );
}
