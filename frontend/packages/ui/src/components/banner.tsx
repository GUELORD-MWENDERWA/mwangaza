import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { Icon, type IconName } from "../icons";
import { cn } from "../lib/cn";

// `.banner` des maquettes : icône à gauche, texte ; la couleur n'est jamais seule.
const bannerVariants = cva("flex items-center gap-3 rounded-box border px-3.5 py-2.5 text-md", {
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
});

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
