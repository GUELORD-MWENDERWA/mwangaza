import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

/** `.code` des maquettes : clé, code à recopier (chasse fixe, lettres espacées). */
export function Code({ className, ...props }: ComponentProps<"code">) {
  return (
    <code className={cn("font-mono font-bold tracking-[.12em] break-all", className)} {...props} />
  );
}

/** `.codes` des maquettes : codes de secours sur deux colonnes. */
export function CodeList({ codes, className }: { codes: string[]; className?: string }) {
  return (
    <ul
      className={cn(
        "grid grid-cols-2 gap-x-[18px] gap-y-2 font-mono text-[1.02rem] tracking-[.06em]",
        className,
      )}
    >
      {codes.map((code) => (
        <li key={code}>{code}</li>
      ))}
    </ul>
  );
}
