import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.pill` des maquettes : point de couleur devant le texte.
const pillVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-xs font-bold whitespace-nowrap before:size-[7px] before:rounded-full before:bg-current before:content-['']",
  {
    variants: {
      tone: {
        ok: "bg-ok-50 text-ok",
        due: "bg-due-50 text-due",
        warn: "bg-warn-50 text-warn",
        info: "bg-info-50 text-lake",
        gray: "bg-gray-50 text-ink-2",
      },
    },
    defaultVariants: { tone: "gray" },
  },
);

export function StatusPill({
  className,
  tone,
  ...props
}: ComponentProps<"span"> & VariantProps<typeof pillVariants>) {
  return <span className={cn(pillVariants({ tone }), className)} {...props} />;
}

// `.tag` des maquettes ; `lot` = marqueur V1.1 / V1.2.
export function Tag({ className, lot, ...props }: ComponentProps<"span"> & { lot?: boolean }) {
  return (
    <span
      className={cn(
        "inline-block rounded-[6px] px-2 py-0.5 text-xs font-bold",
        lot ? "bg-lamp-soft text-lamp-900" : "bg-gray-50 text-ink-2",
        className,
      )}
      {...props}
    />
  );
}
