import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps, ReactNode } from "react";

import { Icon, type IconName } from "../icons";
import { cn } from "../lib/cn";

// `.banner` des maquettes : icône à gauche, alignée sur la première ligne du texte (pas au milieu
// d'un texte qui passe sur plusieurs lignes au téléphone) ; `action` (un bouton) à droite, centré,
// et au téléphone sous le texte, aligné avec lui (le texte garde toute la largeur, NB.3).
// La couleur n'est jamais seule.
const bannerVariants = cva(
  "flex flex-wrap items-start gap-3 rounded-box border px-4 py-3 text-md sm:flex-nowrap",
  {
    variants: {
      tone: {
        info: "border-info-200 bg-info-50 text-lake-700",
        warn: "border-warn-200 bg-warn-50 text-warn-900",
        due: "border-due-200 bg-due-50 text-due-900",
        ok: "border-ok-200 bg-ok-50 text-ok-900",
        lamp: "border-lamp-200 bg-lamp-soft text-lamp-900",
      },
    },
    defaultVariants: { tone: "info" },
  },
);

const icons: Record<NonNullable<VariantProps<typeof bannerVariants>["tone"]>, IconName> = {
  info: "info",
  warn: "alert",
  due: "alert",
  ok: "check",
  lamp: "sparkle",
};

type BannerProps = ComponentProps<"div"> &
  VariantProps<typeof bannerVariants> & { icon?: IconName; action?: ReactNode };

export function Banner({ className, tone, icon, action, children, ...props }: BannerProps) {
  return (
    <div className={cn(bannerVariants({ tone }), className)} {...props}>
      <Icon name={icon ?? icons[tone ?? "info"]} size={18} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 basis-[calc(100%-30px)] sm:basis-0">{children}</div>
      {action && <div className="ml-[30px] shrink-0 sm:ml-0 sm:self-center">{action}</div>}
    </div>
  );
}
