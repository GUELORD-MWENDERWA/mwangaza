import type { ReactNode } from "react";

import { Icon, type IconName } from "../icons";
import { cn } from "../lib/cn";
import { Card } from "./card";

const tones = { ok: "text-ok", warn: "text-warn", due: "text-due" };
const chips = {
  lake: "bg-lake-50 text-lake",
  ok: "bg-ok-50 text-ok",
  warn: "bg-warn-50 text-warn",
  due: "bg-due-50 text-due",
  lamp: "bg-lamp-soft text-lamp-900",
};

/** `.kpi` des maquettes : libellé, grand chiffre tabulaire, précision en dessous ; `icon` dans
 *  une pastille teintée en haut à droite (couleur `chip`, celle du chiffre par défaut). */
export function Kpi({
  label,
  value,
  sub,
  tone,
  icon,
  chip,
  className,
  children,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: keyof typeof tones;
  icon?: IconName;
  chip?: keyof typeof chips;
  className?: string;
  /** Sous le chiffre : barre de progression, mini-graphique. */
  children?: ReactNode;
}) {
  return (
    <Card className={cn("relative flex flex-col px-5 py-4", className)}>
      {/* Pastille dans le coin (`.kpi .chip` des maquettes) : un libellé sur deux lignes ne
          passe jamais sous le chiffre. */}
      <p className={cn("text-sm font-semibold text-ink-2", icon && "min-h-7 pr-12")}>{label}</p>
      {icon && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute top-4 right-5 grid size-9 place-items-center rounded-box",
            chips[chip ?? tone ?? "lake"],
          )}
        >
          <Icon name={icon} size={18} />
        </span>
      )}
      <p
        className={cn(
          "text-2xl font-extrabold tracking-tight tabular-nums",
          !icon && "mt-1",
          tone && tones[tone],
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-sm break-words text-ink-3">{sub}</p>}
      {children}
    </Card>
  );
}
