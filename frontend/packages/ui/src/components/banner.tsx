import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { Icon, type IconName } from "../icons";
import { cn } from "../lib/cn";

// `.banner` des maquettes : icône à gauche, texte ; la couleur n'est jamais seule.
const bannerVariants = cva(
  "flex items-center gap-3 rounded-box border px-3.5 py-2.5 text-[.9rem]",
  {
    variants: {
      tone: {
        info: "border-[#c5dde1] bg-info-50 text-lake-700",
        warn: "border-[#f3d9a4] bg-warn-50 text-[#6b4000]",
        due: "border-[#f2c4be] bg-due-50 text-[#7a1810]",
        ok: "border-[#bfe0cc] bg-ok-50 text-[#155436]",
        lamp: "border-[#f1d98f] bg-lamp-soft text-[#5c4300]",
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
  VariantProps<typeof bannerVariants> & { icon?: IconName };

export function Banner({ className, tone, icon, children, ...props }: BannerProps) {
  return (
    <div className={cn(bannerVariants({ tone }), className)} {...props}>
      <Icon name={icon ?? icons[tone ?? "info"]} size={18} />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
