import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.card` `.hd` `.bd` `.ft` des maquettes.
export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn("rounded-card border border-line bg-card shadow-card", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-b border-line px-[18px] py-3.5",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: ComponentProps<"h2">) {
  return <h2 className={cn("text-lg", className)} {...props} />;
}

export function CardContent({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("px-[18px] py-4", className)} {...props} />;
}

export function CardFooter({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 border-t border-line px-[18px] py-3",
        className,
      )}
      {...props}
    />
  );
}

/** `.list` des maquettes : lignes séparées d'un trait, libellé à gauche, valeur à droite. */
export function List({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex flex-col [&>*]:flex [&>*]:items-center [&>*]:justify-between [&>*]:gap-2.5 [&>*]:border-b [&>*]:border-line-soft [&>*]:py-3 [&>*:last-child]:border-b-0",
        className,
      )}
      {...props}
    />
  );
}
