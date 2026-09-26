import type { ReactNode } from "react";

import { Icon, type IconName } from "../icons";
import { cn } from "../lib/cn";

const tones = {
  due: "bg-due-50 text-due",
  warn: "bg-warn-50 text-warn",
  gray: "bg-gray-50 text-ink-2",
  lake: "bg-lake-50 text-lake",
};

/** Pages d'état (M8) : ce qui se passe, pourquoi, et quoi faire. */
export function StateCard({
  icon,
  tone,
  title,
  children,
  tag,
  actions,
  className,
}: {
  icon: IconName;
  tone: keyof typeof tones;
  title: ReactNode;
  children?: ReactNode;
  tag?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex min-h-[300px] flex-col items-center justify-center gap-3 rounded-card border border-line bg-card px-[22px] py-7 text-center shadow-card",
        className,
      )}
    >
      <div className={cn("grid size-16 place-items-center rounded-full", tones[tone])}>
        <Icon name={icon} size={28} />
      </div>
      <h1 className="text-lg">{title}</h1>
      {children && <div className="max-w-[340px] text-sm text-ink-3">{children}</div>}
      {tag}
      {actions && <div className="flex flex-wrap justify-center gap-3">{actions}</div>}
    </section>
  );
}
