import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

// `.pill` des maquettes : point de couleur devant le texte.
const pillVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset before:size-1.5 before:rounded-full before:bg-current before:content-['']",
  {
    variants: {
      tone: {
        ok: "bg-ok-50 text-ok ring-ok-200",
        due: "bg-due-50 text-due ring-due-200",
        warn: "bg-warn-50 text-warn ring-warn-200",
        info: "bg-info-50 text-lake ring-info-200",
        gray: "bg-gray-50 text-ink-2 ring-line",
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
        "inline-block rounded-[6px] px-2 py-0.5 text-xs font-semibold",
        lot ? "bg-lamp-soft text-lamp-900" : "bg-gray-50 text-ink-2",
        className,
      )}
      {...props}
    />
  );
}
